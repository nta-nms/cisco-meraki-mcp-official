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
"""CiscoMerakiMCP — FastMCP server for the Meraki Dashboard API."""

import logging
from collections.abc import Awaitable, Callable

from fastmcp import FastMCP

from cisco_meraki_mcp.classifiers.product import TagBasedProductClassifier
from cisco_meraki_mcp.classifiers.risk import HttpMethodRiskClassifier
from cisco_meraki_mcp.index_state import IndexState
from cisco_meraki_mcp.providers.meraki_credentials import (
    meraki_api_key_for_transport,
)
from cisco_meraki_mcp.resources import service_info
from cisco_meraki_mcp.tools.execute_api import ExecuteApiFactory
from cisco_meraki_mcp.tools.semantic_search import SemanticSearchFactory

logger = logging.getLogger(__name__)


class CiscoMerakiMCP(FastMCP):
    """FastMCP server for discovering and executing Meraki API endpoints.

    Registers a service-info resource and the ``semantic_search`` /
    ``execute_api`` tools via :meth:`register_core_capabilities`.
    """

    def register_core_capabilities(
        self,
        state: IndexState,
        *,
        runtime_transport: str | None = None,
    ) -> None:
        """Register the service-info resource and the search / execute tools.

        ``state`` carries the vector-index build status for readiness
        reporting.
        """
        self._register_info_resource()
        self._register_vector_tools(runtime_transport=runtime_transport)

    def shutdown(self) -> None:
        """Release resources held by the service.

        No-op by default; overridable for cleanup at process exit.
        """

    def instrument_tool(
        self,
        fn: Callable[..., Awaitable[object]],
        *,
        tool_name: str,
        span_attrs: list[str] | None = None,
    ) -> Callable[..., Awaitable[object]]:
        """Return *fn* unchanged.

        Overridable hook for wrapping a tool coroutine with observability
        before registration.
        """
        return fn

    def instrument_api_request(
        self,
        fn: Callable[..., Awaitable[object]],
    ) -> Callable[..., Awaitable[object]]:
        """Return *fn* unchanged.

        Overridable hook for wrapping an API request coroutine with
        observability before execution.
        """
        return fn

    def _register_info_resource(self) -> None:
        @self.resource(uri="info://service")
        async def info() -> str:
            """Service information resource, returned as JSON."""
            return service_info()

    def _register_vector_tools(
        self,
        *,
        runtime_transport: str | None = None,
    ) -> None:
        """Register the semantic-search and execute-API tools.

        Registered eagerly so ``tools/list`` is complete at bind time; each
        tool returns a structured "not ready" error until the vector index
        finishes building.
        """
        risk_classifier = HttpMethodRiskClassifier()
        product_classifier = TagBasedProductClassifier()

        search_factory = SemanticSearchFactory(
            risk_classifier=risk_classifier,
            product_classifier=product_classifier,
        )
        execute_factory = ExecuteApiFactory(
            product_classifier=product_classifier,
            credential_provider=lambda: meraki_api_key_for_transport(
                transport=runtime_transport,
            ),
            instrument_api_request=self.instrument_api_request,
        )

        self.tool(
            self.instrument_tool(
                search_factory.tool(),
                tool_name=search_factory.tool_name,
                span_attrs=search_factory.span_attrs,
            ),
            name=search_factory.tool_name,
            annotations=search_factory.annotations(),
        )
        self.tool(
            self.instrument_tool(
                execute_factory.tool(),
                tool_name=execute_factory.tool_name,
                span_attrs=execute_factory.span_attrs,
            ),
            name=execute_factory.tool_name,
            annotations=execute_factory.annotations(),
        )
        logger.info("Registered semantic search tools")
