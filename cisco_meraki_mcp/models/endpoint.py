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
"""Data models for API endpoints."""

from enum import StrEnum

from pydantic import BaseModel, Field


class EndpointScope(StrEnum):
    """Scope level of an API endpoint (priority order)."""

    ORGANIZATION = "organization"
    NETWORK = "network"
    DEVICE = "device"
    ADMINISTERED = "administered"
    GLOBAL = "global"


class EndpointParameter(BaseModel):
    """Model for an API endpoint parameter."""

    name: str = Field(description="Parameter name")
    location: str = Field(description="Parameter location (path, query)")
    required: bool = Field(default=False, description="Whether required")
    param_type: str = Field(
        default="string",
        description="Parameter type",
        alias="type",
    )
    description: str = Field(default="", description="Parameter description")


class EndpointMetadata(BaseModel):
    """Metadata for a single API endpoint."""

    operation_id: str = Field(description="Unique operation identifier")
    method: str = Field(description="HTTP method (GET)")
    path: str = Field(description="API path with path parameters")
    summary: str = Field(default="", description="Brief summary")
    description: str = Field(default="", description="Detailed description")
    tags: list[str] = Field(default_factory=list, description="API tags")
    parameters: list[EndpointParameter] = Field(
        default_factory=list,
        description="Endpoint parameters",
    )
    scope: EndpointScope = Field(
        default=EndpointScope.GLOBAL,
        description="API scope level",
    )
    required_scopes: frozenset[str] = Field(
        default_factory=frozenset,
        description="OAuth scopes required to call this endpoint",
    )

    @property
    def searchable_text(self) -> str:
        """Generate text for semantic search indexing."""
        parts = [
            self.operation_id,
            self.summary,
            self.description,
            " ".join(self.tags),
            self.path,
        ]
        return " ".join(part for part in parts if part)


class VectorSearchHit(BaseModel):
    """Vector search hit with endpoint and weighted similarity score."""

    endpoint: EndpointMetadata = Field(description="Matched endpoint metadata")
    score: float = Field(
        description="Weighted similarity score (higher is better)",
    )
