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
"""Adapter from internal `EndpointMetadata` to public `SearchResult`.

Sole construction site for `SearchResult`. Risk and product scope
are delegated to injected `RiskClassifier` / `ProductClassifier`
strategies so callers can swap classification policies without
touching the contract module.
"""

from cisco_meraki_mcp.classifiers.product import ProductClassifier
from cisco_meraki_mcp.classifiers.risk import RiskClassifier
from cisco_meraki_mcp.contracts.search import RequiredParameter, SearchResult
from cisco_meraki_mcp.models.endpoint import (
    EndpointMetadata,
    EndpointParameter,
)


def intent_for_endpoint(endpoint: EndpointMetadata) -> str:
    return endpoint.summary or endpoint.description or endpoint.operation_id


def to_required_parameter(parameter: EndpointParameter) -> RequiredParameter:
    """Project an `EndpointParameter` onto the public typed model."""
    return RequiredParameter(
        name=parameter.name,
        location=parameter.location,
        required=parameter.required,
        type=parameter.param_type,
        description=parameter.description,
    )


def build_search_result(
    endpoint: EndpointMetadata,
    *,
    risk_classifier: RiskClassifier,
    product_classifier: ProductClassifier,
) -> SearchResult:
    """Build a `SearchResult` from `endpoint` using the strategies."""
    return SearchResult(
        capability_id=endpoint.operation_id,
        intent=intent_for_endpoint(endpoint),
        product_scope=product_classifier.classify(endpoint),
        risk_tier=risk_classifier.classify(endpoint),
        tags=list(endpoint.tags),
        required_parameters=[
            to_required_parameter(p) for p in endpoint.parameters if p.required
        ],
    )
