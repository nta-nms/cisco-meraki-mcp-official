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
"""API execution tool factory and SDK response helpers."""

import logging
from collections.abc import Awaitable, Callable, Mapping
from typing import ClassVar

from fastmcp import Context
from mcp.types import ToolAnnotations
from pydantic import SecretStr

from cisco_meraki_mcp.classifiers.product import ProductClassifier
from cisco_meraki_mcp.contracts.execute import (
    ExecuteData,
    ExecuteError,
    ExecuteReadOutput,
    ParameterValue,
)
from cisco_meraki_mcp.factories.api_error_message import ApiErrorMessage
from cisco_meraki_mcp.factories.execute_result import ExecuteResult
from cisco_meraki_mcp.models.endpoint import EndpointMetadata
from cisco_meraki_mcp.providers.meraki_client import (
    MerakiApiError,
    MerakiClient,
)
from cisco_meraki_mcp.providers.request_validation import (
    RequestValidationError,
)
from cisco_meraki_mcp.tools.logging import log_tool_invocation
from cisco_meraki_mcp.tools.tool_factory import ToolFactory

logger = logging.getLogger(__name__)

TOOL_NAME = "execute_api"
CredentialProvider = Callable[[], SecretStr | None]
ApiRequest = Callable[..., Awaitable[object]]
ApiRequestInstrumenter = Callable[[ApiRequest], ApiRequest]


def normalize_execute_data(payload: object) -> ExecuteData:
    """Normalize SDK payloads into the public execute data envelope."""
    if isinstance(payload, Mapping):
        return ExecuteData.model_validate(dict(payload))

    if isinstance(payload, list):
        return ExecuteData.model_validate({"items": payload})

    return ExecuteData.model_validate({"value": payload})


def log_request(endpoint: EndpointMetadata) -> None:
    """Log request details for observability.

    The resolved URL is intentionally not logged because it
    interpolates caller-supplied parameter values that may contain
    identifiers that must not appear in logs.
    """
    logger.info("Endpoint: %s %s", endpoint.method, endpoint.path)
    logger.info("Scope: %s", endpoint.scope.value)


def missing_required_parameters(
    endpoint: EndpointMetadata,
    parameters: Mapping[str, ParameterValue],
) -> list[str]:
    """Return the list of missing required parameters."""
    return [
        param.name
        for param in endpoint.parameters
        if param.required and param.name not in parameters
    ]


class ExecuteApiFactory(ToolFactory):
    """Build the `execute_api` MCP tool with injected deps."""

    tool_name = TOOL_NAME
    span_attrs: ClassVar[list[str]] = ["capability_id"]

    def __init__(
        self,
        *,
        product_classifier: ProductClassifier,
        credential_provider: CredentialProvider,
        instrument_api_request: ApiRequestInstrumenter,
    ) -> None:
        self._product_classifier = product_classifier
        self._credential_provider = credential_provider
        self._instrument_api_request = instrument_api_request

    def tool(
        self,
    ) -> Callable[..., Awaitable[ExecuteReadOutput | ExecuteError]]:
        return self.execute_api

    @staticmethod
    def annotations() -> ToolAnnotations:
        """Behavior hints for the `execute_api` tool listing."""
        return ToolAnnotations(
            readOnlyHint=True,
            idempotentHint=False,
            openWorldHint=True,
        )

    @staticmethod
    def sdk_error_result(
        result: ExecuteResult,
        endpoint: EndpointMetadata,
        exc: Exception,
    ) -> ExecuteError:
        """Translate SDK execution exceptions into tool errors."""
        if isinstance(exc, MerakiApiError):
            message = ApiErrorMessage(
                status=exc.status,
                operation_id=endpoint.operation_id,
            )
            return result.error(
                error=message.error_message,
                recovery_suggestion=message.recovery_suggestion,
            )

        if isinstance(exc, RequestValidationError):
            return result.error(
                error=exc.error,
                recovery_suggestion=exc.recovery_suggestion,
            )

        logger.error("Meraki SDK execution failed: %s", type(exc).__name__)
        return result.error(
            error="Meraki SDK error.",
            recovery_suggestion=(
                "Retry later or choose another read capability."
            ),
        )

    async def execute_with_client(
        self,
        *,
        client: MerakiClient,
        endpoint: EndpointMetadata,
        result: ExecuteResult,
        parameters: dict[str, ParameterValue],
    ) -> ExecuteReadOutput | ExecuteError:
        operation = client.operation_for(endpoint.operation_id)
        if operation is None:
            return result.error(
                error=(
                    "Capability is not supported by the Meraki SDK: "
                    f"{endpoint.operation_id}"
                ),
                recovery_suggestion=(
                    "Use semantic_search to choose another read capability."
                ),
            )

        try:
            request = self._instrument_api_request(client.request)
            payload = await request(operation, **parameters)
        except Exception as exc:
            return ExecuteApiFactory.sdk_error_result(result, endpoint, exc)

        return result.success(
            endpoint=endpoint,
            data=normalize_execute_data(payload),
        )

    async def execute_endpoint(
        self,
        *,
        endpoint: EndpointMetadata,
        result: ExecuteResult,
        parameters: dict[str, ParameterValue],
    ) -> ExecuteReadOutput | ExecuteError:
        """Create a short-lived SDK client and execute one endpoint."""
        api_key = self._credential_provider()
        if api_key is None:
            return result.error(
                error="Meraki API key is not configured",
                recovery_suggestion=(
                    "Send Authorization: Bearer <api-key> for HTTP "
                    "transports or set MERAKI_DASHBOARD_API_KEY for stdio."
                ),
            )

        log_request(endpoint)
        client = MerakiClient(api_key=api_key)
        try:
            return await self.execute_with_client(
                client=client,
                endpoint=endpoint,
                result=result,
                parameters=parameters,
            )
        finally:
            await client.close()

    @staticmethod
    def notification_summary(
        kwargs: Mapping[str, object],
        result: object,
    ) -> dict[str, object]:
        return {
            "capability_id": kwargs.get("capability_id", ""),
            "outcome": "error"
            if isinstance(result, ExecuteError)
            else "success",
        }

    @log_tool_invocation(
        TOOL_NAME,
        ["capability_id"],
        notification_summary,
    )
    async def execute_api(
        self,
        capability_id: str,
        ctx: Context,
        parameters: dict[str, ParameterValue] | None = None,
    ) -> ExecuteReadOutput | ExecuteError:
        """Execute a read-only Meraki capability found via semantic_search.

        Two-step flow: first call semantic_search to find a capability,
        then call execute_api with that capability's capability_id. Only
        GET/read capabilities are supported.

        Pass any path or query values through the parameters dict, keyed
        by parameter name. The Meraki API key is not a tool argument; the
        MCP host supplies the key per request via the Authorization:
        Bearer <api-key> header.

        Example:
            execute_api(
                capability_id="getOrganizationDevices",
                parameters={"organizationId": "123456"},
            )

        If you already know the capability_id, call execute_api directly.
        Otherwise use semantic_search to find it. Do NOT invent a
        capability_id.

        Args:
            capability_id: The capability ID from semantic search results.
            parameters: Dict of parameter names to values for the call.

        Returns:
            `ExecuteReadOutput` on success, `ExecuteError` on
            validation/lookup failure.
        """
        store = self.require_ready_store(ctx)
        parameters = parameters or {}

        result = ExecuteResult(
            capability_id=capability_id,
            product_classifier=self._product_classifier,
        )

        endpoint = store.endpoint_for(capability_id)
        if not endpoint:
            return result.error(
                error=f"Capability not found: {capability_id}",
                recovery_suggestion=(
                    "Use semantic_search to find valid capabilities."
                ),
            )

        missing = missing_required_parameters(endpoint, parameters)
        if missing:
            return result.error(
                error="Missing required parameters",
                recovery_suggestion=(
                    f"Provide values for: {', '.join(missing)}"
                ),
            )

        return await self.execute_endpoint(
            endpoint=endpoint,
            result=result,
            parameters=parameters,
        )
