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
"""Async Meraki API client wrapping AsyncDashboardAPI."""

from typing import Any, cast

import meraki.aio
import meraki.exceptions
from pydantic import SecretStr

from cisco_meraki_mcp.providers.request_validation import (
    SdkOperation,
    reject_total_pages_parameter,
    reject_traversal_parameters,
    require_get_operation,
)
from cisco_meraki_mcp.resources import SERVER_NAME


class MerakiApiError(Exception):
    """Raised when the Meraki API returns an error response."""

    def __init__(self, *, status: int, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.message = message


class MerakiClient:
    """Async Meraki API client backed by the official Meraki Python SDK.

    Wraps AsyncDashboardAPI with rate-limit backoff, automatic retries,
    and paginated GET support. SDK logging is suppressed to prevent API
    key exposure and to protect MCP's reserved stdout channel.
    """

    BASE_URL = "https://api.meraki.com/api/v1"
    CALLER = "MerakiOSSMCPO/1.0 CiscoMeraki"
    APP_ID = SERVER_NAME

    def __init__(
        self,
        *,
        api_key: SecretStr,
        base_url: str = BASE_URL,
        maximum_retries: int = 3,
    ) -> None:
        self._dashboard = meraki.aio.AsyncDashboardAPI(
            api_key=api_key.get_secret_value(),
            caller=self.CALLER,
            meraki_app_id=self.APP_ID,
            base_url=base_url,
            wait_on_rate_limit=True,
            maximum_retries=maximum_retries,
            single_request_timeout=30,
            output_log=False,
            suppress_logging=True,
        )

    async def request(
        self,
        operation_method: SdkOperation,
        **kwargs: Any,
    ) -> Any:
        """Execute a single SDK operation method.

        Only read (GET) operations are accepted today.

        For paginated endpoints this returns only the first page: the SDK
        methods default to `total_pages=1` and this wrapper never raises
        that. Fetching every page is intentionally unsupported for now, as
        it can bloat the agent's context and stall on large orgs.

        Args:
            operation_method: A bound SDK method, e.g.
                `client.dashboard.organizations.getOrganizationNetworks`.
            **kwargs: Parameters forwarded verbatim to the operation.

        Returns:
            The API response (first page only for paginated endpoints).

        Raises:
            RequestValidationError: If the operation method is not a GET SDK
                method, if `total_pages` is passed (multi-page fetching is not
                supported), or if a parameter looks like path traversal.
            MerakiApiError: If the Meraki API returns an error response.
        """
        require_get_operation(operation_method)
        reject_total_pages_parameter(kwargs)
        reject_traversal_parameters(kwargs)
        try:
            response = await operation_method(**kwargs)
        except (
            meraki.exceptions.APIError,
            meraki.exceptions.AsyncAPIError,
        ) as exc:
            raise MerakiApiError(
                status=cast("int", exc.status),
                message=str(exc.message),
            ) from exc

        return response

    def operation_for(self, operation_id: str) -> SdkOperation | None:
        """Return the SDK operation matching an OpenAPI operation ID."""
        for group in self.public_resource_groups():
            operation = self.operation_from_group(group, operation_id)
            if operation is not None:
                return operation

        return None

    def public_resource_groups(self) -> list[object]:
        """Return public SDK resource groups to inspect for operations."""
        return [
            getattr(self._dashboard, group_name)
            for group_name in dir(self._dashboard)
            if not group_name.startswith("_")
        ]

    @staticmethod
    def operation_from_group(
        group: object,
        operation_id: str,
    ) -> SdkOperation | None:
        """Return a callable operation from one SDK resource group."""
        operation = getattr(group, operation_id, None)
        if callable(operation):
            return cast("SdkOperation", operation)

        return None

    async def close(self) -> None:
        """Close the underlying SDK HTTP session."""
        # The SDK exposes async context-manager cleanup but no public close().
        await self._dashboard.__aexit__(None, None, None)

    @property
    def dashboard(self) -> meraki.aio.AsyncDashboardAPI:
        """The underlying AsyncDashboardAPI instance."""
        return self._dashboard
