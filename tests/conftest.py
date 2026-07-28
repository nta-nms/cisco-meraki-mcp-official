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
import asyncio
import json
from contextlib import asynccontextmanager
from pathlib import Path
from types import SimpleNamespace

import httpx
import numpy as np
import pytest
from fastmcp import FastMCP
from pydantic import SecretStr

from cisco_meraki_mcp.classifiers.product import TagBasedProductClassifier
from cisco_meraki_mcp.classifiers.risk import HttpMethodRiskClassifier
from cisco_meraki_mcp.config.settings import get_settings
from cisco_meraki_mcp.index_state import IndexState, IndexStatus
from cisco_meraki_mcp.models.endpoint import (
    EndpointMetadata,
    EndpointParameter,
    EndpointScope,
)
from cisco_meraki_mcp.providers.vector_store import InMemoryVectorStore
from cisco_meraki_mcp.tools.execute_api import ExecuteApiFactory
from cisco_meraki_mcp.tools.semantic_search import SemanticSearchFactory


class EndpointProductClassifier:
    @staticmethod
    def classify(endpoint: EndpointMetadata) -> str:
        return endpoint.tags[0] if endpoint.tags else "common"


@pytest.fixture
def clear_settings_cache():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def asgi_client():
    @asynccontextmanager
    async def make_client(asgi_app):
        transport = httpx.ASGITransport(app=asgi_app)
        async with (
            httpx.AsyncClient(
                transport=transport, base_url="http://testserver"
            ) as client,
            asgi_app.router.lifespan_context(asgi_app),
        ):
            yield client

    return make_client


@pytest.fixture
def wait_for_status():
    async def _wait(
        state: IndexState,
        target: IndexStatus,
        *,
        timeout: float = 2.5,
        interval: float = 0.05,
    ) -> None:
        deadline = asyncio.get_running_loop().time() + timeout

        while (
            state.status is not target
            and asyncio.get_running_loop().time() < deadline
        ):
            await asyncio.sleep(interval)

        assert state.status is target, (
            f"IndexState did not reach {target} within "
            f"{timeout}s; observed {state.status}"
        )

    return _wait


@pytest.fixture
def skip_vector_store_init(mocker):
    return mocker.patch(
        "cisco_meraki_mcp.main.initialize_vector_store",
        return_value=mocker.Mock(),
    )


@pytest.fixture
def mock_text_embedding(mocker):
    base_rows = [
        np.array([0.1, 0.2, 0.3]),
        np.array([0.4, 0.5, 0.6]),
        np.array([0.7, 0.8, 0.9]),
    ]

    def fake_embed(texts, **_):
        materialized = list(texts)
        rows = [
            base_rows[index % len(base_rows)]
            for index in range(len(materialized))
        ]
        return iter(rows)

    mock_model = mocker.MagicMock()
    mock_model.embed.side_effect = fake_embed

    mocker.patch(
        "cisco_meraki_mcp.providers.vector_store.TextEmbedding",
        return_value=mock_model,
    )

    return mock_model


@pytest.fixture
def sample_endpoints() -> list[EndpointMetadata]:
    return [
        EndpointMetadata(
            operation_id="getNetworkWirelessSsids",
            summary="Get wireless SSIDs",
            description="Returns list of wireless SSIDs",
            method="GET",
            path="/networks/{networkId}/wireless/ssids",
            scope=EndpointScope.NETWORK,
            parameters=[
                EndpointParameter(
                    name="networkId",
                    location="path",
                    required=True,
                    param_type="string",
                    description="Network ID",
                )
            ],
        ),
        EndpointMetadata(
            operation_id="getOrganizationDevices",
            summary="Get organization devices",
            description="Returns list of devices in organization",
            method="GET",
            path="/organizations/{organizationId}/devices",
            scope=EndpointScope.ORGANIZATION,
            parameters=[
                EndpointParameter(
                    name="organizationId",
                    location="path",
                    required=True,
                    param_type="string",
                    description="Organization ID",
                )
            ],
        ),
        EndpointMetadata(
            operation_id="getNetwork",
            summary="Get network",
            description="Returns network info",
            method="GET",
            path="/networks/{networkId}",
            scope=EndpointScope.NETWORK,
            parameters=[],
        ),
    ]


@pytest.fixture
def endpoint_factory():
    def make_endpoint(**overrides) -> EndpointMetadata:
        values = {
            "operation_id": "op",
            "method": "GET",
            "path": "/x",
            "scope": EndpointScope.GLOBAL,
        }
        values.update(overrides)
        return EndpointMetadata(**values)

    return make_endpoint


@pytest.fixture
def product_classifier():
    return EndpointProductClassifier()


@pytest.fixture
def vector_store(mock_text_embedding, sample_endpoints):
    store = InMemoryVectorStore(model_name="test-model")
    store.add_endpoints(sample_endpoints)
    return store


@pytest.fixture
def mcp_context(vector_store: InMemoryVectorStore):
    state = IndexState()
    state.mark_ready()
    return SimpleNamespace(
        lifespan_context={
            "index_state": state,
            "store": vector_store,
        }
    )


@pytest.fixture
def search_factory() -> SemanticSearchFactory:
    return SemanticSearchFactory(
        risk_classifier=HttpMethodRiskClassifier(),
        product_classifier=TagBasedProductClassifier(),
    )


@pytest.fixture
def execute_factory() -> ExecuteApiFactory:
    return ExecuteApiFactory(
        product_classifier=TagBasedProductClassifier(),
        credential_provider=lambda: SecretStr("configured-key"),
        instrument_api_request=lambda fn: fn,
    )


@pytest.fixture
def search_tool(search_factory: SemanticSearchFactory, mcp_context):
    tool = search_factory.tool()

    async def call(query: str, *, top_k: int = 5):
        return await tool(query, ctx=mcp_context, top_k=top_k)

    return call


@pytest.fixture
def execute_tool(execute_factory: ExecuteApiFactory, mcp_context):
    tool = execute_factory.tool()

    async def call(**kwargs):
        return await tool(ctx=mcp_context, **kwargs)

    return call


@pytest.fixture
def sdk_execute_client(mocker):
    sdk_result = {"number": 0, "name": "Corp"}
    operation = mocker.AsyncMock()
    operation.__name__ = "getNetworkWirelessSsids"
    client = mocker.MagicMock()
    client.operation_for.return_value = operation
    client.request = mocker.AsyncMock(return_value=sdk_result)
    client.close = mocker.AsyncMock()
    meraki_client = mocker.patch(
        "cisco_meraki_mcp.tools.execute_api.MerakiClient",
        return_value=client,
    )

    return SimpleNamespace(
        client=client,
        meraki_client=meraki_client,
        operation=operation,
        sdk_result=sdk_result,
    )


@pytest.fixture
def mcp_app_factory():
    def make_app(tool, tool_name: str) -> FastMCP:
        app = FastMCP("network-platform-cloud-mcp-test")
        app.tool(tool, name=tool_name)
        return app

    return make_app


@pytest.fixture
def sample_openapi_spec(tmp_path) -> Path:
    spec = {
        "openapi": "3.0.0",
        "info": {
            "title": "Meraki API",
            "version": "1.0.0",
        },
        "paths": {
            "/networks/{networkId}/wireless/ssids": {
                "get": {
                    "operationId": "getNetworkWirelessSsids",
                    "summary": "List the MR SSIDs in a network",
                    "description": "List wireless SSIDs",
                    "tags": ["wireless"],
                    "parameters": [
                        {
                            "name": "networkId",
                            "in": "path",
                            "required": True,
                            "schema": {"type": "string"},
                            "description": "Network ID",
                        }
                    ],
                    "security": [{"oauth2": ["wireless:configure:read"]}],
                    "responses": {"200": {"description": "OK"}},
                },
                "post": {
                    "operationId": "createNetworkWirelessSsid",
                    "summary": "Create wireless SSID",
                    "description": "Create a wireless SSID",
                    "responses": {"201": {"description": "Created"}},
                },
            },
            "/organizations/{organizationId}/devices": {
                "get": {
                    "operationId": "getOrganizationDevices",
                    "summary": "Get organization devices",
                    "description": "Get devices in organization",
                    "parameters": [
                        {
                            "name": "organizationId",
                            "in": "path",
                            "required": True,
                            "schema": {"type": "string"},
                            "description": "Organization ID",
                        }
                    ],
                    "responses": {"200": {"description": "OK"}},
                },
            },
            "/networks/{networkId}/wireless/ssids/deprecated": {
                "get": {
                    "operationId": "getDeprecatedEndpoint",
                    "deprecated": True,
                    "summary": "Deprecated endpoint",
                    "responses": {"200": {"description": "OK"}},
                }
            },
        },
    }

    spec_file = tmp_path / "openapi.json"
    spec_file.write_text(json.dumps(spec))
    return spec_file
