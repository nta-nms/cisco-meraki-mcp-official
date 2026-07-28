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

from cisco_meraki_mcp.contracts.execute import ExecuteError, ExecuteReadOutput
from cisco_meraki_mcp.providers.meraki_client import MerakiApiError
from cisco_meraki_mcp.providers.request_validation import (
    RequestValidationError,
)
from cisco_meraki_mcp.tools.execute_api import (
    ExecuteApiFactory,
    normalize_execute_data,
)


@pytest.fixture
def wireless_execute_call(execute_tool, sdk_execute_client):
    async def call():
        return await execute_tool(
            capability_id="getNetworkWirelessSsids",
            parameters={"networkId": "N_123"},
        )

    return call


@pytest.mark.parametrize(
    ("payload", "expected"),
    [
        ([{"id": "N_123"}], {"items": [{"id": "N_123"}]}),
        ("ok", {"value": "ok"}),
    ],
    ids=["list", "scalar"],
)
def test_normalize_execute_data_wraps_non_mapping_payloads(
    payload,
    expected,
):
    data = normalize_execute_data(payload)

    assert data.model_dump() == expected


@pytest.mark.asyncio
async def test_execute_api_calls_sdk_operation(
    execute_tool,
    sdk_execute_client,
):
    result = await execute_tool(
        capability_id="getNetworkWirelessSsids",
        parameters={"networkId": "N_123"},
    )

    assert isinstance(result, ExecuteReadOutput)
    assert result.capability_id == "getNetworkWirelessSsids"
    assert result.data.model_dump() == sdk_execute_client.sdk_result
    assert (
        sdk_execute_client.meraki_client.call_args.kwargs[
            "api_key"
        ].get_secret_value()
        == "configured-key"
    )
    sdk_execute_client.client.operation_for.assert_called_once_with(
        "getNetworkWirelessSsids"
    )
    sdk_execute_client.client.request.assert_awaited_once_with(
        sdk_execute_client.operation,
        networkId="N_123",
    )
    sdk_execute_client.client.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_execute_api_applies_request_instrumentation(
    mcp_context,
    product_classifier,
    sdk_execute_client,
):
    calls = []

    def instrument(fn):
        async def wrapped(*args, **kwargs):
            calls.append((args, kwargs))
            return await fn(*args, **kwargs)

        return wrapped

    factory = ExecuteApiFactory(
        product_classifier=product_classifier,
        credential_provider=lambda: SecretStr("configured-key"),
        instrument_api_request=instrument,
    )

    result = await factory.tool()(
        capability_id="getNetworkWirelessSsids",
        ctx=mcp_context,
        parameters={"networkId": "N_123"},
    )

    assert isinstance(result, ExecuteReadOutput)
    assert calls == [
        (
            (sdk_execute_client.operation,),
            {"networkId": "N_123"},
        )
    ]


@pytest.mark.asyncio
async def test_execute_api_errors_when_api_key_missing(
    mcp_context,
    product_classifier,
):
    factory = ExecuteApiFactory(
        product_classifier=product_classifier,
        credential_provider=lambda: None,
        instrument_api_request=lambda fn: fn,
    )
    tool = factory.tool()

    result = await tool(
        capability_id="getNetworkWirelessSsids",
        ctx=mcp_context,
        parameters={"networkId": "N_123"},
    )

    assert isinstance(result, ExecuteError)
    assert "api key" in result.error.lower()
    assert "Authorization: Bearer" in result.recovery_suggestion
    assert "MERAKI_DASHBOARD_API_KEY" in result.recovery_suggestion


@pytest.mark.asyncio
async def test_execute_api_unknown_capability(execute_tool):
    result = await execute_tool(
        capability_id="unknownCapability",
        parameters={},
    )

    assert isinstance(result, ExecuteError)
    assert "not found" in result.error.lower()
    assert result.capability_id == "unknownCapability"
    assert result.recovery_suggestion


def test_execute_api_notification_summary():
    summary = ExecuteApiFactory.notification_summary(
        {"capability_id": "unknownCapability"},
        ExecuteError(error="not found", recovery_suggestion="search again"),
    )

    assert summary == {
        "capability_id": "unknownCapability",
        "outcome": "error",
    }


@pytest.mark.asyncio
async def test_execute_api_returns_product_for_wireless(wireless_execute_call):
    result = await wireless_execute_call()

    assert isinstance(result, ExecuteReadOutput)
    assert result.product


@pytest.mark.asyncio
async def test_execute_api_missing_required_param(execute_tool):
    result = await execute_tool(
        capability_id="getNetworkWirelessSsids",
        parameters={},
    )

    assert isinstance(result, ExecuteError)
    assert "missing required" in result.error.lower()
    assert "networkId" in result.recovery_suggestion


@pytest.mark.asyncio
async def test_execute_api_errors_for_sdk_unsupported_capability(
    execute_tool,
    sdk_execute_client,
):
    sdk_execute_client.client.operation_for.return_value = None

    result = await execute_tool(
        capability_id="getNetworkWirelessSsids",
        parameters={"networkId": "N_123"},
    )

    assert isinstance(result, ExecuteError)
    assert "not supported" in result.error.lower()
    sdk_execute_client.client.request.assert_not_awaited()
    sdk_execute_client.client.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_execute_api_returns_error_for_meraki_api_error(
    execute_tool,
    sdk_execute_client,
):
    sdk_execute_client.client.request.side_effect = MerakiApiError(
        status=403,
        message="Forbidden",
    )

    result = await execute_tool(
        capability_id="getNetworkWirelessSsids",
        parameters={"networkId": "N_123"},
    )

    assert isinstance(result, ExecuteError)
    assert result.error == "Access denied."
    assert result.recovery_suggestion == (
        "This API key lacks permission for getNetworkWirelessSsids."
    )
    sdk_execute_client.client.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_execute_api_maps_400_invalid_parameters(
    execute_tool,
    sdk_execute_client,
):
    sdk_execute_client.client.request.side_effect = MerakiApiError(
        status=400,
        message="raw sdk detail",
    )

    result = await execute_tool(
        capability_id="getNetworkWirelessSsids",
        parameters={"networkId": "N_123"},
    )

    assert isinstance(result, ExecuteError)
    assert result.error == "Invalid parameters for getNetworkWirelessSsids."
    assert result.recovery_suggestion == (
        "Verify the parameter values with semantic_search."
    )
    assert result.capability_id == "getNetworkWirelessSsids"


@pytest.mark.asyncio
async def test_execute_api_maps_401_authentication_failed(
    execute_tool,
    sdk_execute_client,
):
    sdk_execute_client.client.request.side_effect = MerakiApiError(
        status=401,
        message="raw sdk detail",
    )

    result = await execute_tool(
        capability_id="getNetworkWirelessSsids",
        parameters={"networkId": "N_123"},
    )

    assert isinstance(result, ExecuteError)
    assert result.error == "Authentication failed."
    assert result.recovery_suggestion == (
        "The provided API key is invalid or expired."
    )


@pytest.mark.asyncio
async def test_execute_api_maps_404_resource_not_found(
    execute_tool,
    sdk_execute_client,
):
    sdk_execute_client.client.request.side_effect = MerakiApiError(
        status=404,
        message="raw sdk detail",
    )

    result = await execute_tool(
        capability_id="getNetworkWirelessSsids",
        parameters={"networkId": "N_123"},
    )

    assert isinstance(result, ExecuteError)
    assert result.error == "Resource not found."
    assert result.recovery_suggestion == (
        "Verify the organization, network, or device identifier."
    )


@pytest.mark.asyncio
async def test_execute_api_maps_429_rate_limit(
    execute_tool,
    sdk_execute_client,
):
    sdk_execute_client.client.request.side_effect = MerakiApiError(
        status=429,
        message="raw sdk detail",
    )

    result = await execute_tool(
        capability_id="getNetworkWirelessSsids",
        parameters={"networkId": "N_123"},
    )

    assert isinstance(result, ExecuteError)
    assert result.error == "Meraki API rate limit reached."
    assert result.recovery_suggestion == "Try again shortly."


@pytest.mark.asyncio
async def test_execute_api_maps_500_unavailable(
    execute_tool,
    sdk_execute_client,
):
    sdk_execute_client.client.request.side_effect = MerakiApiError(
        status=500,
        message="raw sdk detail",
    )

    result = await execute_tool(
        capability_id="getNetworkWirelessSsids",
        parameters={"networkId": "N_123"},
    )

    assert isinstance(result, ExecuteError)
    assert result.error == "Meraki API is temporarily unavailable."
    assert result.recovery_suggestion == "Try again shortly."


@pytest.mark.asyncio
async def test_execute_api_maps_503_unavailable(
    execute_tool,
    sdk_execute_client,
):
    sdk_execute_client.client.request.side_effect = MerakiApiError(
        status=503,
        message="raw sdk detail",
    )

    result = await execute_tool(
        capability_id="getNetworkWirelessSsids",
        parameters={"networkId": "N_123"},
    )

    assert isinstance(result, ExecuteError)
    assert result.error == "Meraki API is temporarily unavailable."
    assert result.recovery_suggestion == "Try again shortly."


@pytest.mark.asyncio
async def test_execute_api_maps_unknown_status_to_unavailable(
    execute_tool,
    sdk_execute_client,
):
    sdk_execute_client.client.request.side_effect = MerakiApiError(
        status=418,
        message="raw sdk detail",
    )

    result = await execute_tool(
        capability_id="getNetworkWirelessSsids",
        parameters={"networkId": "N_123"},
    )

    assert isinstance(result, ExecuteError)
    assert result.error == "Meraki API is temporarily unavailable."
    assert result.recovery_suggestion == "Try again shortly."


@pytest.mark.asyncio
async def test_execute_api_returns_structured_request_validation_error(
    execute_tool,
    sdk_execute_client,
):
    sdk_execute_client.client.request.side_effect = RequestValidationError(
        error="Multi-page fetching is not supported.",
        recovery_suggestion=(
            "Remove the 'total_pages' parameter; one page is returned."
        ),
    )

    result = await execute_tool(
        capability_id="getNetworkWirelessSsids",
        parameters={"networkId": "N_123", "total_pages": "all"},
    )

    assert isinstance(result, ExecuteError)
    assert result.error == "Multi-page fetching is not supported."
    assert result.recovery_suggestion == (
        "Remove the 'total_pages' parameter; one page is returned."
    )
    assert result.capability_id == "getNetworkWirelessSsids"
    sdk_execute_client.client.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_execute_api_returns_generic_error_for_sdk_value_error(
    execute_tool,
    sdk_execute_client,
):
    sdk_execute_client.client.request.side_effect = ValueError(
        "total_pages is not supported",
    )

    result = await execute_tool(
        capability_id="getNetworkWirelessSsids",
        parameters={"networkId": "N_123", "total_pages": "all"},
    )

    assert isinstance(result, ExecuteError)
    assert result.error == "Meraki SDK error."
    assert "total_pages" not in result.recovery_suggestion
    sdk_execute_client.client.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_execute_api_returns_generic_error_for_unexpected_exception(
    execute_tool,
    sdk_execute_client,
):
    sdk_execute_client.client.request.side_effect = RuntimeError("boom")

    result = await execute_tool(
        capability_id="getNetworkWirelessSsids",
        parameters={"networkId": "N_123"},
    )

    assert isinstance(result, ExecuteError)
    assert result.error == "Meraki SDK error."
    assert result.recovery_suggestion == (
        "Retry later or choose another read capability."
    )
    sdk_execute_client.client.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_execute_api_does_not_log_sdk_value_error_details(
    execute_tool,
    caplog,
    sdk_execute_client,
):
    detail = "SECRET_NETWORK_ID_b8e3"
    sdk_execute_client.client.request.side_effect = ValueError(
        f"serialization detail for {detail}",
    )

    with caplog.at_level(
        logging.ERROR,
        logger="cisco_meraki_mcp.tools.execute_api",
    ):
        result = await execute_tool(
            capability_id="getNetworkWirelessSsids",
            parameters={"networkId": "N_123"},
        )

    assert isinstance(result, ExecuteError)
    assert result.error == "Meraki SDK error."
    assert detail not in result.recovery_suggestion
    assert detail not in "\n".join(
        record.getMessage() for record in caplog.records
    )
    sdk_execute_client.client.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_execute_api_does_not_log_caller_supplied_parameter_values(
    execute_tool,
    caplog,
    sdk_execute_client,
):
    sentinel = "SECRET_NETWORK_ID_b8e3"

    with caplog.at_level(
        logging.INFO,
        logger="cisco_meraki_mcp.tools.execute_api",
    ):
        await execute_tool(
            capability_id="getNetworkWirelessSsids",
            parameters={"networkId": sentinel},
        )

    blob = "\n".join(record.getMessage() for record in caplog.records)
    assert caplog.records
    assert sentinel not in blob
    assert "configured-key" not in blob
