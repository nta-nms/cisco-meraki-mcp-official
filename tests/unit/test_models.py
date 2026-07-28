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
from cisco_meraki_mcp.models.endpoint import EndpointScope, VectorSearchHit


def test_endpoint_scope_values():
    assert EndpointScope.ORGANIZATION.value == "organization"
    assert EndpointScope.NETWORK.value == "network"
    assert EndpointScope.DEVICE.value == "device"
    assert EndpointScope.ADMINISTERED.value == "administered"
    assert EndpointScope.GLOBAL.value == "global"


def test_endpoint_metadata_searchable_text(endpoint_factory):
    endpoint = endpoint_factory(
        operation_id="getNetworkWirelessSsids",
        path="/networks/{networkId}/wireless/ssids",
        summary="List SSIDs",
        description="List the MR SSIDs in a network",
        tags=["wireless", "ssids"],
        scope=EndpointScope.NETWORK,
    )

    text = endpoint.searchable_text

    assert "getNetworkWirelessSsids" in text
    assert "List SSIDs" in text
    assert "List the MR SSIDs in a network" in text
    assert "wireless" in text
    assert "ssids" in text
    assert "/networks/{networkId}/wireless/ssids" in text


def test_endpoint_metadata_searchable_text_empty_fields(endpoint_factory):
    endpoint = endpoint_factory(
        operation_id="getTest",
        path="/test",
    )

    text = endpoint.searchable_text

    assert "getTest" in text
    assert "/test" in text
    assert "  " not in text


def test_endpoint_metadata_required_scopes_default_empty(endpoint_factory):
    endpoint = endpoint_factory(
        operation_id="getThing",
        path="/things",
    )

    assert endpoint.required_scopes == frozenset()
    assert isinstance(endpoint.required_scopes, frozenset)


def test_endpoint_metadata_required_scopes_stored_as_frozenset(
    endpoint_factory,
):
    endpoint = endpoint_factory(
        operation_id="getThing",
        path="/things",
        required_scopes=frozenset({"camera:config:read"}),
    )

    assert endpoint.required_scopes == frozenset({"camera:config:read"})
    assert isinstance(endpoint.required_scopes, frozenset)


def test_endpoint_metadata_required_scopes_excluded_from_searchable_text(
    endpoint_factory,
):
    endpoint = endpoint_factory(
        operation_id="getThing",
        path="/things",
        summary="A thing",
        required_scopes=frozenset({"camera:config:read"}),
    )

    text = endpoint.searchable_text

    assert "camera:config:read" not in text


def test_vector_search_hit_score_validation(endpoint_factory):
    endpoint = endpoint_factory(
        operation_id="getTest",
        path="/test",
    )

    result = VectorSearchHit(endpoint=endpoint, score=0.0)
    assert result.score == 0.0

    result = VectorSearchHit(endpoint=endpoint, score=1.0)
    assert result.score == 1.0

    result = VectorSearchHit(endpoint=endpoint, score=0.5)
    assert result.score == 0.5
