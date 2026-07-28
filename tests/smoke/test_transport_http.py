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
from pathlib import Path

import pytest
from fastmcp import Client
from fastmcp.client.transports.http import StreamableHttpTransport
from fastmcp.utilities.tests import run_server_async

from cisco_meraki_mcp.main import create_app


@pytest.fixture
async def http_client(mock_text_embedding, sdk_execute_client):
    fixtures = Path(__file__).resolve().parent.parent / "fixtures"
    spec_path = fixtures / "minimal_meraki.json"

    app = create_app(spec_path=spec_path)
    async with run_server_async(app) as url:
        transport = StreamableHttpTransport(url)
        async with Client(transport=transport) as client:
            yield client


@pytest.mark.slow
@pytest.mark.asyncio
async def test_initialize_session_over_http(
    http_client: Client[StreamableHttpTransport],
):
    init_result = await http_client.initialize()
    assert init_result is not None
    pong = await http_client.ping()
    assert pong is not None


@pytest.mark.slow
@pytest.mark.asyncio
async def test_list_tools_over_http(
    http_client: Client[StreamableHttpTransport],
):
    tools = await http_client.list_tools()

    assert len(tools) >= 1
    tool_names = [t.name for t in tools]
    assert "semantic_search" in tool_names
    assert "execute_api" in tool_names


@pytest.mark.slow
@pytest.mark.asyncio
async def test_list_resources_over_http(
    http_client: Client[StreamableHttpTransport],
):
    resources = await http_client.list_resources()
    uris = [str(r.uri) for r in resources]
    assert any("info" in u for u in uris)


@pytest.mark.slow
@pytest.mark.asyncio
async def test_semantic_search_over_http(
    http_client: Client[StreamableHttpTransport],
):
    result = await http_client.call_tool(
        "semantic_search",
        {"query": "list wireless SSIDs", "top_k": 2},
    )

    text = result.content[0].text
    assert "capability_id" in text


@pytest.mark.slow
@pytest.mark.asyncio
async def test_call_tool_over_http(
    http_client: Client[StreamableHttpTransport],
):
    result = await http_client.call_tool(
        "execute_api",
        {
            "capability_id": "getNetworkWirelessSsids",
            "parameters": {"networkId": "N_123"},
        },
    )

    text = result.content[0].text
    assert "getNetworkWirelessSsids" in text
