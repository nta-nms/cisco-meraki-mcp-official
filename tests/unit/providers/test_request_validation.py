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

from cisco_meraki_mcp.providers.request_validation import (
    RequestValidationError,
    looks_like_traversal,
    reject_total_pages_parameter,
    reject_traversal_parameters,
    require_get_operation,
)


def _named(name):
    def operation():
        return None

    operation.__name__ = name
    return operation


def test_require_get_operation_allows_get_method():
    assert require_get_operation(_named("getNetwork")) is None


@pytest.mark.parametrize(
    "name",
    ["createNetwork", "updateNetwork", "deleteNetwork", "claimDevices"],
)
def test_require_get_operation_rejects_non_get_method(name):
    with pytest.raises(RequestValidationError) as exc_info:
        require_get_operation(_named(name))

    assert exc_info.value.error == "Only GET (read) operations are supported."
    assert exc_info.value.recovery_suggestion


def test_reject_total_pages_parameter_returns_none_when_total_pages_absent():
    assert reject_total_pages_parameter({"networkId": "N_1"}) is None


def test_reject_total_pages_parameter_raises_error_when_total_pages_present():
    with pytest.raises(RequestValidationError) as exc_info:
        reject_total_pages_parameter({"total_pages": "all"})

    assert exc_info.value.error == "Multi-page fetching is not supported."
    assert "total_pages" in exc_info.value.recovery_suggestion


def test_reject_traversal_parameters_allows_safe_values():
    assert reject_traversal_parameters({"path": "folder/name"}) is None


@pytest.mark.parametrize(
    "value",
    [
        "../../admin",
        "net/../admin",
        "%2e%2e%2fadmin",
        "net/%2e%2e/admin",
        "..%5cadmin",
    ],
)
def test_reject_traversal_parameters_rejects_traversal_values(value):
    with pytest.raises(RequestValidationError) as exc_info:
        reject_traversal_parameters({"networkId": value})

    assert exc_info.value.error == (
        "Parameter 'networkId' contains a disallowed path value."
    )
    assert value not in exc_info.value.error
    assert value not in exc_info.value.recovery_suggestion


def test_reject_traversal_parameters_ignores_non_string_values():
    assert reject_traversal_parameters({"page": 2, "enabled": True}) is None


def test_looks_like_traversal_detects_encoded_backslash_segment():
    assert looks_like_traversal("..%5cadmin") is True


def test_looks_like_traversal_allows_slash_bearing_value():
    assert looks_like_traversal("https://example.com/a/b") is False
