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
"""Validation guards for outbound SDK requests.

Enforce the read-only (GET) boundary, reject unsupported multi-page fetches,
and reject path-traversal-looking parameters. Each deliberate reject raises
`RequestValidationError`.
"""

from collections.abc import Awaitable, Callable
from typing import Any
from urllib.parse import unquote

# A bound async SDK method (e.g. `organizations.getOrganizationNetworks`).
# The SDK annotates neither parameters nor results, so parameters stay open
# (`...`) and the awaited result is `object` rather than `Any` to keep
# checking on at call sites.
SdkOperation = Callable[..., Awaitable[object]]


class RequestValidationError(Exception):
    """A deliberate, caller-fixable rejection of an outbound SDK request.

    Carries a caller-safe summary and recovery suggestion so execute_api can
    render a helpful ExecuteError without leaking raw SDK or caller-supplied
    parameter values. It keeps policy rejections distinct from incidental
    SDK `ValueError`.
    """

    def __init__(self, *, error: str, recovery_suggestion: str) -> None:
        super().__init__(error)
        self.error = error
        self.recovery_suggestion = recovery_suggestion


def require_get_operation(operation_method: SdkOperation) -> None:
    """Reject non-read SDK operations.

    The Meraki SDK names every read endpoint `getXxx` while mutating
    endpoints use `createXxx`/`updateXxx`/`deleteXxx` or action verbs
    (`claimNetworkDevices`, `bindNetwork`). None of the mutating methods
    start with `get`, so a `get` prefix allowlist admits only reads and
    keeps POST/PUT/DELETE out of this read-only client.

    Raises:
        RequestValidationError: Non-GET operation.
    """
    operation_name = getattr(operation_method, "__name__", "")
    if not operation_name.startswith("get"):
        raise RequestValidationError(
            error="Only GET (read) operations are supported.",
            recovery_suggestion=(
                "Choose a read capability whose id starts with 'get'."
            ),
        )


def reject_total_pages_parameter(params: dict[str, Any]) -> None:
    """Reject unsupported multi-page fetch requests.

    The SDK accepts `total_pages` to auto-fetch multiple pages; this client
    returns only the first page to avoid bloating agent context and stalling
    on large orgs.

    Raises:
        RequestValidationError: If `total_pages` is present.
    """
    if "total_pages" in params:
        raise RequestValidationError(
            error="Multi-page fetching is not supported.",
            recovery_suggestion=(
                "Remove the 'total_pages' parameter; one page is returned."
            ),
        )


def reject_traversal_parameters(params: dict[str, Any]) -> None:
    """Reject parameters containing decoded parent-directory segments.

    Raises:
        RequestValidationError: If a string value decodes to a `..` segment.
    """
    for key, value in params.items():
        if isinstance(value, str) and looks_like_traversal(value):
            raise RequestValidationError(
                error=(f"Parameter {key!r} contains a disallowed path value."),
                recovery_suggestion=(
                    "Correct the parameter value and try again."
                ),
            )


def looks_like_traversal(value: str) -> bool:
    decoded = unquote(value).replace("\\", "/")
    return any(segment == ".." for segment in decoded.split("/"))
