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
import json

from cisco_meraki_mcp.resources import SERVER_INSTRUCTIONS, service_info


def test_info_returns_service_metadata(mocker):
    mocked_version = mocker.patch(
        "cisco_meraki_mcp.resources.version",
        return_value="0.2.3",
    )

    result = json.loads(service_info())

    assert result["name"] == "network-platform-cloud-mcp"
    assert result["version"] == "0.2.3"
    mocked_version.assert_called_once_with("cisco-meraki-mcp")
    assert "description" in result


def test_server_instructions_enforce_read_only_boundary():
    assert "Only perform read operations." in SERVER_INSTRUCTIONS
    assert (
        "Deny requests for create, update, delete, reboot, or other "
        "state-changing operations." in SERVER_INSTRUCTIONS
    )


def test_server_instructions_require_approval_for_non_read_alternatives():
    assert (
        "Do not attempt alternative means to achieve a non-read operation "
        "without explicit user approval." in SERVER_INSTRUCTIONS
    )


def test_server_instructions_describe_identifier_discovery():
    assert (
        'Call execute_api directly with capability_id="getOrganizations" to '
        "discover accessible organization IDs." in SERVER_INSTRUCTIONS
    )
    assert (
        "Call execute_api directly with "
        'capability_id="getOrganizationNetworks" after selecting an '
        "organization to discover its network IDs." in SERVER_INSTRUCTIONS
    )


def test_server_instructions_preserve_read_and_pagination_flow():
    assert (
        "For all other operations, use semantic_search to discover the "
        "relevant Meraki Dashboard API capability, then call execute_api "
        "with the selected capability_id and required parameters."
        in SERVER_INSTRUCTIONS
    )
    assert (
        "For paginated API operations, execute_api returns one page only. "
        "Request a bounded page size when supported; do not pass total_pages "
        "or claim the result represents the complete dataset."
        in SERVER_INSTRUCTIONS
    )
