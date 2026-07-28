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

from cisco_meraki_mcp.classifiers.risk import HttpMethodRiskClassifier
from cisco_meraki_mcp.contracts.common import RiskTier


@pytest.mark.parametrize(
    ("method", "expected"),
    [
        ("GET", RiskTier.SAFE),
        ("get", RiskTier.SAFE),
        ("POST", RiskTier.ELEVATED),
        ("PUT", RiskTier.ELEVATED),
        ("PATCH", RiskTier.ELEVATED),
        ("DELETE", RiskTier.DESTRUCTIVE),
        ("HEAD", RiskTier.UNKNOWN),
        ("", RiskTier.UNKNOWN),
    ],
)
def test_http_method_risk_classifier(
    endpoint_factory,
    method: str,
    expected: RiskTier,
):
    classifier = HttpMethodRiskClassifier()

    assert classifier.classify(endpoint_factory(method=method)) == expected
