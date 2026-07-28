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
"""Builder for `execute_api` response variants.

Encapsulates the wiring between an `EndpointMetadata` (when
available) and the public success/error contract types so callers
construct typed responses through one place per variant. The
`capability_id` and `product_classifier` are lifted to instance
state because they are stable across both the success and error
paths for a single tool invocation.
"""

from cisco_meraki_mcp.classifiers.product import ProductClassifier
from cisco_meraki_mcp.contracts.execute import (
    ExecuteData,
    ExecuteError,
    ExecuteReadOutput,
)
from cisco_meraki_mcp.models.endpoint import EndpointMetadata


class ExecuteResult:
    """Typed-result builder bound to a single `capability_id`."""

    def __init__(
        self,
        *,
        capability_id: str,
        product_classifier: ProductClassifier,
    ) -> None:
        self._capability_id = capability_id
        self._product_classifier = product_classifier

    def success(
        self,
        *,
        endpoint: EndpointMetadata,
        data: ExecuteData,
    ) -> ExecuteReadOutput:
        """Build an `ExecuteReadOutput` for a resolved capability."""
        return ExecuteReadOutput(
            capability_id=self._capability_id,
            product=self._product_classifier.classify(endpoint),
            data=data,
        )

    def error(
        self,
        *,
        error: str,
        recovery_suggestion: str,
    ) -> ExecuteError:
        """Build an `ExecuteError` for a failure path."""
        return ExecuteError(
            error=error,
            recovery_suggestion=recovery_suggestion,
            capability_id=self._capability_id,
        )
