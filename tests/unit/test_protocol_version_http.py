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
import pytest

from cisco_meraki_mcp.main import create_app

# Protocol-version validation is owned by the MCP SDK (`mcp`); we add no
# custom handling. Supported versions come from the SDK's
# SUPPORTED_PROTOCOL_VERSIONS (mcp/shared/version.py): 2024-11-05, 2025-03-26,
# 2025-06-18, 2025-11-25 (as of mcp 1.26.0). The SDK rejects an unsupported
# MCP-Protocol-Version header with HTTP 400; these tests lock that in.
# SUPPORTED_VERSION is one such valid version.
SUPPORTED_VERSION = "2025-03-26"


@pytest.fixture
def skip_vector_store_init(mocker):
    return mocker.patch(
        "cisco_meraki_mcp.main.initialize_vector_store",
        return_value=mocker.Mock(),
    )


@pytest.mark.asyncio
async def test_unsupported_protocol_version_returns_400(
    asgi_client, skip_vector_store_init
):
    # stateless_http=True mirrors production (main.py http_run_kwargs)
    asgi_app = create_app().http_app(stateless_http=True)
    body = '{"jsonrpc":"2.0","id":1,"method":"ping"}'

    async with asgi_client(asgi_app) as client:
        response = await client.post(
            "/mcp",
            content=body,
            headers={
                "host": "localhost",
                "accept": "application/json, text/event-stream",
                "content-type": "application/json",
                "mcp-protocol-version": "1999-01-01",
            },
        )

    assert response.status_code == 400
    assert "protocol version" in response.text.lower()


@pytest.mark.asyncio
async def test_supported_protocol_version_not_rejected(
    asgi_client, skip_vector_store_init
):
    asgi_app = create_app().http_app(stateless_http=True)
    body = '{"jsonrpc":"2.0","id":1,"method":"ping"}'

    async with asgi_client(asgi_app) as client:
        response = await client.post(
            "/mcp",
            content=body,
            headers={
                "host": "localhost",
                "accept": "application/json, text/event-stream",
                "content-type": "application/json",
                "mcp-protocol-version": SUPPORTED_VERSION,
            },
        )

    assert response.status_code != 400
