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
"""Meraki API credential resolution for MCP transports."""

from collections.abc import Mapping

from fastmcp.server.dependencies import get_http_headers
from pydantic import SecretStr

from cisco_meraki_mcp.config.settings import Settings, get_settings

AUTHORIZATION_HEADER = "authorization"
BEARER_SCHEME = "bearer"


def secret_from_text(value: str | None) -> SecretStr | None:
    if value is None or not value.strip():
        return None

    return SecretStr(value.strip())


def secret_from_bearer(value: str) -> SecretStr | None:
    scheme, separator, token = value.strip().partition(" ")
    if not separator or scheme.lower() != BEARER_SCHEME:
        return None

    return secret_from_text(token.strip())


def _normalize_header_name(name: str | bytes) -> str:
    return name.decode() if isinstance(name, bytes) else name


def meraki_api_key_from_headers[HeaderName: (str, bytes)](
    headers: Mapping[HeaderName, str],
) -> SecretStr | None:
    for name, value in headers.items():
        if _normalize_header_name(name).lower() == AUTHORIZATION_HEADER:
            return secret_from_bearer(value)

    return None


def meraki_api_key_from_settings(
    settings: Settings,
) -> SecretStr | None:
    if settings.meraki_dashboard_api_key is None:
        return None

    return secret_from_text(
        settings.meraki_dashboard_api_key.get_secret_value()
    )


def meraki_api_key_for_transport(
    *,
    settings: Settings | None = None,
    transport: str | None = None,
) -> SecretStr | None:
    resolved_settings = settings or get_settings()
    resolved_transport = transport or resolved_settings.mcp_transport
    if resolved_transport == "stdio":
        return meraki_api_key_from_settings(resolved_settings)

    headers = get_http_headers(include={AUTHORIZATION_HEADER})
    return meraki_api_key_from_headers(headers)
