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
from cisco_meraki_mcp.classifiers.product import TagBasedProductClassifier


def test_picks_first_known_tag(endpoint_factory):
    classifier = TagBasedProductClassifier()
    endpoint = endpoint_factory(tags=["wireless", "configure"])

    assert classifier.classify(endpoint) == "wireless"


def test_skips_unknown_tags_until_known_one(endpoint_factory):
    classifier = TagBasedProductClassifier()
    endpoint = endpoint_factory(tags=["configure", "switch"])

    assert classifier.classify(endpoint) == "switch"


def test_falls_back_to_common_when_no_known_tag(endpoint_factory):
    classifier = TagBasedProductClassifier()
    endpoint = endpoint_factory(tags=["configure"])

    assert classifier.classify(endpoint) == "common"


def test_falls_back_to_common_with_empty_tags(endpoint_factory):
    classifier = TagBasedProductClassifier()
    endpoint = endpoint_factory(tags=[])

    assert classifier.classify(endpoint) == "common"
