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

from cisco_meraki_mcp.contracts.execute import ExecuteData
from cisco_meraki_mcp.factories.execute_result import ExecuteResult
from cisco_meraki_mcp.models.endpoint import EndpointMetadata, EndpointScope


class FailingProductClassifier:
    @staticmethod
    def classify(endpoint: EndpointMetadata) -> str:
        raise AssertionError("error results should not classify products")


@pytest.fixture
def wireless_endpoint(endpoint_factory) -> EndpointMetadata:
    return endpoint_factory(
        operation_id="getNetworkWirelessSsids",
        path="/networks/{networkId}/wireless/ssids",
        tags=["wireless"],
        scope=EndpointScope.NETWORK,
    )


def test_success_uses_injected_classifier(
    product_classifier,
    wireless_endpoint,
):
    factory = ExecuteResult(
        capability_id="getNetworkWirelessSsids",
        product_classifier=product_classifier,
    )

    data = ExecuteData.model_validate({"id": "S_1"})
    output = factory.success(endpoint=wireless_endpoint, data=data)

    assert output.type == "success"
    assert output.capability_id == "getNetworkWirelessSsids"
    assert output.product == "wireless"
    assert output.data.model_dump() == {"id": "S_1"}


def test_error_carries_capability_id_from_factory_state():
    factory = ExecuteResult(
        capability_id="getNetwork",
        product_classifier=FailingProductClassifier(),
    )

    err = factory.error(error="boom", recovery_suggestion="retry")

    assert err.type == "error"
    assert err.error == "boom"
    assert err.recovery_suggestion == "retry"
    assert err.capability_id == "getNetwork"
