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
"""Shared primitives for tool contracts.

Holds cross-cutting types depended on by every tool contract module.
Behavior-free by design so the public surface stays composable.
"""

from enum import StrEnum

from pydantic import BaseModel, ConfigDict


class RiskTier(StrEnum):
    """Capability safety classification.

    Concrete classifier strategies live in
    `cisco_meraki_mcp.classifiers`; this enum is the
    vocabulary they share with consumers.
    """

    SAFE = "safe"
    ELEVATED = "elevated"
    DESTRUCTIVE = "destructive"
    UNKNOWN = "unknown"


class StrictModel(BaseModel):
    """Base for tool contracts: frozen, forbid extras, public surface."""

    model_config = ConfigDict(frozen=True, extra="forbid")
