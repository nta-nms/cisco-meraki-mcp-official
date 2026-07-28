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
from collections.abc import Awaitable, Callable
from types import SimpleNamespace

import pytest
from fastmcp.exceptions import ToolError

from cisco_meraki_mcp.index_state import IndexState, IndexStatus
from cisco_meraki_mcp.providers.vector_store import InMemoryVectorStore
from cisco_meraki_mcp.tools.tool_factory import ToolFactory


class _StubFactory(ToolFactory):
    tool_name = "stub"

    def tool(self) -> Callable[..., Awaitable[object]]:
        return self.noop

    async def noop(self) -> None:
        return None


def mcp_context(
    state: IndexState,
    store: InMemoryVectorStore | None = None,
):
    return SimpleNamespace(
        lifespan_context={
            "index_state": state,
            "store": store,
        }
    )


def test_require_ready_store_returns_published_store(
    mock_text_embedding,
):
    state = IndexState()
    state.status = IndexStatus.READY
    store = InMemoryVectorStore(model_name="test-model")
    factory = _StubFactory()

    assert (
        factory.require_ready_store(mcp_context(state=state, store=store))
        is store
    )


def test_require_ready_store_raises_when_context_missing_state():
    factory = _StubFactory()
    ctx = SimpleNamespace(lifespan_context={})

    with pytest.raises(ToolError, match="not initialized"):
        factory.require_ready_store(ctx)


@pytest.mark.parametrize(
    ("status", "error_message", "expected_substring"),
    [
        (IndexStatus.PENDING, None, "still indexing"),
        (IndexStatus.BUILDING, None, "still indexing"),
        (IndexStatus.FAILED, "boom", "boom"),
        (IndexStatus.READY, None, "not initialized"),
    ],
)
def test_require_ready_store_raises_tool_error_when_unready(
    status: IndexStatus,
    error_message: str | None,
    expected_substring: str,
):
    state = IndexState()
    state.status = status
    state.error_message = error_message
    factory = _StubFactory()

    with pytest.raises(ToolError, match=expected_substring):
        factory.require_ready_store(mcp_context(state=state))
