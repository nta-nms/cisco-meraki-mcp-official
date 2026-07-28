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
import logging
import os

import pytest

from cisco_meraki_mcp.config.settings import get_settings
from cisco_meraki_mcp.main import create_app

CANARY = "MCP_TEST_CANARY_KEY_7f3a9c2e"


@pytest.fixture
def canary_api_key_env(mocker, clear_settings_cache):
    mocker.patch.dict(
        os.environ,
        {"MERAKI_DASHBOARD_API_KEY": CANARY},
        clear=True,
    )
    get_settings.cache_clear()
    return


def test_settings_never_serializes_raw_api_key(canary_api_key_env):
    settings = get_settings()
    assert CANARY not in settings.model_dump_json()
    assert CANARY not in str(settings.model_dump(mode="json"))


def test_create_app_logs_never_contain_api_key(canary_api_key_env, caplog):
    caplog.set_level(logging.INFO)

    create_app()

    blob = " ".join(rec.getMessage() for rec in caplog.records)
    assert CANARY not in blob
