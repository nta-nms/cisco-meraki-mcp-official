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
"""Abstract base class for MCP tool factories with shared readiness gating."""

from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable
from typing import ClassVar

from fastmcp import Context
from fastmcp.exceptions import ToolError

from cisco_meraki_mcp.index_state import IndexState, IndexStatus
from cisco_meraki_mcp.providers.vector_store import InMemoryVectorStore


class ToolFactory(ABC):
    """Bind injected dependencies to a tool coroutine."""

    tool_name: ClassVar[str]
    span_attrs: ClassVar[list[str]] = []

    @abstractmethod
    def tool(self) -> Callable[..., Awaitable[object]]:
        """Return the bound FastMCP tool coroutine."""

    def require_ready_store(self, ctx: Context) -> InMemoryVectorStore:
        store = ctx.lifespan_context.get("store")

        if isinstance(store, InMemoryVectorStore):
            return store

        index_state = ctx.lifespan_context.get("index_state")
        if isinstance(index_state, IndexState):
            raise self._readiness_error(index_state)

        raise ToolError(
            "Vector store not initialized. Start the server first."
        )

    @staticmethod
    def _readiness_error(index_state: IndexState) -> ToolError:
        match index_state.status:
            case IndexStatus.FAILED:
                return ToolError(
                    f"Vector store indexing failed: "
                    f"{index_state.error_message}. "
                    "Server cannot serve search or execute requests."
                )

            case IndexStatus.PENDING | IndexStatus.BUILDING:
                return ToolError(
                    "Vector store is still indexing. "
                    "Retry shortly once indexing completes."
                )

            case _:
                return ToolError(
                    "Vector store not initialized. Start the server first."
                )
