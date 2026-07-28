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

from cisco_meraki_mcp.contracts.common import RiskTier
from cisco_meraki_mcp.contracts.search import RequiredParameter, SearchOutput
from cisco_meraki_mcp.tools.semantic_search import SemanticSearchFactory


@pytest.mark.asyncio
async def test_semantic_search_returns_search_output(search_tool):
    output = await search_tool("wireless SSIDs", top_k=3)

    assert isinstance(output, SearchOutput)
    assert len(output.results) == 3


@pytest.mark.asyncio
async def test_semantic_search_organization_devices_returns_known_fields(
    search_tool,
):
    output = await search_tool("organization devices", top_k=3)

    result = next(
        r
        for r in output.results
        if r.capability_id == "getOrganizationDevices"
    )

    assert result.intent == "Get organization devices"
    assert result.product_scope == "common"
    assert result.risk_tier == RiskTier.SAFE
    assert result.tags == []
    assert len(result.required_parameters) == 1
    assert isinstance(result.required_parameters[0], RequiredParameter)
    assert result.required_parameters[0].name == "organizationId"


@pytest.mark.asyncio
async def test_semantic_search_top_k_at_upper_bound(search_tool):
    output = await search_tool("test", top_k=20)

    assert isinstance(output, SearchOutput)


def test_semantic_search_notification_summary():
    summary = SemanticSearchFactory.notification_summary(
        {"top_k": 3},
        SearchOutput.model_construct(results=[object()] * 3),
    )

    assert summary == {"top_k": 3, "result_count": 3}
