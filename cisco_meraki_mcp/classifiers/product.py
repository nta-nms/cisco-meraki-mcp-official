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
"""Product-scope classification strategies.

Defines the `ProductClassifier` Protocol and the default
`TagBasedProductClassifier` implementation that picks the first
known Meraki product tag from an endpoint's tag list.
"""

from typing import ClassVar, Protocol

from cisco_meraki_mcp.models.endpoint import EndpointMetadata


class ProductClassifier(Protocol):
    """Strategy interface for assigning a product scope to an endpoint."""

    def classify(self, endpoint: EndpointMetadata) -> str:
        """Return the product scope for `endpoint`."""
        ...


class TagBasedProductClassifier:
    """Default strategy: pick the first known product tag.

    Falls back to `"common"` when no tag matches.
    """

    _KNOWN_PRODUCTS: ClassVar[frozenset[str]] = frozenset({
        "wireless",
        "switch",
        "appliance",
        "camera",
        "cellularGateway",
        "sensor",
        "sm",
        "insight",
    })
    _FALLBACK: ClassVar[str] = "common"

    def classify(self, endpoint: EndpointMetadata) -> str:
        return next(
            (tag for tag in endpoint.tags if tag in self._KNOWN_PRODUCTS),
            self._FALLBACK,
        )
