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

"""Construction seam selecting the concrete service implementation.

``build_service`` is the single place that names the concrete
:class:`~cisco_meraki_mcp.mcp_service.MCPService` and its
constructor arguments, so the entrypoint stays agnostic about what it runs.
"""

from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from importlib.metadata import version
from typing import Any

from fastmcp import FastMCP

from cisco_meraki_mcp.cisco_meraki_mcp import CiscoMerakiMCP
from cisco_meraki_mcp.resources import (
    DISTRIBUTION_NAME,
    SERVER_INSTRUCTIONS,
    SERVER_NAME,
)

Lifespan = Callable[[FastMCP], AbstractAsyncContextManager[Any]]


def build_service(
    *,
    lifespan: Lifespan | None,
    runtime_transport: str | None,
) -> CiscoMerakiMCP:
    """Construct the MCP service."""
    return CiscoMerakiMCP(
        SERVER_NAME,
        instructions=SERVER_INSTRUCTIONS,
        version=version(DISTRIBUTION_NAME),
        lifespan=lifespan,
    )
