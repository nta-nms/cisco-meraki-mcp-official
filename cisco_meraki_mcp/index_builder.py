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
"""Background index lifecycle for the MCP server.

Owns the asyncio plumbing that runs the slow vector-store index build
off the event loop while uvicorn's HTTP listener stays responsive.
The `IndexState` instance is owned by `create_app()` and passed in
via the constructor; `IndexBuilder` drives it from a worker thread
and from the lifespan task via the `mark_*` transition methods. The
indexed `InMemoryVectorStore` is published into the FastMCP lifespan
context so tools can read it from `ctx.lifespan_context`.
"""

import asyncio
import contextlib
import logging
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from threading import Lock

from fastmcp import FastMCP

from cisco_meraki_mcp.index_state import IndexState
from cisco_meraki_mcp.providers.vector_store import InMemoryVectorStore

logger = logging.getLogger(__name__)

EXPECTED_INDEX_ERRORS: tuple[type[Exception], ...] = (
    FileNotFoundError,
    OSError,
    RuntimeError,
    ValueError,
)

StoreFactory = Callable[[], InMemoryVectorStore]
LifespanContext = dict[str, IndexState | InMemoryVectorStore | None]


class IndexBuilder:
    """Drive the background vector-store index build."""

    def __init__(
        self,
        build_store: StoreFactory,
        state: IndexState,
    ) -> None:
        self._build_store = build_store
        self.state = state
        self._published_store: InMemoryVectorStore | None = None
        self._lifespan_context: LifespanContext | None = None
        self._store_lock = Lock()
        self._is_closed = False

    def build_blocking(self) -> None:
        """Run the blocking index build on a worker thread.

        Sentence-transformer model load and the 502-endpoint embedding
        pass are CPU- and IO-bound, and would block the event loop for
        ~15-30s on a CI runner if invoked inline. Invoked via
        `asyncio.to_thread(builder.build_blocking)` from the lifespan
        task so the server keeps serving requests.

        Any failure flips the owned `IndexState` to `FAILED` so
        readiness checks report the failure instead of reporting
        `building` forever. Expected
        errors are suppressed; programming bugs are re-raised so the
        asyncio.Task logs the traceback.
        """
        store = self.run_build()
        if store is not None:
            self.publish(store)

    def run_build(self) -> InMemoryVectorStore | None:
        self.state.mark_building()

        try:
            return self._build_store()
        except EXPECTED_INDEX_ERRORS as exc:
            self.record_failure(exc)
            return None
        except Exception as exc:
            self.record_failure(exc)
            raise

    def record_failure(self, exc: Exception) -> None:
        self.state.mark_failed(exc)
        self.log_failure(exc)

    def schedule(self) -> asyncio.Task[None]:
        self.state.mark_pending()
        return asyncio.create_task(
            asyncio.to_thread(self.build_blocking),
            name="vector-store-index-build",
        )

    def _open_lifespan_context(self) -> LifespanContext:
        self._lifespan_context = {
            "index_state": self.state,
            "store": None,
        }
        return self._lifespan_context

    @asynccontextmanager
    async def lifespan(
        self, server: FastMCP
    ) -> AsyncIterator[LifespanContext]:
        """Run indexing as a sibling task to request serving.

        Uvicorn refuses to accept HTTP connections until the lifespan
        startup block finishes, so any work that runs before `yield`
        delays the moment the server accepts requests. The blocking
        index build takes ~15-30s, which is why we schedule it as a
        background task and yield right away instead of awaiting it
        here.

        On shutdown we cancel the indexing task (if still in flight)
        and suppress `CancelledError` so teardown stays clean even
        when the server is interrupted before the index finishes.

        References:
        - ASGI Lifespan: https://asgi.readthedocs.io/en/latest/specs/lifespan.html
        - Uvicorn lifespan: https://www.uvicorn.org/settings/#implementation
        - FastMCP lifespans: https://gofastmcp.com/servers/server#lifespan
        """
        context = self._open_lifespan_context()
        task = self.schedule()
        try:
            yield context
        finally:
            await self.cancel(task)
            self.close_published_store()
            self._lifespan_context = None

    def log_failure(self, exc: Exception) -> None:
        """Log an index-build failure proportional to severity.

        Spec-missing is an operator misconfiguration: log a single warning.
        Anything else is still an operator-facing error (OS, network,
        malformed spec): log with full traceback so the failure is
        debuggable from CI artifacts and aggregated log search.
        """
        if isinstance(exc, FileNotFoundError):
            logger.warning(
                "Meraki spec not found; "
                "search/execute tools remain unavailable"
            )
            return

        logger.exception(
            "Vector store initialization failed; "
            "search/execute tools remain unavailable",
        )

    def publish(self, store: InMemoryVectorStore) -> None:
        with self._store_lock:
            if self._is_closed:
                store.close()
                return

            self._published_store = store
            if self._lifespan_context is not None:
                self._lifespan_context["store"] = store

            self.state.mark_ready()
        logger.info("Vector store index ready")

    def close_published_store(self) -> None:
        with self._store_lock:
            self._is_closed = True
            store = self._published_store
            self._published_store = None

            if self._lifespan_context is not None:
                self._lifespan_context["store"] = None

        if store is not None:
            store.close()

    async def cancel(self, task: asyncio.Task[None]) -> None:
        if not task.done():
            task.cancel()

        # Await the task so any CancelledError is retrieved and Python
        # does not log "Task exception was never retrieved" at GC.
        # Non-cancellation exceptions are intentionally left to
        # propagate so the lifespan teardown surfaces real bugs.
        with contextlib.suppress(asyncio.CancelledError):
            await task
