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
"""Public contract for the `semantic_search` tool.

Pure data definitions. Construction logic lives in
`cisco_meraki_mcp.factories.search_result` so this module
has no knowledge of internal endpoint metadata.
"""

from typing import Annotated

from pydantic import Field

from cisco_meraki_mcp.contracts.common import RiskTier, StrictModel


class RequiredParameter(StrictModel):
    """Typed description of a parameter the caller must provide.

    Field names mirror the previously emitted dict shape so the MCP
    `outputSchema` for `semantic_search` stays wire-compatible.
    """

    name: str = Field(
        description="Parameter name.",
    )
    location: str = Field(
        description="Where the parameter is sent (path, query, ...).",
    )
    required: bool = Field(
        description="Whether the caller must supply this parameter.",
    )
    type: str = Field(
        description="Parameter primitive type (string, integer, ...).",
    )
    description: str = Field(
        default="",
        description="Human-readable parameter description.",
    )


class SearchInput(StrictModel):
    """Input schema for the `semantic_search` tool."""

    query: str = Field(
        description="Natural-language description of intent.",
    )
    top_k: Annotated[int, Field(ge=1, le=20)] = Field(
        default=5,
        description="Number of results to return (1-20).",
    )


class SearchResult(StrictModel):
    """A single ranked capability surfaced by `semantic_search`."""

    capability_id: str = Field(
        description="Stable capability identifier.",
    )
    intent: str = Field(
        description="Short natural-language intent.",
    )
    product_scope: str = Field(
        description="Meraki product family (wireless, switch, ...).",
    )
    risk_tier: RiskTier = Field(
        description="Safety classification of the capability.",
    )
    tags: list[str] = Field(
        default_factory=list,
        description="Free-form tags from the underlying API spec.",
    )
    required_parameters: list[RequiredParameter] = Field(
        default_factory=list,
        description="Parameters the caller must provide.",
    )


class SearchOutput(StrictModel):
    """Output schema for the `semantic_search` tool."""

    results: list[SearchResult] = Field(
        default_factory=list,
        description="Ranked capabilities matching the query.",
    )
