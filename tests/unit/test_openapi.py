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
import json
from pathlib import Path

import pytest
from openapi_pydantic.v3.v3_0 import OpenAPI, Operation
from pydantic import ValidationError

from cisco_meraki_mcp.models.endpoint import EndpointScope
from cisco_meraki_mcp.providers.openapi import (
    collect_get_operations,
    detect_scope,
    extract_required_scopes,
    load_meraki_endpoints,
    load_spec,
    parse_openapi_spec,
)


def make_operation(security):
    payload = {
        "operationId": "op",
        "responses": {"200": {"description": "OK"}},
    }

    if security is not None:
        payload["security"] = security

    return Operation.model_validate(payload)


def test_parse_openapi_spec_extracts_get_only(sample_openapi_spec: Path):
    endpoints = parse_openapi_spec(load_spec(sample_openapi_spec))

    assert len(endpoints) == 2

    operation_ids = [e.operation_id for e in endpoints]
    assert "getNetworkWirelessSsids" in operation_ids
    assert "getOrganizationDevices" in operation_ids
    assert "createNetworkWirelessSsid" not in operation_ids


def test_parse_openapi_spec_extracts_metadata(sample_openapi_spec: Path):
    endpoints = parse_openapi_spec(load_spec(sample_openapi_spec))

    ssid_endpoint = next(
        e for e in endpoints if e.operation_id == "getNetworkWirelessSsids"
    )

    assert ssid_endpoint.method == "GET"
    assert ssid_endpoint.path == "/networks/{networkId}/wireless/ssids"
    assert ssid_endpoint.summary == "List the MR SSIDs in a network"
    assert "wireless" in ssid_endpoint.tags


def test_parse_openapi_spec_extracts_parameters(sample_openapi_spec: Path):
    endpoints = parse_openapi_spec(load_spec(sample_openapi_spec))

    ssid_endpoint = next(
        e for e in endpoints if e.operation_id == "getNetworkWirelessSsids"
    )

    assert len(ssid_endpoint.parameters) == 1
    param = ssid_endpoint.parameters[0]
    assert param.name == "networkId"
    assert param.location == "path"
    assert param.required is True


def test_load_meraki_endpoints_file_not_found():
    with pytest.raises(FileNotFoundError) as exc_info:
        load_meraki_endpoints("/nonexistent/path/spec.json")

    assert "not found" in str(exc_info.value).lower()
    assert "/nonexistent/path/spec.json" in str(exc_info.value)


def test_load_meraki_endpoints_success(sample_openapi_spec: Path):
    endpoints = load_meraki_endpoints(sample_openapi_spec)

    assert len(endpoints) == 2
    assert all(e.method == "GET" for e in endpoints)


@pytest.mark.parametrize(
    ("path", "expected_scope"),
    [
        (
            "/organizations/{organizationId}/devices",
            EndpointScope.ORGANIZATION,
        ),
        ("/organizations/{organizationId}", EndpointScope.ORGANIZATION),
        ("/networks/{networkId}/devices", EndpointScope.NETWORK),
        ("/networks/{networkId}", EndpointScope.NETWORK),
        ("/devices/{serial}", EndpointScope.DEVICE),
        ("/devices/{serial}/clients", EndpointScope.DEVICE),
        ("/administered/identities/me", EndpointScope.ADMINISTERED),
        ("/administered/licensing/subscription", EndpointScope.ADMINISTERED),
        ("/organizations", EndpointScope.GLOBAL),
        ("/some/other/path", EndpointScope.GLOBAL),
    ],
)
def test_detect_scope(path: str, expected_scope: EndpointScope):
    assert detect_scope(path) == expected_scope


def test_parse_openapi_spec_skips_missing_operation_id(caplog):
    spec = OpenAPI.model_validate({
        "openapi": "3.0.0",
        "info": {"title": "Test API", "version": "1.0.0"},
        "paths": {
            "/test": {
                "get": {
                    "summary": "Test endpoint without operation ID",
                    "responses": {"200": {"description": "OK"}},
                }
            }
        },
    })

    endpoints = parse_openapi_spec(spec)

    assert len(endpoints) == 0
    assert "Skipping endpoint without operationId" in caplog.text


def test_parse_openapi_spec_skips_non_get_operations():
    spec = OpenAPI.model_validate({
        "openapi": "3.0.0",
        "info": {"title": "Test API", "version": "1.0.0"},
        "paths": {
            "/test": {
                "post": {
                    "operationId": "createTest",
                    "summary": "POST operation",
                    "responses": {"201": {"description": "Created"}},
                }
            }
        },
    })

    endpoints = parse_openapi_spec(spec)

    assert len(endpoints) == 0


def test_extract_parameters_filters_non_path_query_params():
    spec = OpenAPI.model_validate({
        "openapi": "3.0.0",
        "info": {"title": "Test API", "version": "1.0.0"},
        "paths": {
            "/test": {
                "get": {
                    "operationId": "test_op",
                    "summary": "Test",
                    "parameters": [
                        {
                            "name": "pathParam",
                            "in": "path",
                            "required": True,
                            "schema": {"type": "string"},
                        },
                        {
                            "name": "queryParam",
                            "in": "query",
                            "required": False,
                            "schema": {"type": "string"},
                        },
                        {
                            "name": "headerParam",
                            "in": "header",
                            "required": False,
                            "schema": {"type": "string"},
                        },
                        {
                            "name": "cookieParam",
                            "in": "cookie",
                            "required": False,
                            "schema": {"type": "string"},
                        },
                    ],
                    "responses": {"200": {"description": "OK"}},
                }
            }
        },
    })

    endpoints = parse_openapi_spec(spec)

    assert len(endpoints) == 1
    assert len(endpoints[0].parameters) == 2
    param_names = [p.name for p in endpoints[0].parameters]
    assert "pathParam" in param_names
    assert "queryParam" in param_names
    assert "headerParam" not in param_names
    assert "cookieParam" not in param_names


def test_extract_parameters_uses_default_type():
    spec = OpenAPI.model_validate({
        "openapi": "3.0.0",
        "info": {"title": "Test API", "version": "1.0.0"},
        "paths": {
            "/test": {
                "get": {
                    "operationId": "test_op",
                    "summary": "Test",
                    "parameters": [
                        {
                            "name": "param_no_schema",
                            "in": "query",
                            "required": False,
                        }
                    ],
                    "responses": {"200": {"description": "OK"}},
                }
            }
        },
    })

    endpoints = parse_openapi_spec(spec)

    assert len(endpoints) == 1
    assert endpoints[0].parameters[0].param_type == "string"


def test_load_spec_raises_on_invalid_spec(tmp_path: Path):
    bad_spec = tmp_path / "bad.json"
    bad_spec.write_text(json.dumps({"not": "a valid openapi document"}))

    with pytest.raises(ValidationError):
        load_spec(bad_spec)


def test_extract_parameters_skips_reference_parameters():
    spec = OpenAPI.model_validate({
        "openapi": "3.0.0",
        "info": {"title": "Test API", "version": "1.0.0"},
        "components": {
            "parameters": {
                "SharedParam": {
                    "name": "shared",
                    "in": "query",
                    "schema": {"type": "string"},
                }
            }
        },
        "paths": {
            "/test": {
                "get": {
                    "operationId": "test_op",
                    "summary": "Test",
                    "parameters": [
                        {"$ref": "#/components/parameters/SharedParam"},
                        {
                            "name": "direct",
                            "in": "query",
                            "schema": {"type": "string"},
                        },
                    ],
                    "responses": {"200": {"description": "OK"}},
                }
            }
        },
    })

    endpoints = parse_openapi_spec(spec)

    assert len(endpoints) == 1
    names = [p.name for p in endpoints[0].parameters]
    assert names == ["direct"]


@pytest.mark.parametrize(
    "security",
    [
        pytest.param(None, id="missing_security_key"),
        pytest.param([], id="empty_security_list"),
        pytest.param([{"oauth2": []}], id="empty_oauth2_scopes"),
        pytest.param([{"oauth2": ["-"]}], id="dash_collapses_to_empty"),
    ],
)
def test_extract_required_scopes_empty_equivalents(security):
    operation = make_operation(security)

    assert extract_required_scopes(operation) == frozenset()


def test_extract_required_scopes_named_scopes():
    operation = make_operation(
        [{"oauth2": ["camera:config:read", "camera:config:write"]}],
    )

    assert extract_required_scopes(operation) == frozenset({
        "camera:config:read",
        "camera:config:write",
    })


def test_extract_required_scopes_star_preserved():
    operation = make_operation([{"oauth2": ["*"]}])

    result = extract_required_scopes(operation)

    assert result == frozenset({"*"})


def test_extract_required_scopes_star_and_dash_same_entry_collapses_to_empty():
    operation = make_operation([{"oauth2": ["*", "-"]}])

    assert extract_required_scopes(operation) == frozenset()


def test_extract_required_scopes_multiple_entries_union():
    operation = make_operation([
        {"oauth2": ["a:read"]},
        {"oauth2": ["b:read"]},
    ])

    expected = frozenset({"a:read", "b:read"})
    assert extract_required_scopes(operation) == expected


def test_extract_required_scopes_ignores_non_oauth_schemes():
    operation = make_operation([
        {"meraki_api_key": []},
        {"oauth2": ["scope:x"]},
    ])

    assert extract_required_scopes(operation) == frozenset({"scope:x"})


def test_parse_openapi_spec_populates_required_scopes(
    sample_openapi_spec: Path,
):
    endpoints = parse_openapi_spec(load_spec(sample_openapi_spec))

    ssid = next(
        e for e in endpoints if e.operation_id == "getNetworkWirelessSsids"
    )
    org_devices = next(
        e for e in endpoints if e.operation_id == "getOrganizationDevices"
    )

    assert ssid.required_scopes == frozenset({"wireless:configure:read"})
    assert org_devices.required_scopes == frozenset()


def test_collect_get_operations_skips_deprecated():
    spec = OpenAPI.model_validate({
        "openapi": "3.0.0",
        "info": {"title": "Test API", "version": "1.0.0"},
        "paths": {
            "/active": {
                "get": {
                    "operationId": "getActive",
                    "summary": "Active endpoint",
                    "responses": {"200": {"description": "OK"}},
                }
            },
            "/deprecated": {
                "get": {
                    "operationId": "getDeprecated",
                    "deprecated": True,
                    "summary": "Deprecated endpoint",
                    "responses": {"200": {"description": "OK"}},
                }
            },
        },
    })

    operations = collect_get_operations(spec.paths or {})

    operation_ids = [op.operationId for _, op, _ in operations]
    assert "getActive" in operation_ids
    assert "getDeprecated" not in operation_ids


def test_parse_openapi_spec_excludes_deprecated(sample_openapi_spec: Path):
    endpoints = parse_openapi_spec(load_spec(sample_openapi_spec))

    operation_ids = [e.operation_id for e in endpoints]
    assert len(endpoints) == 2
    assert "getDeprecatedEndpoint" not in operation_ids
