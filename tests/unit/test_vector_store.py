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
import logging

import pytest

from cisco_meraki_mcp.models.endpoint import EndpointMetadata, EndpointScope
from cisco_meraki_mcp.providers.vector_store import InMemoryVectorStore


def test_vector_store_initialization(mock_text_embedding):
    store = InMemoryVectorStore(model_name="test-model")

    assert store.endpoints == []
    assert store.embeddings is None
    assert store.endpoint_count == 0


def test_vector_store_initialization_uses_default_model(mocker):
    text_embedding = mocker.patch(
        "cisco_meraki_mcp.providers.vector_store.TextEmbedding"
    )

    InMemoryVectorStore()

    text_embedding.assert_called_once_with(
        model_name="sentence-transformers/all-MiniLM-L6-v2"
    )


def test_vector_store_add_endpoints(
    mock_text_embedding,
    sample_endpoints: list[EndpointMetadata],
):
    store = InMemoryVectorStore(model_name="test-model")
    store.add_endpoints(sample_endpoints)

    assert store.endpoint_count == len(sample_endpoints)
    assert store.embeddings is not None
    assert store.embeddings.shape[0] == len(sample_endpoints)


def test_vector_store_add_endpoints_rejects_second_write(
    vector_store: InMemoryVectorStore,
    sample_endpoints: list[EndpointMetadata],
):
    with pytest.raises(RuntimeError, match="single-write"):
        vector_store.add_endpoints(sample_endpoints)


def test_vector_store_add_empty_endpoints(mock_text_embedding):
    store = InMemoryVectorStore(model_name="test-model")
    store.add_endpoints([])

    assert store.endpoint_count == 0
    assert store.embeddings is None


def test_vector_store_close_releases_index_and_model(
    vector_store: InMemoryVectorStore,
):
    vector_store.close()

    assert vector_store.endpoints == []
    assert vector_store.endpoint_count == 0
    assert vector_store.embeddings is None
    assert vector_store.endpoint_for("getOrganizationDevices") is None
    assert vector_store.model is None


def test_vector_store_add_endpoints_raises_after_close(
    mock_text_embedding,
    sample_endpoints: list[EndpointMetadata],
):
    store = InMemoryVectorStore(model_name="test-model")
    store.close()

    with pytest.raises(RuntimeError, match="closed"):
        store.add_endpoints(sample_endpoints)

    assert store.endpoint_count == 0
    assert store.embeddings is None
    assert store.endpoint_for("getOrganizationDevices") is None


def test_vector_store_search_returns_empty_after_close(
    vector_store: InMemoryVectorStore,
):
    vector_store.close()

    assert vector_store.search("organization devices") == []


def test_vector_store_search_returns_results(
    vector_store: InMemoryVectorStore,
):
    results = vector_store.search("get SSIDs for a network", top_k=3)

    assert len(results) == 3
    assert all(hasattr(r, "endpoint") for r in results)
    assert all(hasattr(r, "score") for r in results)


def test_vector_store_search_scores_in_range(
    vector_store: InMemoryVectorStore,
):
    results = vector_store.search("wireless SSIDs", top_k=3)

    for result in results:
        assert -1.0 <= result.score <= 1.0


def test_vector_store_search_finds_relevant_endpoint(
    vector_store: InMemoryVectorStore,
):
    # Search for all endpoints to verify the target is indexed
    # (mock embeddings don't guarantee semantic ranking)
    results = vector_store.search("wireless SSID network", top_k=10)

    operation_ids = [r.endpoint.operation_id for r in results]
    assert "getNetworkWirelessSsids" in operation_ids


def test_vector_store_search_devices_query(
    vector_store: InMemoryVectorStore,
):
    # Search for all endpoints to verify the target is indexed
    # (mock embeddings don't guarantee semantic ranking)
    results = vector_store.search("list devices in organization", top_k=10)

    operation_ids = [r.endpoint.operation_id for r in results]
    assert "getOrganizationDevices" in operation_ids


def test_vector_store_search_empty_store(mock_text_embedding):
    store = InMemoryVectorStore(model_name="test-model")
    results = store.search("anything", top_k=5)

    assert results == []


def test_vector_store_search_top_k_limit(
    vector_store: InMemoryVectorStore,
):
    results = vector_store.search("network", top_k=2)
    assert len(results) == 2

    results = vector_store.search("network", top_k=1)
    assert len(results) == 1


def test_vector_store_search_top_k_exceeds_endpoints(
    vector_store: InMemoryVectorStore,
):
    results = vector_store.search("network", top_k=100)

    assert len(results) == vector_store.endpoint_count


def test_vector_store_search_with_scope_weights(
    vector_store: InMemoryVectorStore,
):
    scope_weights = {
        EndpointScope.ORGANIZATION: 2.0,
        EndpointScope.NETWORK: 1.0,
        EndpointScope.DEVICE: 1.0,
        EndpointScope.ADMINISTERED: 1.0,
        EndpointScope.GLOBAL: 1.0,
    }
    results = vector_store.search(
        "list devices",
        top_k=5,
        scope_weights=scope_weights,
    )
    assert len(results) >= 1
    assert len(results) <= 5

    org_results = [
        r for r in results if r.endpoint.scope == EndpointScope.ORGANIZATION
    ]
    assert len(org_results) > 0


def test_vector_store_endpoint_for(
    vector_store: InMemoryVectorStore,
):
    endpoint = vector_store.endpoint_for("getOrganizationDevices")
    assert endpoint is not None
    assert endpoint.operation_id == "getOrganizationDevices"
    assert endpoint.scope == EndpointScope.ORGANIZATION


def test_vector_store_endpoint_for_not_found(
    vector_store: InMemoryVectorStore,
):
    endpoint = vector_store.endpoint_for("nonexistent")
    assert endpoint is None


def test_vector_store_search_does_not_log_raw_query_at_info(
    vector_store: InMemoryVectorStore,
    caplog,
):
    canary_query = "QUERY_CANARY_zx9q4t_sensitive_text"

    with caplog.at_level(
        logging.INFO,
        logger="cisco_meraki_mcp.providers.vector_store",
    ):
        vector_store.search(canary_query, top_k=2)

    blob = "\n".join(record.getMessage() for record in caplog.records)
    assert canary_query not in blob
    assert "Query:" not in blob
