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
from types import SimpleNamespace

import meraki.exceptions
import pytest
from pydantic import SecretStr

from cisco_meraki_mcp.providers.meraki_client import (
    MerakiApiError,
    MerakiClient,
)
from cisco_meraki_mcp.providers.request_validation import (
    RequestValidationError,
)
from cisco_meraki_mcp.resources import SERVER_NAME

API_KEY = SecretStr("test-api-key-abc123")


@pytest.fixture
def mock_sdk(mocker):
    return mocker.patch(
        "cisco_meraki_mcp.providers.meraki_client.meraki.aio.AsyncDashboardAPI"
    )


@pytest.fixture
def client(mock_sdk):
    return MerakiClient(api_key=API_KEY)


@pytest.fixture
def get_operation(mocker):
    def _make(**kwargs):
        operation = mocker.AsyncMock(**kwargs)
        operation.__name__ = "getNetwork"
        return operation

    return _make


@pytest.fixture
def fake_api_error(mocker):
    response = mocker.MagicMock()
    response.status_code = 403
    response.reason = "Forbidden"
    response.text = "Forbidden"
    response.json.return_value = {"errors": ["Forbidden"]}
    return meraki.exceptions.APIError(
        metadata={"tags": ["networks"], "operation": "getNetwork"},
        response=response,
    )


@pytest.fixture
def fake_async_api_error(mocker):
    response = mocker.MagicMock()
    response.status_code = 429
    response.reason = "Too Many Requests"
    return meraki.exceptions.AsyncAPIError(
        metadata={"tags": ["networks"], "operation": "getNetwork"},
        response=response,
        message="Rate limited",
    )


def test_client_enables_rate_limit_wait(mock_sdk):
    MerakiClient(api_key=API_KEY)

    assert mock_sdk.call_args.kwargs["wait_on_rate_limit"] is True


def test_client_suppresses_sdk_logging(mock_sdk):
    MerakiClient(api_key=API_KEY)

    assert mock_sdk.call_args.kwargs["suppress_logging"] is True
    assert mock_sdk.call_args.kwargs["output_log"] is False


def test_client_sets_mcp_caller_user_agent(mock_sdk):
    MerakiClient(api_key=API_KEY)

    assert MerakiClient.CALLER == "MerakiMCP/1.0 CiscoMeraki"
    assert mock_sdk.call_args.kwargs["caller"] == MerakiClient.CALLER


def test_client_uses_default_maximum_retries(mock_sdk):
    MerakiClient(api_key=API_KEY)

    assert mock_sdk.call_args.kwargs["maximum_retries"] == 3


def test_client_accepts_custom_maximum_retries(mock_sdk):
    MerakiClient(api_key=API_KEY, maximum_retries=5)

    assert mock_sdk.call_args.kwargs["maximum_retries"] == 5


def test_client_defaults_to_meraki_base_url_when_omitted(mock_sdk):
    MerakiClient(api_key=API_KEY)

    assert MerakiClient.BASE_URL == "https://api.meraki.com/api/v1"
    assert mock_sdk.call_args.kwargs["base_url"] == MerakiClient.BASE_URL


def test_client_passes_base_url_when_provided(mock_sdk):
    MerakiClient(api_key=API_KEY, base_url="https://custom.api.com")

    assert mock_sdk.call_args.kwargs["base_url"] == "https://custom.api.com"


def test_dashboard_exposes_underlying_sdk(client, mock_sdk):
    assert client.dashboard is mock_sdk.return_value


def test_operation_for_returns_matching_sdk_method(mocker, mock_sdk):
    operation = mocker.AsyncMock()
    operation.__name__ = "getNetworkWirelessSsids"
    dashboard = SimpleNamespace(
        networks=SimpleNamespace(getNetwork=mocker.AsyncMock()),
        wireless=SimpleNamespace(getNetworkWirelessSsids=operation),
    )
    mock_sdk.return_value = dashboard
    client = MerakiClient(api_key=API_KEY)

    assert client.operation_for("getNetworkWirelessSsids") is operation


def test_operation_for_returns_none_for_unknown_operation(mock_sdk):
    mock_sdk.return_value = SimpleNamespace(
        networks=SimpleNamespace(getNetwork=lambda: None),
    )
    client = MerakiClient(api_key=API_KEY)

    assert client.operation_for("getNotReal") is None


def test_operation_from_group_returns_none_for_non_callable_attribute():
    group = SimpleNamespace(getNetwork="not-callable")

    assert MerakiClient.operation_from_group(group, "getNetwork") is None


async def test_close_exits_dashboard_context(client, mock_sdk):
    await client.close()

    mock_sdk.return_value.__aexit__.assert_awaited_once_with(
        None,
        None,
        None,
    )


async def test_request_delegates_to_operation_method(client, get_operation):
    operation = get_operation(return_value={"id": "N_123"})

    result = await client.request(operation, networkId="N_123")

    operation.assert_called_once_with(networkId="N_123")
    assert result == {"id": "N_123"}


async def test_request_forwards_kwargs_without_total_pages(
    client, get_operation
):
    operation = get_operation(return_value=[{"id": "org-1"}])

    result = await client.request(operation, organizationId="org-1")

    operation.assert_called_once_with(organizationId="org-1")
    assert result == [{"id": "org-1"}]


async def test_request_rejects_total_pages(client, get_operation):
    operation = get_operation()

    with pytest.raises(RequestValidationError, match="Multi-page fetching"):
        await client.request(operation, total_pages="all")

    operation.assert_not_called()


async def test_request_raises_for_non_get_operation(client, mocker):
    operation = mocker.AsyncMock()
    operation.__name__ = "createNetwork"

    with pytest.raises(RequestValidationError, match="Only GET"):
        await client.request(operation, networkId="N_123")

    operation.assert_not_called()


async def test_request_passes_url_like_query_values(client, get_operation):
    operation = get_operation(return_value=[])
    url = "https://example.com/a/b"

    await client.request(operation, url=url)

    operation.assert_called_once_with(url=url)


async def test_request_passes_slash_bearing_non_traversal_values(
    client, get_operation
):
    operation = get_operation(return_value=[])

    await client.request(operation, path="folder/name")

    operation.assert_called_once_with(path="folder/name")


async def test_request_rejects_traversal_like_parameters(
    client, get_operation
):
    operation = get_operation()

    with pytest.raises(RequestValidationError, match="disallowed path value"):
        await client.request(operation, networkId="../../admin")

    operation.assert_not_called()


async def test_request_raises_meraki_api_error_on_sdk_error(
    client, get_operation, fake_api_error
):
    operation = get_operation(side_effect=fake_api_error)

    with pytest.raises(MerakiApiError):
        await client.request(operation, networkId="N_123")


async def test_request_preserves_status_on_meraki_api_error(
    client, get_operation, mocker
):
    response = mocker.MagicMock()
    response.status_code = 401
    response.reason = "Unauthorized"
    response.text = "Unauthorized"
    response.json.return_value = {"errors": ["Invalid API key"]}
    error = meraki.exceptions.APIError(
        metadata={"tags": ["organizations"], "operation": "getOrganizations"},
        response=response,
    )
    operation = get_operation(side_effect=error)

    with pytest.raises(MerakiApiError) as exc_info:
        await client.request(operation, organizationId="org-1")

    assert exc_info.value.status == 401


async def test_request_preserves_status_on_async_meraki_api_error(
    client, get_operation, fake_async_api_error
):
    operation = get_operation(side_effect=fake_async_api_error)

    with pytest.raises(MerakiApiError) as exc_info:
        await client.request(operation, networkId="N_123")

    assert exc_info.value.status == 429
    assert exc_info.value.message == "Rate limited"


def test_app_id_matches_canonical_server_name():
    assert MerakiClient.APP_ID == SERVER_NAME


def test_client_passes_app_id_to_sdk(mock_sdk):
    MerakiClient(api_key=API_KEY)

    assert mock_sdk.call_args.kwargs["meraki_app_id"] == MerakiClient.APP_ID
