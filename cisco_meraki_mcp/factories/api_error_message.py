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
"""Meraki API status-code-to-message mapping.

Encapsulates the translation from a Meraki API status code into a
human-readable error and recovery suggestion. Bundling both strings
behind one object avoids passing a bare tuple around (primitive
obsession) and gives callers an explicit public interface.
"""


class ApiErrorMessage:
    """Map a Meraki API status code to an error and recovery hint."""

    def __init__(self, *, status: int, operation_id: str) -> None:
        self._status = status
        self._operation_id = operation_id

    def _messages(self) -> dict[int, tuple[str, str]]:
        return {
            400: (
                f"Invalid parameters for {self._operation_id}.",
                "Verify the parameter values with semantic_search.",
            ),
            401: (
                "Authentication failed.",
                "The provided API key is invalid or expired.",
            ),
            403: (
                "Access denied.",
                f"This API key lacks permission for {self._operation_id}.",
            ),
            404: (
                "Resource not found.",
                "Verify the organization, network, or device identifier.",
            ),
            429: (
                "Meraki API rate limit reached.",
                "Try again shortly.",
            ),
        }

    def _resolve(self) -> tuple[str, str]:
        return self._messages().get(
            self._status,
            (
                "Meraki API is temporarily unavailable.",
                "Try again shortly.",
            ),
        )

    @property
    def error_message(self) -> str:
        """The human-readable error for the status code."""
        return self._resolve()[0]

    @property
    def recovery_suggestion(self) -> str:
        """The recovery hint for the status code."""
        return self._resolve()[1]
