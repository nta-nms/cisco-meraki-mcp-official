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
import json

import pytest
from fastmcp import Client, FastMCP

from cisco_meraki_mcp.tools.execute_api import ExecuteApiFactory


@pytest.fixture
def mcp_app(mcp_app_factory, execute_factory: ExecuteApiFactory) -> FastMCP:
    return mcp_app_factory(execute_factory.tool(), execute_factory.tool_name)


@pytest.mark.asyncio
async def test_execute_api_input_schema_includes_call_inputs(
    mcp_app: FastMCP,
):
    async with Client(mcp_app) as client:
        tools = await client.list_tools()

    by_name = {tool.name: tool for tool in tools}
    schema = by_name["execute_api"].inputSchema
    properties = schema["properties"]
    required = set(schema.get("required", []))

    assert "capability_id" in properties
    assert "api_key" not in properties
    assert "parameters" in properties
    assert required == {"capability_id"}


@pytest.mark.asyncio
async def test_execute_api_output_schema_exposes_discriminator_tags(
    mcp_app: FastMCP,
):
    async with Client(mcp_app) as client:
        tools = await client.list_tools()

    schema = next(
        tool for tool in tools if tool.name == "execute_api"
    ).outputSchema
    blob = json.dumps(schema)

    assert '"const": "success"' in blob
    assert '"const": "error"' in blob


@pytest.mark.asyncio
async def test_execute_api_parameters_schema_constrains_value_types(
    mcp_app: FastMCP,
):
    async with Client(mcp_app) as client:
        tools = await client.list_tools()

    schema = next(
        tool for tool in tools if tool.name == "execute_api"
    ).inputSchema
    parameters = schema["properties"]["parameters"]

    blob = json.dumps(parameters)
    assert '"additionalProperties": true' not in blob
