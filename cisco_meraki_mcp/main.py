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
"""Network Platform Cloud MCP Server.

FastMCP server providing semantic search and execution of Meraki API endpoints.
"""

import argparse
import logging
import os
import sys
from importlib import resources
from pathlib import Path
from typing import Any

from cisco_meraki_mcp.cisco_meraki_mcp import CiscoMerakiMCP
from cisco_meraki_mcp.config.settings import MCP_PATH, Settings, get_settings
from cisco_meraki_mcp.conformance import conformance_profile_enabled
from cisco_meraki_mcp.index_builder import IndexBuilder
from cisco_meraki_mcp.index_state import IndexState
from cisco_meraki_mcp.providers.openapi import load_meraki_endpoints
from cisco_meraki_mcp.providers.vector_store import InMemoryVectorStore
from cisco_meraki_mcp.service_factory import build_service

logger = logging.getLogger(__name__)
TRANSPORT_CHOICES = ("stdio", "streamable-http")


def logging_level_from_env() -> int:
    """Return the configured log level from `LOG_LEVEL` (defaults to INFO).

    Lets operators change the level from the environment instead of
    requiring a code change. Unknown values
    fall back to INFO rather than raising so a typo cannot brick the
    bootstrap path.
    """
    log_level = os.environ.get("LOG_LEVEL", "INFO").upper()

    return logging.getLevelNamesMapping().get(log_level, logging.INFO)


def configure_logging() -> None:
    """Configure the root logger for the MCP server bootstrap.

    Routes records to stderr so stdout stays reserved for the MCP
    protocol, and quiets uvicorn's access/server loggers. Called from
    `main()` rather than at import time so importing this module in
    tests does not mutate global state.

    This is application bootstrap logging, distinct from the per-tool
    invocation logging utilities in
    `cisco_meraki_mcp.tools.logging`,
    which handle request-id correlation and parameter redaction inside
    individual MCP tool calls.
    """
    logging.basicConfig(
        level=logging_level_from_env(),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[logging.StreamHandler(sys.stderr)],
    )

    logging.getLogger("uvicorn").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)


def create_app(
    spec_path: Path | None = None,
    *,
    state: IndexState | None = None,
    runtime_transport: str | None = None,
) -> CiscoMerakiMCP:
    """Create and configure the FastMCP application.

    Owns the single `IndexState` instance for this process and passes it to
    `IndexBuilder`. The vector-store index is built asynchronously by
    `IndexBuilder.lifespan` so the server starts accepting requests within
    seconds of process start, well before the endpoint embedding pass
    completes.

    `state` is exposed as an optional kwarg so tests can construct
    an `IndexState` they control and observe (e.g. via
    `wait_for_status(state, IndexStatus.READY)`) instead of reading
    it back through a module global. Production callers omit the
    kwarg and get a fresh `IndexState`.
    """
    state = state or IndexState()

    builder = IndexBuilder(
        lambda: initialize_vector_store(spec_path),
        state=state,
    )
    app = build_service(
        lifespan=builder.lifespan,
        runtime_transport=runtime_transport,
    )
    app.register_core_capabilities(state, runtime_transport=runtime_transport)

    return app


def bundled_spec_path() -> Path:
    """On-disk path to the gzipped Meraki spec bundled with the package."""
    return Path(
        str(
            resources.files("cisco_meraki_mcp").joinpath(
                "specs", "meraki.json.gz"
            )
        )
    )


def initialize_vector_store(
    spec_path: Path | None = None,
) -> InMemoryVectorStore:
    """Initialize the vector store with Meraki endpoints."""
    settings = get_settings()
    path = spec_path or bundled_spec_path()
    logger.info("Loading Meraki endpoints from %s", path)
    endpoints = load_meraki_endpoints(path)
    logger.info("Initializing vector store with %d endpoints", len(endpoints))
    store = InMemoryVectorStore(model_name=settings.embedding_model)
    store.add_endpoints(endpoints)
    return store


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments for the server entrypoint."""
    parser = argparse.ArgumentParser(
        description="Run the Network Platform Cloud MCP server.",
    )
    parser.add_argument(
        "--transport",
        choices=TRANSPORT_CHOICES,
        default=None,
        help="FastMCP transport to use.",
    )
    parser.add_argument(
        "--host",
        default=None,
        help="Host to bind for HTTP transports.",
    )
    parser.add_argument(
        "--port",
        default=None,
        type=int,
        help="Port to bind for HTTP transports.",
    )
    return parser.parse_args(argv)


def log_startup(settings: Settings, transport: str) -> None:
    """Log startup settings for the MCP server."""
    logger.info("=" * 60)
    logger.info("Network Platform Cloud MCP Server")
    logger.info("=" * 60)
    logger.info("Transport: %s", transport)
    logger.info("Host: %s", settings.mcp_host)
    logger.info("Port: %s", settings.mcp_port)
    logger.info("Path: %s", MCP_PATH)
    logger.info("Embedding model: %s", settings.embedding_model)
    logger.info("=" * 60)


def http_run_kwargs(
    settings: Settings,
    *,
    host: str | None,
    port: int | None,
) -> dict[str, Any]:
    """Build FastMCP HTTP transport run options."""
    run_kwargs: dict[str, Any] = {
        "port": port if port is not None else settings.mcp_port,
        "path": MCP_PATH,
        "stateless_http": True,
    }
    if host or settings.mcp_host:
        run_kwargs["host"] = host or settings.mcp_host

    return run_kwargs


def server_run_kwargs(
    settings: Settings,
    *,
    transport: str,
    host: str | None,
    port: int | None,
) -> dict[str, Any]:
    """Build FastMCP `run()` options for the selected transport."""
    run_kwargs: dict[str, Any] = {
        "transport": transport,
        "show_banner": False,
    }
    if transport != "stdio":
        run_kwargs.update(http_run_kwargs(settings, host=host, port=port))

    return run_kwargs


def run_server(
    *,
    transport: str = "stdio",
    host: str | None = None,
    port: int | None = None,
) -> None:
    """Create and run the FastMCP application."""
    settings = get_settings()
    logger.info("Starting MCP server...")
    app = create_app(runtime_transport=transport)
    run_kwargs = server_run_kwargs(
        settings,
        transport=transport,
        host=host,
        port=port,
    )

    try:
        app.run(**run_kwargs)
    finally:
        app.shutdown()


def handle_missing_spec(error: FileNotFoundError) -> None:
    """Handle startup failure when the Meraki spec is missing."""
    logger.exception("Failed to load Meraki spec: %s", error)
    sys.exit(1)


def handle_startup_failure() -> None:
    """Handle generic startup failures."""
    logger.exception("Failed to start server")
    sys.exit(1)


def start_from_args(args: argparse.Namespace) -> None:
    """Start the server from parsed command-line arguments."""
    settings = get_settings()
    transport = (
        "streamable-http"
        if conformance_profile_enabled()
        else args.transport or settings.mcp_transport
    )
    log_startup(settings, transport)
    run_server(
        transport=transport,
        host=args.host,
        port=args.port,
    )


def main(argv: list[str] | None = None) -> None:
    """Entry point for the MCP server."""
    configure_logging()

    try:
        start_from_args(parse_args(argv))
    except FileNotFoundError as e:
        handle_missing_spec(e)
    except OSError, RuntimeError, ValueError:
        handle_startup_failure()


if __name__ == "__main__":
    main()
