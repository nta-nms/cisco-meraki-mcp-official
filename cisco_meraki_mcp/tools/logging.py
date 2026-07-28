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
"""Logging utilities for MCP tools.

Tool modules use their Python module logger names. Tool-specific context is
attached through structured log fields so filtering does not depend on custom
logger hierarchies.
"""

import functools
import logging
import uuid
from collections.abc import Awaitable, Callable, Mapping
from typing import ParamSpec, TypeVar

from fastmcp.server.dependencies import get_http_request
from pydantic import SecretStr

P = ParamSpec("P")
R = TypeVar("R")
SummaryBuilder = Callable[[Mapping[str, object], object], dict[str, object]]
logger = logging.getLogger(__name__)

REDACTED_PLACEHOLDER = "***REDACTED***"

SENSITIVE_PARAM_NAMES: frozenset[str] = frozenset({
    "api_key",
    "meraki_api_key",
    "meraki_dashboard_api_key",
    "token",
    "secret",
    "password",
    "authorization",
})
MCP_EXCLUDED_PARAMS = SENSITIVE_PARAM_NAMES | frozenset({
    "parameters",
    "query",
})

MCP_SESSION_HEADER = "mcp-session-id"
REQUEST_ID_HEADER = "x-request-id"


def redact_value(name: str, value: object) -> object:
    """Return a redacted placeholder for sensitive values.

    A value is redacted when its parameter name is on the sensitive
    allow-list or when the value is a `SecretStr`. Everything else is
    returned unchanged so non-sensitive parameters remain observable.
    """
    if isinstance(value, SecretStr):
        return REDACTED_PLACEHOLDER

    if name.lower() in SENSITIVE_PARAM_NAMES:
        return REDACTED_PLACEHOLDER

    return value


def resolve_request_id() -> tuple[str, str | None]:
    """Resolve a `(request_id, session_id)` pair for a tool invocation.

    Uses an upstream `x-request-id` header when one is supplied by the
    HTTP transport, otherwise mints a fresh UUIDv4 hex. Returns the
    `mcp-session-id` header when present so log lines can be joined
    with traces from the FastMCP HTTP transport. Falls back to a
    minted request id and `None` session id outside an HTTP context
    (e.g. stdio transport, unit tests).
    """
    try:
        request = get_http_request()
    except RuntimeError, LookupError:
        return uuid.uuid4().hex, None

    headers = request.headers
    upstream = headers.get(REQUEST_ID_HEADER)
    session_id = headers.get(MCP_SESSION_HEADER)
    request_id = upstream or uuid.uuid4().hex

    return request_id, session_id


class ToolLogger:
    """Callable decorator that logs MCP tool invocations."""

    def __init__(
        self,
        tool_name: str,
        log_params: list[str] | None = None,
        summary_builder: SummaryBuilder | None = None,
    ) -> None:
        self.tool_name = tool_name
        self.log_params = log_params
        self.summary_builder = summary_builder

    def structured_extra(
        self,
        request_id: str,
        session_id: str | None,
    ) -> dict[str, object]:
        """Return structured log fields for all tool invocation records."""
        return {
            "tool": self.tool_name,
            "request_id": request_id,
            "session_id": session_id,
        }

    def parameter_names(self, kwargs: Mapping[str, object]) -> list[str]:
        """Return the parameter names that should be logged."""
        if self.log_params is not None:
            return [param for param in self.log_params if param in kwargs]

        return list(kwargs.keys())

    def log_parameters(
        self,
        logger: logging.Logger,
        kwargs: Mapping[str, object],
        extra: dict[str, object],
    ) -> None:
        """Log selected keyword arguments, redacting sensitive values."""
        for param in self.parameter_names(kwargs):
            logger.info(
                "%s: %s",
                param.replace("_", " ").title(),
                redact_value(param, kwargs[param]),
                extra=extra,
            )

    def log_correlation_ids(
        self,
        logger: logging.Logger,
        request_id: str,
        session_id: str | None,
        extra: dict[str, object],
    ) -> None:
        """Log correlation identifiers for a tool invocation."""
        if session_id is None:
            logger.info("request_id=%s", request_id, extra=extra)
            return

        logger.info(
            "request_id=%s session_id=%s",
            request_id,
            session_id,
            extra=extra,
        )

    def build_notification_summary(
        self,
        kwargs: Mapping[str, object],
        result: object,
        log_extra: dict[str, object],
    ) -> dict[str, object]:
        summary: dict[str, object] = {"tool": self.tool_name}
        if self.summary_builder is None:
            return summary

        try:
            summary.update(self.summary_builder(kwargs, result))
        except Exception:
            logger.warning(
                "Failed to build MCP tool notification summary",
                exc_info=True,
                extra=log_extra,
            )

        return summary

    async def emit_tool_notification(
        self,
        ctx: object | None,
        kwargs: Mapping[str, object],
        result: object,
        log_extra: dict[str, object],
    ) -> None:
        info = getattr(ctx, "info", None)
        if not callable(info):
            return

        summary = self.build_notification_summary(kwargs, result, log_extra)
        notification_extra = {
            key: value
            for key, value in summary.items()
            if key not in MCP_EXCLUDED_PARAMS
        }
        notification_extra.update({
            "request_id": log_extra["request_id"],
            "session_id": log_extra["session_id"],
        })

        try:
            await info(
                f"{summary['tool']} completed",
                extra=notification_extra,
            )
        except Exception:
            # Notification delivery must not alter the wrapped tool result.
            logger.warning(
                "Failed to emit MCP tool notification",
                exc_info=True,
                extra=log_extra,
            )

    def __call__(
        self,
        func: Callable[P, Awaitable[R]],
    ) -> Callable[P, Awaitable[R]]:
        logger = logging.getLogger(func.__module__)

        @functools.wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            request_id, session_id = resolve_request_id()
            extra = self.structured_extra(request_id, session_id)

            logger.info(self.tool_name.upper().replace("_", " "), extra=extra)
            self.log_correlation_ids(logger, request_id, session_id, extra)
            self.log_parameters(logger, kwargs, extra)

            result = await func(*args, **kwargs)
            await self.emit_tool_notification(
                kwargs.get("ctx"),
                kwargs,
                result,
                extra,
            )

            return result

        return wrapper


def log_tool_invocation(
    tool_name: str,
    log_params: list[str] | None = None,
    summary_builder: SummaryBuilder | None = None,
) -> ToolLogger:
    """Decorator to log tool invocations with consistent formatting."""
    return ToolLogger(tool_name, log_params, summary_builder)
