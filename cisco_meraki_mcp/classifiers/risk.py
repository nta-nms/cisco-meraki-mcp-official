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
"""Risk-tier classification strategies.

Defines the `RiskClassifier` Protocol and the default
`HttpMethodRiskClassifier` implementation. Alternative strategies
(e.g. config-driven, per-tenant overrides) can be plugged in by
implementing the same Protocol without touching call sites.
"""

from typing import ClassVar, Protocol

from cisco_meraki_mcp.contracts.common import RiskTier
from cisco_meraki_mcp.models.endpoint import EndpointMetadata


class RiskClassifier(Protocol):
    """Strategy interface for assigning a `RiskTier` to an endpoint."""

    def classify(self, endpoint: EndpointMetadata) -> RiskTier:
        """Return the risk tier for `endpoint`."""
        ...


class HttpMethodRiskClassifier:
    """Default strategy: derive risk tier from HTTP method.

    GET maps to SAFE; POST/PUT/PATCH map to ELEVATED; DELETE maps to
    DESTRUCTIVE; anything else falls through to UNKNOWN.
    """

    _METHOD_TO_RISK: ClassVar[dict[str, RiskTier]] = {
        "GET": RiskTier.SAFE,
        "POST": RiskTier.ELEVATED,
        "PUT": RiskTier.ELEVATED,
        "PATCH": RiskTier.ELEVATED,
        "DELETE": RiskTier.DESTRUCTIVE,
    }

    def classify(self, endpoint: EndpointMetadata) -> RiskTier:
        return self._METHOD_TO_RISK.get(
            endpoint.method.upper(),
            RiskTier.UNKNOWN,
        )
