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

"""Application settings using pydantic-settings."""

from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

McpTransport = Literal["stdio", "streamable-http"]
MCP_PATH = "/mcp"


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(env_prefix="", case_sensitive=False)

    meraki_dashboard_api_key: SecretStr | None = Field(
        default=None,
        description="Meraki Dashboard API key (never log or serialize raw)",
    )

    mcp_host: str | None = Field(
        default=None,
        description="Host to bind MCP server",
    )
    mcp_port: int = Field(
        default=8000,
        description="Port to bind MCP server",
    )
    mcp_transport: McpTransport = Field(
        default="stdio",
        description="FastMCP transport to use",
    )
    embedding_model: str = Field(
        default="sentence-transformers/all-MiniLM-L6-v2",
        description="ONNX embedding model used for semantic search",
    )

    # Scope weight multipliers for search ranking
    scope_weight_organization: float = Field(
        default=1.5,
        description="Weight multiplier for organization-scoped endpoints",
    )
    scope_weight_network: float = Field(
        default=1.2,
        description="Weight multiplier for network-scoped endpoints",
    )
    scope_weight_device: float = Field(
        default=1.1,
        description="Weight multiplier for device-scoped endpoints",
    )
    scope_weight_administered: float = Field(
        default=1.0,
        description="Weight multiplier for administered endpoints",
    )
    scope_weight_global: float = Field(
        default=1.0,
        description="Weight multiplier for global endpoints",
    )

    @field_validator("mcp_host", mode="before")
    @classmethod
    def normalize_empty_mcp_host(cls, value: str | None) -> str | None:
        return None if value == "" else value


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
