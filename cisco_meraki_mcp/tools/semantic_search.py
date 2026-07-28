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
"""Semantic search tool factory."""

from collections.abc import Awaitable, Callable, Mapping
from typing import Annotated

from fastmcp import Context
from mcp.types import ToolAnnotations
from pydantic import Field

from cisco_meraki_mcp.classifiers.product import ProductClassifier
from cisco_meraki_mcp.classifiers.risk import RiskClassifier
from cisco_meraki_mcp.config.settings import get_settings
from cisco_meraki_mcp.contracts.search import SearchOutput
from cisco_meraki_mcp.factories.search_result import build_search_result
from cisco_meraki_mcp.models.endpoint import EndpointScope
from cisco_meraki_mcp.tools.logging import log_tool_invocation
from cisco_meraki_mcp.tools.tool_factory import ToolFactory

TOOL_NAME = "semantic_search"


class SemanticSearchFactory(ToolFactory):
    """Build the `semantic_search` MCP tool with injected deps."""

    tool_name = TOOL_NAME

    def __init__(
        self,
        *,
        product_classifier: ProductClassifier,
        risk_classifier: RiskClassifier,
    ) -> None:
        self._product_classifier = product_classifier
        self._risk_classifier = risk_classifier

    @staticmethod
    def build_scope_weights() -> dict[EndpointScope, float]:
        """Build scope weights dict from settings."""
        settings = get_settings()
        return {
            EndpointScope.ORGANIZATION: settings.scope_weight_organization,
            EndpointScope.NETWORK: settings.scope_weight_network,
            EndpointScope.DEVICE: settings.scope_weight_device,
            EndpointScope.ADMINISTERED: settings.scope_weight_administered,
            EndpointScope.GLOBAL: settings.scope_weight_global,
        }

    def tool(self) -> Callable[..., Awaitable[SearchOutput]]:
        return self.semantic_search

    @staticmethod
    def annotations() -> ToolAnnotations:
        """Behavior hints for the `semantic_search` tool listing."""
        return ToolAnnotations(
            readOnlyHint=True,
            idempotentHint=True,
            openWorldHint=False,
        )

    @staticmethod
    def notification_summary(
        kwargs: Mapping[str, object],
        result: object,
    ) -> dict[str, object]:
        return {
            "top_k": kwargs.get("top_k", 5),
            "result_count": len(result.results)
            if isinstance(result, SearchOutput)
            else 0,
        }

    @log_tool_invocation(
        TOOL_NAME,
        ["query", "top_k"],
        notification_summary,
    )
    async def semantic_search(
        self,
        query: str,
        ctx: Context,
        top_k: Annotated[int, Field(ge=1, le=20)] = 5,
    ) -> SearchOutput:
        """Search the Meraki capability catalog for relevant GET endpoints.

        Describe the data or action you need in natural language. Results
        are ranked GET capabilities, weighted so organization-scoped
        capabilities surface first.

        Good queries:
        - "devices offline in my org"
        - "switch port status history"
        - "recent config changes"

        Bad queries (avoid these):
        - "networks" (too vague)
        - "meraki stuff" (not actionable)

        Do NOT call with vague or single-word queries.

        Follow up with execute_api using the capability_id from these
        results.

        Args:
            query: Natural language description of what you want to do.
            top_k: Number of results to return (default: 5, range: 1-20).

        Returns:
            `SearchOutput` with ranked, typed capability results.
        """
        store = self.require_ready_store(ctx)
        hits = store.search(
            query,
            top_k=top_k,
            scope_weights=self.build_scope_weights(),
        )

        return SearchOutput(
            results=[
                build_search_result(
                    hit.endpoint,
                    risk_classifier=self._risk_classifier,
                    product_classifier=self._product_classifier,
                )
                for hit in hits
            ],
        )
