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
"""Public contract for the `execute_api` tool.

Pure data definitions. `ExecuteReadOutput` and `ExecuteError`
form a tagged union via the literal `type` field; clients use that
field to discriminate at runtime even though FastMCP serializes the
union as `anyOf` rather than a Pydantic discriminated union.
"""

from typing import Literal

from pydantic import ConfigDict, Field

from cisco_meraki_mcp.contracts.common import StrictModel

ParameterValue = str | int | bool


class ExecuteData(StrictModel):
    """Typed envelope for the capability response payload.

    Carries the runtime payload without resorting to `Any` while
    preserving the serialized field set: extra fields are allowed so
    the existing dict-on-the-wire shape round-trips unchanged.
    """

    model_config = ConfigDict(frozen=True, extra="allow")


class ExecuteReadInput(StrictModel):
    """Input schema for `execute_api` (read capabilities)."""

    capability_id: str = Field(
        description="Capability identifier from semantic_search.",
    )
    parameters: dict[str, ParameterValue] | None = Field(
        default=None,
        description="Path/query parameters for the capability.",
    )


class ExecuteReadOutput(StrictModel):
    """Successful response from `execute_api`."""

    type: Literal["success"] = Field(
        default="success",
        description="Discriminator tag for the response variant.",
    )
    capability_id: str = Field(
        description="Echo of the executed capability identifier.",
    )
    product: str = Field(
        description="Meraki product family the capability targets.",
    )
    data: ExecuteData = Field(
        description="Typed response payload from the capability.",
    )


class ExecuteError(StrictModel):
    """Failure response from `execute_api`."""

    type: Literal["error"] = Field(
        default="error",
        description="Discriminator tag for the response variant.",
    )
    error: str = Field(
        description="Human-readable failure summary.",
    )
    recovery_suggestion: str = Field(
        description="Concrete next step the caller can take.",
    )
    capability_id: str | None = Field(
        default=None,
        description="Capability identifier when known.",
    )
