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
from fastmcp import Client

from cisco_meraki_mcp.main import create_app


@pytest.fixture
async def mcp_client(mock_text_embedding, sample_openapi_spec):
    app = create_app(spec_path=sample_openapi_spec)
    async with Client(app) as client:
        yield client


@pytest.mark.asyncio
async def test_list_tools_returns_production_tools(mcp_client):
    tools = await mcp_client.list_tools()

    tool_names = [t.name for t in tools]
    assert "semantic_search" in tool_names
    assert "execute_api" in tool_names


@pytest.mark.asyncio
async def test_semantic_search_advertises_tool_annotations(mcp_client):
    tools = await mcp_client.list_tools()

    annotations = next(
        t for t in tools if t.name == "semantic_search"
    ).annotations

    assert annotations is not None
    assert annotations.readOnlyHint is True
    assert annotations.idempotentHint is True
    assert annotations.openWorldHint is False


@pytest.mark.asyncio
async def test_execute_api_advertises_tool_annotations(mcp_client):
    tools = await mcp_client.list_tools()

    annotations = next(t for t in tools if t.name == "execute_api").annotations

    assert annotations is not None
    assert annotations.readOnlyHint is True
    assert annotations.idempotentHint is False
    assert annotations.openWorldHint is True


@pytest.mark.asyncio
async def test_list_resources_returns_info(mcp_client):
    resources = await mcp_client.list_resources()

    uris = [str(r.uri) for r in resources]
    assert any("info" in uri for uri in uris)
