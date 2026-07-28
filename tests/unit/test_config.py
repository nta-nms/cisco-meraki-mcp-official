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
import os

from pydantic import SecretStr

from cisco_meraki_mcp.config.settings import Settings, get_settings


def test_settings_defaults():
    settings = Settings()
    assert settings.mcp_host is None
    assert settings.mcp_port == 8000
    assert settings.embedding_model == "sentence-transformers/all-MiniLM-L6-v2"
    assert settings.meraki_dashboard_api_key is None


def test_settings_mcp_host_uses_environment_override(mocker):
    mocker.patch.dict(os.environ, {"MCP_HOST": "127.0.0.1"}, clear=True)

    settings = Settings()

    assert settings.mcp_host == "127.0.0.1"


def test_settings_mcp_host_treats_empty_environment_as_unset(mocker):
    mocker.patch.dict(os.environ, {"MCP_HOST": ""}, clear=True)

    settings = Settings()

    assert settings.mcp_host is None


def test_settings_meraki_dashboard_api_key_uses_dashboard_environment(mocker):
    mocker.patch.dict(
        os.environ,
        {"MERAKI_DASHBOARD_API_KEY": "dashboard-key"},
        clear=True,
    )

    settings = Settings()

    assert settings.meraki_dashboard_api_key is not None
    assert (
        settings.meraki_dashboard_api_key.get_secret_value() == "dashboard-key"
    )


def test_settings_meraki_dashboard_api_key_ignores_legacy_environment(mocker):
    mocker.patch.dict(
        os.environ,
        {"_".join(("MERAKI", "API", "KEY")): "legacy-key"},
        clear=True,
    )

    settings = Settings()

    assert settings.meraki_dashboard_api_key is None


def test_settings_meraki_dashboard_api_key_accepts_direct_construction():
    settings = Settings(meraki_dashboard_api_key=SecretStr("dashboard-key"))

    assert settings.meraki_dashboard_api_key is not None
    assert (
        settings.meraki_dashboard_api_key.get_secret_value() == "dashboard-key"
    )


def test_meraki_api_key_not_exposed_in_json_serialization(
    mocker, clear_settings_cache
):
    mocker.patch.dict(
        os.environ,
        {"MERAKI_DASHBOARD_API_KEY": "CANARY_SECRET_ABC_FOR_TESTS"},
        clear=True,
    )
    get_settings.cache_clear()

    settings = get_settings()
    dumped = settings.model_dump_json()

    assert "CANARY_SECRET_ABC_FOR_TESTS" not in dumped


def test_settings_scope_weights_defaults():
    settings = Settings()
    assert settings.scope_weight_organization == 1.5
    assert settings.scope_weight_network == 1.2
    assert settings.scope_weight_device == 1.1
    assert settings.scope_weight_administered == 1.0
    assert settings.scope_weight_global == 1.0


def test_get_settings_cached():
    settings1 = get_settings()
    settings2 = get_settings()
    assert settings1 is settings2
