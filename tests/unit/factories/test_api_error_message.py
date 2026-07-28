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

from cisco_meraki_mcp.factories.api_error_message import ApiErrorMessage


@pytest.mark.parametrize(
    ("status", "expected_error", "expected_recovery"),
    [
        (
            400,
            "Invalid parameters for getNetworkWirelessSsids.",
            "Verify the parameter values with semantic_search.",
        ),
        (
            401,
            "Authentication failed.",
            "The provided API key is invalid or expired.",
        ),
        (
            403,
            "Access denied.",
            "This API key lacks permission for getNetworkWirelessSsids.",
        ),
        (
            404,
            "Resource not found.",
            "Verify the organization, network, or device identifier.",
        ),
        (
            429,
            "Meraki API rate limit reached.",
            "Try again shortly.",
        ),
    ],
)
def test_known_status_maps_to_guidance(
    status,
    expected_error,
    expected_recovery,
):
    message = ApiErrorMessage(
        status=status,
        operation_id="getNetworkWirelessSsids",
    )

    assert message.error_message == expected_error
    assert message.recovery_suggestion == expected_recovery


@pytest.mark.parametrize("status", [418, 500, 503])
def test_unknown_status_falls_back_to_unavailable(status):
    message = ApiErrorMessage(
        status=status,
        operation_id="getNetworkWirelessSsids",
    )

    assert message.error_message == "Meraki API is temporarily unavailable."
    assert message.recovery_suggestion == "Try again shortly."
