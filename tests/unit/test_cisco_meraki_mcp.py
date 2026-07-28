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
import pytest
from fastmcp import FastMCP

from cisco_meraki_mcp.cisco_meraki_mcp import CiscoMerakiMCP
from cisco_meraki_mcp.index_state import IndexState


@pytest.fixture
def core_service():
    service = CiscoMerakiMCP("test")
    service.register_core_capabilities(IndexState())
    return service


def test_cisco_meraki_mcp_subclasses_fastmcp():
    assert issubclass(CiscoMerakiMCP, FastMCP)


def test_shutdown_is_noop():
    assert CiscoMerakiMCP("test").shutdown() is None


def test_instrument_tool_returns_callable_unchanged():
    async def fn():
        return "ok"

    wrapped = CiscoMerakiMCP("test").instrument_tool(
        fn,
        tool_name="sample_tool",
        span_attrs=[],
    )

    assert wrapped is fn


def test_instrument_api_request_returns_callable_unchanged():
    async def fn():
        return "ok"

    wrapped = CiscoMerakiMCP("test").instrument_api_request(fn)

    assert wrapped is fn


@pytest.mark.asyncio
async def test_register_core_capabilities_exposes_info_resource(core_service):
    resource_uris = [str(r.uri) for r in await core_service.list_resources()]

    assert "info://service" in resource_uris


@pytest.mark.asyncio
async def test_register_core_capabilities_registers_vector_tools(core_service):
    tool_names = {tool.name for tool in await core_service.list_tools()}

    assert {"semantic_search", "execute_api"} <= tool_names


@pytest.mark.asyncio
async def test_base_http_app_omits_production_probes(
    core_service, asgi_client
):
    asgi_app = core_service.http_app()

    async with asgi_client(asgi_app) as client:
        response = await client.get("/health")

    assert response.status_code == 404
