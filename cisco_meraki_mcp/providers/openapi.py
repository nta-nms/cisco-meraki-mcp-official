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
"""OpenAPI specification parser for Meraki API."""

import gzip
import json
import logging
from pathlib import Path

from openapi_pydantic.v3.v3_0 import (
    OpenAPI,
    Operation,
    Parameter,
    PathItem,
    Reference,
    Schema,
)

from cisco_meraki_mcp.models.endpoint import (
    EndpointMetadata,
    EndpointParameter,
    EndpointScope,
)

logger = logging.getLogger(__name__)

SCOPE_PREFIXES = (
    ("/organizations/{organizationId}", EndpointScope.ORGANIZATION),
    ("/networks/{networkId}", EndpointScope.NETWORK),
    ("/devices/{serial}", EndpointScope.DEVICE),
    ("/administered", EndpointScope.ADMINISTERED),
)

ALLOWED_PARAM_LOCATIONS = ("path", "query")
DEFAULT_PARAM_TYPE = "string"

OAUTH2_SCHEME = "oauth2"
DISALLOW_ALL_SCOPE = "-"


def scopes_from_entry(entry: dict[str, list[str]]) -> set[str]:
    """Return the contributing scopes from one OpenAPI security entry.

    `-` collapses to an empty contribution (explicit "no scope required").
    `*` is preserved as a sentinel when no `-` is present.
    """
    scopes = set((entry or {}).get(OAUTH2_SCHEME) or [])

    if DISALLOW_ALL_SCOPE in scopes:
        return set()

    return scopes


def extract_required_scopes(operation: Operation) -> frozenset[str]:
    """Read `security` from an OpenAPI 3 operation as a flat scope set.

    Semantics mirror manage's `Api::Docs::OauthScopes.parse`
    (`app/lib/api/docs/oauth_scopes.rb`): non-oauth2 schemes are ignored,
    multiple oauth2 entries are unioned, `*` is preserved as an allow-any
    sentinel, and `-` collapses to empty.
    """
    security = operation.security or []
    collected: set[str] = set()
    for entry in security:
        collected.update(scopes_from_entry(entry))

    return frozenset(collected)


def detect_scope(path: str) -> EndpointScope:
    """Detect endpoint scope from path pattern.

    Args:
        path: API endpoint path.

    Returns:
        EndpointScope based on path prefix.
    """
    for prefix, scope in SCOPE_PREFIXES:
        if path.startswith(prefix):
            return scope

    return EndpointScope.GLOBAL


def schema_type(schema: Schema | Reference | None) -> str:
    """Return the parameter type name from a Schema, or the default.

    Reference schemas, missing types, and 3.1-style list types fall back
    to `DEFAULT_PARAM_TYPE` because the Meraki spec does not use them
    and downstream consumers expect a single string.
    """
    if not isinstance(schema, Schema):
        return DEFAULT_PARAM_TYPE

    if schema.type is None or isinstance(schema.type, list):
        return DEFAULT_PARAM_TYPE

    return getattr(schema.type, "value", str(schema.type))


def build_parameter(
    param: Parameter | Reference,
) -> EndpointParameter | None:
    """Convert one OpenAPI parameter into an EndpointParameter.

    Returns `None` for `$ref` parameters and for parameters not declared
    in `path` or `query` so callers can filter them out.
    """
    if not isinstance(param, Parameter):
        return None

    location = getattr(param.param_in, "value", str(param.param_in))
    if location not in ALLOWED_PARAM_LOCATIONS:
        return None

    return EndpointParameter(
        name=param.name,
        location=location,
        required=bool(param.required),
        type=schema_type(param.param_schema),
        description=param.description or "",
    )


def extract_parameters(
    operation: Operation,
    path_item: PathItem,
) -> list[EndpointParameter]:
    """Extract path and query parameters from an operation.

    Args:
        operation: OpenAPI Operation model.
        path_item: OpenAPI PathItem model (may carry shared parameters).

    Returns:
        List of EndpointParameter objects. `$ref` parameters and any
        parameter not declared in `path` or `query` are skipped.
    """
    all_params = list(path_item.parameters or []) + list(
        operation.parameters or []
    )

    parameters: list[EndpointParameter] = []
    for param in all_params:
        endpoint_param = build_parameter(param)
        if endpoint_param is None:
            continue

        parameters.append(endpoint_param)

    return parameters


def build_endpoint(
    path: str,
    operation: Operation,
    path_item: PathItem,
) -> EndpointMetadata | None:
    """Build endpoint metadata from an OpenAPI path item."""
    if not operation.operationId:
        logger.warning("Skipping endpoint without operationId: %s", path)
        return None

    return EndpointMetadata(
        operation_id=operation.operationId,
        method="GET",
        path=path,
        summary=operation.summary or "",
        description=operation.description or "",
        tags=list(operation.tags or []),
        parameters=extract_parameters(operation, path_item),
        scope=detect_scope(path),
        required_scopes=extract_required_scopes(operation),
    )


def collect_get_operations(
    paths: dict[str, PathItem],
) -> list[tuple[str, Operation, PathItem]]:
    """Collect non-deprecated GET operations from an OpenAPI paths mapping."""
    operations: list[tuple[str, Operation, PathItem]] = []

    for path, path_item in paths.items():
        if path_item.get is None or path_item.get.deprecated:
            continue

        operations.append((path, path_item.get, path_item))

    return operations


def load_spec(spec_path: Path) -> OpenAPI:
    """Read a JSON OpenAPI spec from disk and validate it as OpenAPI 3.0.

    Raises:
        pydantic.ValidationError: If the spec does not conform to
            OpenAPI 3.0. Surfaced intentionally so malformed upstream
            specs fail loudly instead of yielding zero endpoints.
    """
    logger.info("Loading OpenAPI spec from %s", spec_path)

    if spec_path.suffix == ".gz":
        with gzip.open(spec_path, "rt") as f:
            raw_spec = json.load(f)
    else:
        with spec_path.open() as f:
            raw_spec = json.load(f)

    return OpenAPI.model_validate(raw_spec)


def parse_openapi_spec(spec: OpenAPI) -> list[EndpointMetadata]:
    """Extract GET endpoints from a validated OpenAPI spec.

    Pure function: takes an already-loaded `OpenAPI` model so callers can
    test parsing without touching the filesystem. Use `load_spec` to read
    a JSON file from disk and produce the input model.

    Args:
        spec: Validated OpenAPI 3.0 model.

    Returns:
        List of EndpointMetadata for GET endpoints.
    """
    endpoints: list[EndpointMetadata] = []
    for path, operation, path_item in collect_get_operations(spec.paths or {}):
        endpoint = build_endpoint(path, operation, path_item)
        if endpoint is None:
            continue

        endpoints.append(endpoint)

    logger.info("Parsed %d GET endpoints from OpenAPI spec", len(endpoints))
    return endpoints


def load_meraki_endpoints(spec_path: str | Path) -> list[EndpointMetadata]:
    """Load and parse Meraki OpenAPI spec.

    Args:
        spec_path: Path to Meraki OpenAPI spec file.

    Returns:
        List of EndpointMetadata for GET endpoints.

    Raises:
        FileNotFoundError: If spec file doesn't exist.
        json.JSONDecodeError: If spec file is invalid JSON.
        pydantic.ValidationError: If the spec does not conform to
            OpenAPI 3.0.
    """
    path = Path(spec_path)

    if not path.exists():
        raise FileNotFoundError(f"Meraki OpenAPI spec not found at {path}")

    return parse_openapi_spec(load_spec(path))
