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
"""Production resources for the MCP server."""

import json
from importlib.metadata import version

SERVER_NAME = "network-platform-cloud-mcp"
DISTRIBUTION_NAME = "cisco-meraki-mcp"
SERVER_INSTRUCTIONS = (
    "Only perform read operations. Deny requests for create, update, delete, "
    "reboot, or other state-changing operations. Do not attempt alternative "
    "means to achieve a non-read operation without explicit user approval. "
    'Call execute_api directly with capability_id="getOrganizations" to '
    "discover accessible organization IDs. Call execute_api directly with "
    'capability_id="getOrganizationNetworks" after selecting an '
    "organization to discover its network IDs. For all other operations, use "
    "semantic_search to discover the relevant Meraki Dashboard API "
    "capability, then call execute_api with the selected capability_id and "
    "required parameters. For paginated API operations, execute_api returns "
    "one page only. Request a bounded page size when supported; do not pass "
    "total_pages or claim the result represents the complete dataset."
)


def service_info() -> str:
    metadata = {
        "name": SERVER_NAME,
        "version": version(DISTRIBUTION_NAME),
        "description": (
            "FastMCP server providing semantic search and execution "
            "of Meraki API endpoints."
        ),
    }
    return json.dumps(metadata)
