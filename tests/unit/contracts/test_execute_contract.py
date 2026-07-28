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
from pydantic import ValidationError

from cisco_meraki_mcp.contracts.execute import (
    ExecuteData,
    ExecuteError,
    ExecuteReadInput,
    ExecuteReadOutput,
)


def test_execute_read_input_parameters_accepts_primitive_value_union():
    payload = ExecuteReadInput(
        capability_id="getNetwork",
        parameters={"name": "n", "count": 3, "enabled": True},
    )

    assert payload.parameters == {"name": "n", "count": 3, "enabled": True}


@pytest.mark.parametrize(
    ("key", "bad_value"),
    [
        ("vals", [1, 2]),
        ("nested", {"a": 1}),
    ],
    ids=["list", "nested_dict"],
)
def test_execute_read_input_parameters_rejects_non_primitive(key, bad_value):
    with pytest.raises(ValidationError) as exc_info:
        ExecuteReadInput(
            capability_id="getNetwork",
            parameters={key: bad_value},
        )

    parameter_errors = [
        e
        for e in exc_info.value.errors()
        if e["loc"][:2] == ("parameters", key)
    ]

    assert parameter_errors
    assert {e["type"] for e in parameter_errors} == {
        "string_type",
        "int_type",
        "bool_type",
    }


def test_execute_data_preserves_extra_fields_round_trip():
    payload = {"id": "N_1", "name": "Mock"}
    data = ExecuteData.model_validate(payload)

    assert data.model_dump() == payload


def test_execute_read_output_rejects_wrong_tag():
    with pytest.raises(ValidationError):
        ExecuteReadOutput(
            type="error",
            capability_id="x",
            product="common",
            data=ExecuteData(),
        )


def test_execute_read_output_requires_capability_id():
    with pytest.raises(ValidationError):
        ExecuteReadOutput(product="common", data=ExecuteData())


def test_execute_error_rejects_wrong_tag():
    with pytest.raises(ValidationError):
        ExecuteError(
            type="success",
            error="x",
            recovery_suggestion="y",
        )
