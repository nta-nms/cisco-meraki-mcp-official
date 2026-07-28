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
"""In-memory vector store for semantic endpoint search."""

import logging
from typing import cast

import numpy as np
from fastembed import TextEmbedding

from cisco_meraki_mcp.models.endpoint import (
    EndpointMetadata,
    EndpointScope,
    VectorSearchHit,
)

logger = logging.getLogger(__name__)


class InMemoryVectorStore:
    """In-memory vector store using fastembed for embeddings.

    This is a simple implementation for the pre-MVP that doesn't require
    a database. All embeddings are stored in memory and similarity search
    is performed using numpy.

    The store is single-write/multi-read: populate it exactly once during
    lifespan startup, then serve reads without mutation.
    """

    def __init__(
        self,
        model_name: str = "sentence-transformers/all-MiniLM-L6-v2",
    ) -> None:
        """Initialize the vector store."""
        logger.info("Loading embedding model: %s", model_name)
        self.model: TextEmbedding | None = TextEmbedding(model_name=model_name)
        self.endpoints: list[EndpointMetadata] = []
        self._endpoints_by_id: dict[str, EndpointMetadata] = {}
        self._embeddings_normalized: np.ndarray | None = None
        self._populated = False
        logger.info("Embedding model loaded successfully")

    def _l2_normalize(self, vectors: np.ndarray) -> np.ndarray:
        """Normalize each vector to unit L2 length.

        Handles both the 1D query vector path (single embedding,
        `_encode_query`) and the 2D matrix path (one row per
        endpoint, `add_endpoints`).
        """
        if vectors.ndim == 1:
            return vectors / np.linalg.norm(vectors)

        norms = np.linalg.norm(vectors, axis=1, keepdims=True)
        return vectors / norms

    def _build_results(
        self,
        similarities: np.ndarray,
        top_k: int,
    ) -> list[VectorSearchHit]:
        """Build ranked search results from similarity scores."""
        k = min(top_k, len(self.endpoints))
        top_indices = np.argpartition(similarities, -k)[-k:]
        top_indices = top_indices[np.argsort(similarities[top_indices])[::-1]]
        return [
            VectorSearchHit(
                endpoint=self.endpoints[index],
                score=float(similarities[index]),
            )
            for index in top_indices
        ]

    def _encode_query(self, query: str) -> np.ndarray:
        """Encode and normalize a query for similarity search."""
        model = cast("TextEmbedding", self.model)
        query_embedding = np.asarray(next(iter(model.embed([query]))))
        return self._l2_normalize(query_embedding)

    def _encode_endpoints(
        self, endpoints: list[EndpointMetadata]
    ) -> np.ndarray:
        """Encode endpoint search text for indexing."""
        model = cast("TextEmbedding", self.model)
        texts = [endpoint.searchable_text for endpoint in endpoints]
        logger.info("Generating embeddings for %d endpoints...", len(texts))
        return np.array(list(model.embed(texts)))

    def _apply_scope_weights(
        self,
        similarities: np.ndarray,
        scope_weights: dict[EndpointScope, float] | None,
    ) -> None:
        """Apply scope weights to similarity scores in place."""
        if not scope_weights:
            return

        for index, endpoint in enumerate(self.endpoints):
            weight = scope_weights.get(endpoint.scope, 1.0)
            similarities[index] *= weight

    @staticmethod
    def _log_results(results: list[VectorSearchHit]) -> None:
        """Log search results for observability.

        The raw search query is intentionally not logged because it
        may contain caller-supplied identifiers; only the structured
        per-result lines are emitted.
        """
        for result in results:
            summary = result.endpoint.summary
            logger.info(
                "  %s [%s] (%.3f): %s",
                result.endpoint.operation_id,
                result.endpoint.scope.value,
                result.score,
                summary[:50] if summary else "",
            )

    def _ensure_writable(self) -> None:
        if self.model is None:
            raise RuntimeError("Vector store is closed")

        if self._populated:
            raise RuntimeError(
                "InMemoryVectorStore is single-write/multi-read; "
                "add_endpoints must run once during lifespan startup"
            )

    def add_endpoints(self, endpoints: list[EndpointMetadata]) -> None:
        """Add endpoints to the vector store."""
        if not endpoints:
            logger.warning("No endpoints provided to index")
            return

        self._ensure_writable()
        embeddings = self._l2_normalize(self._encode_endpoints(endpoints))
        self.endpoints = endpoints
        self._endpoints_by_id = {ep.operation_id: ep for ep in endpoints}
        self._embeddings_normalized = embeddings
        self._populated = True
        logger.info("Indexed %d endpoints", len(self.endpoints))

    def close(self) -> None:
        """Release indexed data and the embedding model reference."""
        self.endpoints = []
        self._endpoints_by_id = {}
        self._embeddings_normalized = None
        self.model = None

    def endpoint_for(self, operation_id: str) -> EndpointMetadata | None:
        """Return the indexed endpoint for `operation_id`, if any."""
        return self._endpoints_by_id.get(operation_id)

    def search(
        self,
        query: str,
        top_k: int = 5,
        scope_weights: dict[EndpointScope, float] | None = None,
    ) -> list[VectorSearchHit]:
        """Search for endpoints matching the query.

        Args:
            query: Natural language query.
            top_k: Number of results to return.
            scope_weights: Optional dict mapping EndpointScope to weight
                multipliers. Applied to similarity scores before ranking.

        Returns:
            List of VectorSearchHit with endpoints and weighted scores.
        """
        if self._embeddings_normalized is None or len(self.endpoints) == 0:
            logger.warning("Vector store is empty, returning no results")
            return []

        query_norm = self._encode_query(query)
        similarities = np.dot(self._embeddings_normalized, query_norm)
        self._apply_scope_weights(similarities, scope_weights)
        results = self._build_results(similarities, top_k)
        self._log_results(results)

        return results

    @property
    def embeddings(self) -> np.ndarray | None:
        """Normalized embeddings matrix, or None when not indexed."""
        return self._embeddings_normalized

    @property
    def endpoint_count(self) -> int:
        """Count of indexed endpoints."""
        return len(self.endpoints)
