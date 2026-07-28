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
from contextlib import asynccontextmanager

import pytest
from fastmcp import Client, FastMCP

from cisco_meraki_mcp.tools.semantic_search import SemanticSearchFactory


@pytest.fixture
def mcp_app(search_factory: SemanticSearchFactory, mcp_context) -> FastMCP:
    @asynccontextmanager
    async def lifespan(server: FastMCP):
        yield mcp_context.lifespan_context

    app = FastMCP("network-platform-cloud-mcp-test", lifespan=lifespan)
    app.tool(search_factory.tool(), name=search_factory.tool_name)
    return app


@pytest.mark.asyncio
async def test_semantic_search_input_schema_published(mcp_app: FastMCP):
    async with Client(mcp_app) as client:
        tools = await client.list_tools()

    by_name = {tool.name: tool for tool in tools}
    schema = by_name["semantic_search"].inputSchema
    properties = schema["properties"]

    assert "query" in properties
    assert "top_k" in properties
    assert "query" in schema.get("required", [])
    assert properties["top_k"].get("default") == 5
    assert properties["top_k"].get("type") == "integer"


@pytest.mark.asyncio
async def test_semantic_search_top_k_schema_advertises_bounds(
    mcp_app: FastMCP,
):
    async with Client(mcp_app) as client:
        tools = await client.list_tools()

    schema = next(
        tool for tool in tools if tool.name == "semantic_search"
    ).inputSchema
    top_k = schema["properties"]["top_k"]

    assert top_k.get("minimum") == 1
    assert top_k.get("maximum") == 20


@pytest.mark.asyncio
async def test_semantic_search_output_schema_exposes_results(
    mcp_app: FastMCP,
):
    async with Client(mcp_app) as client:
        tools = await client.list_tools()

    tool = next(
        (tool for tool in tools if tool.name == "semantic_search"),
        None,
    )
    assert tool is not None, "semantic_search tool must be registered"
    schema = tool.outputSchema

    assert schema is not None
    assert "results" in schema.get("properties", {})


@pytest.mark.asyncio
async def test_semantic_search_call_returns_expected_shape(mcp_app: FastMCP):
    async with Client(mcp_app) as client:
        result = await client.call_tool(
            "semantic_search",
            {"query": "wireless ssids", "top_k": 2},
        )

    payload = result.structured_content

    assert payload is not None
    assert isinstance(payload["results"], list)
    assert len(payload["results"]) == 2
    first = payload["results"][0]
    assert "capability_id" in first
    assert "risk_tier" in first
