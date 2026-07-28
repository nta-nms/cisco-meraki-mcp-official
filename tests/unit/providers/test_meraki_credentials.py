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
from pydantic import SecretStr

from cisco_meraki_mcp.config.settings import Settings
from cisco_meraki_mcp.providers.meraki_credentials import (
    AUTHORIZATION_HEADER,
    meraki_api_key_for_transport,
    meraki_api_key_from_headers,
    meraki_api_key_from_settings,
    secret_from_text,
)


def test_secret_from_text_strips_value():
    secret = secret_from_text("  test-key  ")

    assert secret is not None
    assert secret.get_secret_value() == "test-key"


def test_secret_from_text_returns_none_for_blank_value():
    assert secret_from_text("  ") is None


def test_meraki_api_key_from_headers_reads_bearer_token():
    secret = meraki_api_key_from_headers({
        AUTHORIZATION_HEADER: "Bearer header-key",
    })

    assert secret is not None
    assert secret.get_secret_value() == "header-key"


def test_meraki_api_key_from_headers_matches_name_case_insensitively():
    secret = meraki_api_key_from_headers({
        "Authorization": "Bearer header-key",
    })

    assert secret is not None
    assert secret.get_secret_value() == "header-key"


def test_meraki_api_key_from_headers_reads_byte_header_name():
    secret = meraki_api_key_from_headers({
        AUTHORIZATION_HEADER.encode(): "Bearer header-key",
    })

    assert secret is not None
    assert secret.get_secret_value() == "header-key"


def test_meraki_api_key_from_headers_matches_scheme_case_insensitively():
    secret = meraki_api_key_from_headers({
        AUTHORIZATION_HEADER: "bearer header-key",
    })

    assert secret is not None
    assert secret.get_secret_value() == "header-key"


def test_meraki_api_key_from_headers_ignores_blank_bearer_token():
    assert (
        meraki_api_key_from_headers({
            AUTHORIZATION_HEADER: "Bearer   ",
        })
        is None
    )


def test_meraki_api_key_from_headers_ignores_non_bearer_value():
    assert (
        meraki_api_key_from_headers({
            AUTHORIZATION_HEADER: "Basic abc123",
        })
        is None
    )


def test_meraki_api_key_from_headers_returns_none_when_no_matching_header():
    assert (
        meraki_api_key_from_headers({"content-type": "application/json"})
        is None
    )


def test_meraki_api_key_from_settings_reads_stdio_env_key():
    settings = Settings(meraki_dashboard_api_key=SecretStr("env-key"))

    secret = meraki_api_key_from_settings(settings)

    assert secret is not None
    assert secret.get_secret_value() == "env-key"


def test_meraki_api_key_from_settings_ignores_blank_env_key():
    settings = Settings(meraki_dashboard_api_key=SecretStr("  "))

    assert meraki_api_key_from_settings(settings) is None


def test_meraki_api_key_for_transport_uses_stdio_settings():
    settings = Settings(
        mcp_transport="stdio",
        meraki_dashboard_api_key=SecretStr("env-key"),
    )

    secret = meraki_api_key_for_transport(settings=settings)

    assert secret is not None
    assert secret.get_secret_value() == "env-key"


def test_meraki_api_key_for_transport_uses_http_headers(mocker):
    get_headers = mocker.patch(
        "cisco_meraki_mcp.providers.meraki_credentials.get_http_headers",
        return_value={AUTHORIZATION_HEADER: "Bearer header-key"},
    )

    secret = meraki_api_key_for_transport(transport="streamable-http")

    assert secret is not None
    assert secret.get_secret_value() == "header-key"
    get_headers.assert_called_once_with(include={AUTHORIZATION_HEADER})
