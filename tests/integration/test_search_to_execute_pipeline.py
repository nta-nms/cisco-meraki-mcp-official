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
from types import SimpleNamespace

import pytest

from cisco_meraki_mcp.contracts.execute import ExecuteData, ExecuteReadOutput
from cisco_meraki_mcp.index_state import IndexState
from cisco_meraki_mcp.providers.openapi import load_meraki_endpoints
from cisco_meraki_mcp.providers.vector_store import InMemoryVectorStore


@pytest.mark.asyncio
async def test_capability_id_from_search_is_consumable_by_execute(
    search_tool,
    execute_tool,
    sdk_execute_client,
):
    output = await search_tool("wireless SSIDs for a network", top_k=5)
    op_id = "getNetworkWirelessSsids"

    assert any(r.capability_id == op_id for r in output.results)

    result = await execute_tool(
        capability_id=op_id,
        parameters={"networkId": "N_999"},
    )

    assert isinstance(result, ExecuteReadOutput)
    assert result.capability_id == op_id
    assert isinstance(result.data, ExecuteData)


@pytest.mark.asyncio
async def test_deprecated_endpoint_never_returned_by_search(
    sample_openapi_spec: Path,
    mock_text_embedding,
    search_factory,
):
    endpoints = load_meraki_endpoints(sample_openapi_spec)
    store = InMemoryVectorStore(model_name="test-model")
    store.add_endpoints(endpoints)

    state = IndexState()
    state.mark_ready()
    ctx = SimpleNamespace(
        lifespan_context={"index_state": state, "store": store}
    )

    tool = search_factory.tool()
    output = await tool("deprecated endpoint", ctx=ctx, top_k=5)

    assert all(
        r.capability_id != "getDeprecatedEndpoint" for r in output.results
    )
