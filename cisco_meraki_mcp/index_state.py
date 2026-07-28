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
"""Vector-store index lifecycle state for the MCP server.

`IndexState` is a small value object that tracks where the background
vector-store build is in its lifecycle (`PENDING -> BUILDING -> READY`
or `FAILED`). The instance is created once by `create_app()` and
passed explicitly to `IndexBuilder`.
There is no module- or class-level cache; request-time callers read
the instance from FastMCP's lifespan context.
"""

from enum import StrEnum

from pydantic import BaseModel


class IndexStatus(StrEnum):
    """Lifecycle states for the vector-store background index build."""

    PENDING = "pending"
    BUILDING = "building"
    READY = "ready"
    FAILED = "failed"


class IndexState(BaseModel):
    """Observable status of the lazily-built vector-store index.

    Instances are owned by `create_app()` and passed to the
    `IndexBuilder` lifespan.
    `IndexBuilder` drives the state via the `mark_*` transition
    methods from the background asyncio task.
    """

    status: IndexStatus = IndexStatus.PENDING
    error_message: str | None = None

    def mark_pending(self) -> None:
        self.status = IndexStatus.PENDING
        self.error_message = None

    def mark_building(self) -> None:
        self.status = IndexStatus.BUILDING

    def mark_ready(self) -> None:
        self.status = IndexStatus.READY
        self.error_message = None

    def mark_failed(self, exc: Exception) -> None:
        self.status = IndexStatus.FAILED
        self.error_message = f"{type(exc).__name__}: {exc}"
