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
from pydantic import Field, ValidationError

from cisco_meraki_mcp.contracts.common import StrictModel


class Sample(StrictModel):
    name: str = Field(description="x")


def test_strict_model_forbids_extra_fields():
    with pytest.raises(ValidationError):
        Sample(name="ok", extra="boom")


def test_strict_model_is_frozen():
    sample = Sample(name="ok")

    with pytest.raises(ValidationError):
        sample.name = "changed"
