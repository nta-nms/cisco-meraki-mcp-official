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
from pydantic import ValidationError

from cisco_meraki_mcp.contracts.common import RiskTier
from cisco_meraki_mcp.contracts.search import (
    RequiredParameter,
    SearchInput,
    SearchOutput,
    SearchResult,
)


def test_search_input_requires_query():
    with pytest.raises(ValidationError):
        SearchInput(top_k=5)


def test_search_input_top_k_lower_bound():
    with pytest.raises(ValidationError):
        SearchInput(query="q", top_k=0)


def test_search_input_top_k_upper_bound_accepts_twenty():
    payload = SearchInput(query="q", top_k=20)

    assert payload.top_k == 20


def test_search_input_top_k_upper_bound_rejects_above_twenty():
    with pytest.raises(ValidationError):
        SearchInput(query="q", top_k=21)


def test_required_parameter_rejects_extra_fields():
    with pytest.raises(ValidationError):
        RequiredParameter(
            name="x",
            location="path",
            required=True,
            type="string",
            unexpected="boom",
        )


def test_required_parameter_serializes_with_type_key():
    param = RequiredParameter(
        name="organizationId",
        location="path",
        required=True,
        type="string",
        description="Org",
    )

    assert param.model_dump()["type"] == "string"


def test_search_result_rejects_extra_fields():
    with pytest.raises(ValidationError):
        SearchResult(
            capability_id="getNetwork",
            intent="Get network info",
            product_scope="common",
            risk_tier=RiskTier.SAFE,
            tags=["networks"],
            required_parameters=[],
            unexpected="boom",
        )


def test_search_result_is_frozen():
    result = SearchResult(
        capability_id="getNetwork",
        intent="Get network info",
        product_scope="common",
        risk_tier=RiskTier.SAFE,
        tags=["networks"],
        required_parameters=[],
    )

    with pytest.raises(ValidationError):
        result.capability_id = "other"


def test_search_output_defaults_to_empty_list():
    output = SearchOutput()

    assert output.results == []


def test_search_output_validates_with_results():
    output = SearchOutput(
        results=[
            SearchResult(
                capability_id="x",
                intent="Get network info",
                product_scope="common",
                risk_tier=RiskTier.SAFE,
                tags=["networks"],
                required_parameters=[],
            ),
        ],
    )

    assert len(output.results) == 1
    assert output.results[0].capability_id == "x"
