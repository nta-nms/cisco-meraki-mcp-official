# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# SPDX-License-Identifier: Apache-2.0

# oss-safe
import logging

import pytest
from pydantic import SecretStr

from cisco_meraki_mcp.tools.logging import (
    REDACTED_PLACEHOLDER,
    SENSITIVE_PARAM_NAMES,
    ToolLogger,
    log_tool_invocation,
    redact_value,
    resolve_request_id,
)


def test_parameter_names_uses_available_explicit_params():
    tool_logger = ToolLogger("sample_tool", ["b", "missing"])
    kwargs = {"a": 1, "b": 2}

    assert tool_logger.parameter_names(kwargs) == ["b"]


def test_parameter_names_defaults_to_all_keys():
    tool_logger = ToolLogger("sample_tool")
    kwargs = {"foo": 1, "bar": 2}

    assert set(tool_logger.parameter_names(kwargs)) == {"foo", "bar"}


def test_parameter_names_empty_kwargs_with_none_log_params():
    tool_logger = ToolLogger("sample_tool")

    assert tool_logger.parameter_names({}) == []


@pytest.mark.parametrize("name", sorted(SENSITIVE_PARAM_NAMES))
def test_redact_value_redacts_sensitive_param_names(name):
    assert redact_value(name, "plain-text-secret") == REDACTED_PLACEHOLDER


@pytest.mark.parametrize(
    "name",
    [
        "Api_Key",
        "AUTHORIZATION",
        "Meraki_Api_Key",
        "Meraki_Dashboard_Api_Key",
        "Token",
        "PASSWORD",
    ],
)
def test_redact_value_match_folds_case_for_mixed_case_names(name):
    assert redact_value(name, "abc") == REDACTED_PLACEHOLDER


def test_redact_value_redacts_secretstr_regardless_of_name():
    assert redact_value("anything", SecretStr("x")) == REDACTED_PLACEHOLDER


def test_redact_value_passes_through_non_sensitive_param():
    assert redact_value("capability_id", "getNetworkWirelessSsids") == (
        "getNetworkWirelessSsids"
    )


@pytest.mark.parametrize(
    "raised",
    [RuntimeError("No active HTTP request found."), LookupError()],
)
def test_resolve_request_id_returns_minted_uuid_outside_http_context(
    mocker, raised
):
    mocker.patch(
        "cisco_meraki_mcp.tools.logging.get_http_request",
        side_effect=raised,
    )

    request_id, session_id = resolve_request_id()

    assert request_id
    assert session_id is None


def test_resolve_request_id_extracts_mcp_session_id_from_request(mocker):
    fake_request = mocker.MagicMock()
    fake_request.headers = {"mcp-session-id": "sess-abc"}
    mocker.patch(
        "cisco_meraki_mcp.tools.logging.get_http_request",
        return_value=fake_request,
    )

    request_id, session_id = resolve_request_id()

    assert request_id
    assert session_id == "sess-abc"


def test_resolve_request_id_uses_upstream_request_id_when_provided(mocker):
    fake_request = mocker.MagicMock()
    fake_request.headers = {
        "x-request-id": "upstream-req-1",
        "mcp-session-id": "sess-1",
    }
    mocker.patch(
        "cisco_meraki_mcp.tools.logging.get_http_request",
        return_value=fake_request,
    )

    request_id, session_id = resolve_request_id()

    assert request_id == "upstream-req-1"
    assert session_id == "sess-1"


def test_log_tool_invocation_returns_tool_logger():
    assert isinstance(log_tool_invocation("sample_tool"), ToolLogger)


@pytest.mark.asyncio
async def test_log_tool_invocation_emits_non_fatal_notifications(
    mocker, caplog
):
    mocker.patch(
        "cisco_meraki_mcp.tools.logging.resolve_request_id",
        return_value=("r1", "s1"),
    )
    ctx = mocker.Mock()
    ctx.info = mocker.AsyncMock()

    def summary_builder(kwargs, result):
        assert kwargs["visible"] == "value"
        assert result == "ok"
        return {"visible": "value"}

    def broken_summary(_kwargs, _result):
        raise RuntimeError("summary failed")

    @log_tool_invocation("sample_tool", summary_builder=summary_builder)
    async def emits(**kwargs):
        return "ok"

    assert await emits(ctx=ctx, visible="value") == "ok"
    ctx.info.assert_awaited_once_with(
        "sample_tool completed",
        extra={
            "tool": "sample_tool",
            "visible": "value",
            "request_id": "r1",
            "session_id": "s1",
        },
    )

    @log_tool_invocation("sample_tool", summary_builder=broken_summary)
    async def summary_fails(**kwargs):
        return "ok"

    @log_tool_invocation("sample_tool")
    async def notification_fails(**kwargs):
        return "ok"

    with caplog.at_level(
        logging.WARNING,
        logger="cisco_meraki_mcp.tools.logging",
    ):
        assert await summary_fails(ctx=ctx) == "ok"

        failed_ctx = mocker.Mock()
        failed_ctx.info = mocker.AsyncMock(
            side_effect=RuntimeError("send failed")
        )
        assert await notification_fails(ctx=failed_ctx) == "ok"

    failed_ctx.info.assert_awaited_once()
    assert "Failed to build MCP tool notification summary" in caplog.text
    assert "Failed to emit MCP tool notification" in caplog.text


@pytest.mark.asyncio
async def test_log_tool_invocation_emits_session_correlation_ids(
    mocker, caplog
):
    mocker.patch(
        "cisco_meraki_mcp.tools.logging.resolve_request_id",
        return_value=("r1", "s1"),
    )

    @log_tool_invocation("sample_tool")
    async def fn(**kwargs):
        return "ok"

    with caplog.at_level(logging.INFO, logger=__name__):
        await fn()

    blob = "\n".join(r.getMessage() for r in caplog.records)
    assert "request_id=r1 session_id=s1" in blob
    assert caplog.records
    assert {record.name for record in caplog.records} == {__name__}
    assert {record.tool for record in caplog.records} == {"sample_tool"}
    assert {record.request_id for record in caplog.records} == {"r1"}
    assert {record.session_id for record in caplog.records} == {"s1"}


@pytest.mark.asyncio
async def test_log_tool_invocation_omits_session_id_when_absent(
    mocker, caplog
):
    mocker.patch(
        "cisco_meraki_mcp.tools.logging.resolve_request_id",
        return_value=("r2", None),
    )

    @log_tool_invocation("sample_tool")
    async def fn(**kwargs):
        return "ok"

    with caplog.at_level(logging.INFO, logger=__name__):
        await fn()

    blob = "\n".join(r.getMessage() for r in caplog.records)
    assert "request_id=r2" in blob
    assert "session_id=" not in blob
    assert caplog.records
    assert {record.name for record in caplog.records} == {__name__}
    assert {record.tool for record in caplog.records} == {"sample_tool"}
    assert {record.request_id for record in caplog.records} == {"r2"}
    assert {record.session_id for record in caplog.records} == {None}


@pytest.mark.asyncio
async def test_log_tool_invocation_redacts_secretstr_param(caplog):
    canary = "super-secret-canary-9c2e"

    @log_tool_invocation("sample_tool")
    async def fn(**kwargs):
        return "ok"

    with caplog.at_level(logging.INFO, logger=__name__):
        await fn(arbitrary_name=SecretStr(canary))

    blob = "\n".join(r.getMessage() for r in caplog.records)
    assert canary not in blob
    assert REDACTED_PLACEHOLDER in blob


@pytest.mark.asyncio
async def test_log_tool_invocation_redacts_meraki_dashboard_api_key(caplog):
    canary = "plain-canary-name-key"

    @log_tool_invocation("sample_tool")
    async def fn(**kwargs):
        return "ok"

    with caplog.at_level(logging.INFO, logger=__name__):
        await fn(meraki_dashboard_api_key=canary)

    blob = "\n".join(r.getMessage() for r in caplog.records)
    assert canary not in blob
    assert REDACTED_PLACEHOLDER in blob


@pytest.mark.asyncio
async def test_log_tool_invocation_does_not_redact_safe_param(caplog):
    @log_tool_invocation("sample_tool", ["capability_id"])
    async def fn(**kwargs):
        return "ok"

    with caplog.at_level(logging.INFO, logger=__name__):
        await fn(capability_id="getNetworkWirelessSsids")

    blob = "\n".join(r.getMessage() for r in caplog.records)
    assert "getNetworkWirelessSsids" in blob
    assert REDACTED_PLACEHOLDER not in blob
