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
from cisco_meraki_mcp.contracts.search import RequiredParameter
from cisco_meraki_mcp.factories.search_result import build_search_result
from cisco_meraki_mcp.models.endpoint import (
    EndpointMetadata,
    EndpointParameter,
    EndpointScope,
)


class EndpointRiskClassifier:
    @staticmethod
    def classify(endpoint: EndpointMetadata) -> RiskTier:
        if endpoint.operation_id == "getNetworkWirelessSsids":
            return RiskTier.ELEVATED

        return RiskTier.SAFE


@pytest.fixture
def wireless_endpoint() -> EndpointMetadata:
    return EndpointMetadata(
        operation_id="getNetworkWirelessSsids",
        method="GET",
        path="/networks/{networkId}/wireless/ssids",
        summary="List SSIDs",
        description="List the wireless SSIDs in a network",
        tags=["wireless", "configure"],
        parameters=[
            EndpointParameter(
                name="networkId",
                location="path",
                required=True,
                param_type="string",
                description="Network ID",
            ),
            EndpointParameter(
                name="perPage",
                location="query",
                required=False,
                param_type="integer",
                description="Page size",
            ),
        ],
        scope=EndpointScope.NETWORK,
    )


@pytest.fixture
def risk_classifier():
    return EndpointRiskClassifier()


def test_full_mapping_uses_injected_classifiers(
    risk_classifier,
    product_classifier,
    wireless_endpoint,
):
    result = build_search_result(
        wireless_endpoint,
        risk_classifier=risk_classifier,
        product_classifier=product_classifier,
    )

    assert result.capability_id == "getNetworkWirelessSsids"
    assert result.intent == "List SSIDs"
    assert result.product_scope == "wireless"
    assert result.risk_tier == RiskTier.ELEVATED
    assert result.tags == ["wireless", "configure"]


def test_required_parameters_filtered_to_required_only(
    risk_classifier,
    product_classifier,
    wireless_endpoint,
):
    result = build_search_result(
        wireless_endpoint,
        risk_classifier=risk_classifier,
        product_classifier=product_classifier,
    )

    assert len(result.required_parameters) == 1
    assert isinstance(result.required_parameters[0], RequiredParameter)
    assert result.required_parameters[0].name == "networkId"
    assert result.required_parameters[0].location == "path"
    assert result.required_parameters[0].required is True
    assert result.required_parameters[0].type == "string"


def test_intent_falls_back_to_description(
    risk_classifier,
    product_classifier,
    endpoint_factory,
):
    endpoint = endpoint_factory(
        operation_id="getThing",
        path="/things",
        summary="",
        description="A thing description",
    )

    result = build_search_result(
        endpoint,
        risk_classifier=risk_classifier,
        product_classifier=product_classifier,
    )

    assert result.intent == "A thing description"


def test_intent_falls_back_to_operation_id(
    risk_classifier,
    product_classifier,
    endpoint_factory,
):
    endpoint = endpoint_factory(
        operation_id="getThing",
        path="/things",
    )

    result = build_search_result(
        endpoint,
        risk_classifier=risk_classifier,
        product_classifier=product_classifier,
    )

    assert result.intent == "getThing"
