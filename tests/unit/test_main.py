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
import asyncio
import logging
import threading
import time

import pytest
from fastmcp import Client, FastMCP

from cisco_meraki_mcp.index_builder import IndexBuilder
from cisco_meraki_mcp.index_state import IndexState, IndexStatus
from cisco_meraki_mcp.main import (
    bundled_spec_path,
    configure_logging,
    conformance_profile_enabled,
    create_app,
    initialize_vector_store,
    logging_level_from_env,
    main,
    parse_args,
    run_server,
)


@pytest.fixture
def mock_main_app(mocker):
    mock_app = mocker.MagicMock()
    mocker.patch(
        "cisco_meraki_mcp.main.create_app",
        return_value=mock_app,
    )
    return mock_app


@pytest.fixture
def mock_main_settings(mocker):
    mock_get_settings = mocker.patch("cisco_meraki_mcp.main.get_settings")
    mock_get_settings.return_value.mcp_transport = "stdio"
    mock_get_settings.return_value.mcp_host = None
    mock_get_settings.return_value.mcp_port = 8000
    mock_get_settings.return_value.mcp_allowed_host_set = frozenset()
    return mock_get_settings


def test_create_app_returns_fastmcp_instance():
    app = create_app()

    assert isinstance(app, FastMCP)


@pytest.mark.asyncio
async def test_create_app_registers_info_resource():
    app = create_app()

    resources = await app.list_resources()
    resource_uris = [str(r.uri) for r in resources]
    assert "info://service" in resource_uris


@pytest.mark.asyncio
async def test_info_resource_readable(skip_vector_store_init):
    app = create_app()

    async with Client(app) as client:
        resources = await client.list_resources()

        assert resources

        result = await client.read_resource(resources[0].uri)

        assert result


def test_conformance_profile_disabled_by_default(mocker):
    mocker.patch.dict("os.environ", {}, clear=True)

    assert conformance_profile_enabled() is False


def test_conformance_profile_enabled_when_set(mocker):
    mocker.patch.dict(
        "os.environ",
        {"MCP_CONFORMANCE_PROFILE": "true"},
    )

    assert conformance_profile_enabled() is True


def test_main_calls_run(mock_main_app, mock_main_settings):
    main([])

    assert mock_main_settings.called
    mock_main_app.run.assert_called_once_with(
        transport="stdio",
        show_banner=False,
    )


def test_run_server_passes_runtime_transport_to_app(
    mocker, mock_main_settings
):
    mock_app = mocker.MagicMock()
    mock_create_app = mocker.patch(
        "cisco_meraki_mcp.main.create_app",
        return_value=mock_app,
    )

    run_server(transport="streamable-http")

    mock_create_app.assert_called_once_with(
        runtime_transport="streamable-http"
    )


def test_run_server_shuts_down_app(mock_main_settings, mocker):
    mock_app = mocker.MagicMock()
    mocker.patch(
        "cisco_meraki_mcp.main.create_app",
        return_value=mock_app,
    )

    run_server()

    mock_app.shutdown.assert_called_once()


def test_run_server_shuts_down_app_on_error(mock_main_settings, mocker):
    mock_app = mocker.MagicMock()
    mock_app.run.side_effect = RuntimeError("boom")
    mocker.patch(
        "cisco_meraki_mcp.main.create_app",
        return_value=mock_app,
    )

    with pytest.raises(RuntimeError):
        run_server()

    mock_app.shutdown.assert_called_once()


def test_main_passes_streamable_http_options(
    mock_main_app, mock_main_settings
):
    mock_settings = mock_main_settings.return_value
    mock_settings.mcp_host = None
    mock_settings.mcp_port = 8000

    main(["--transport", "streamable-http"])

    mock_main_app.run.assert_called_once()
    call_kwargs = mock_main_app.run.call_args.kwargs
    assert "host" not in call_kwargs
    assert call_kwargs["port"] == 8000


def test_main_passes_cli_host_override_to_streamable_http(
    mock_main_app, mock_main_settings
):
    mock_settings = mock_main_settings.return_value
    mock_settings.mcp_host = "::"
    mock_settings.mcp_port = 8000

    main(["--transport", "streamable-http", "--host", "127.0.0.1"])

    assert mock_main_app.run.call_args.kwargs["host"] == "127.0.0.1"


def test_main_passes_cli_zero_port_override_to_streamable_http(
    mock_main_app, mock_main_settings
):
    mock_settings = mock_main_settings.return_value
    mock_settings.mcp_port = 8000

    main(["--transport", "streamable-http", "--port", "0"])

    assert mock_main_app.run.call_args.kwargs["port"] == 0


def test_main_uses_settings_transport_when_cli_omits_transport(
    mock_main_app, mock_main_settings
):
    mock_settings = mock_main_settings.return_value
    mock_settings.mcp_transport = "streamable-http"
    mock_settings.mcp_host = None

    main([])

    mock_main_app.run.assert_called_once()
    call_kwargs = mock_main_app.run.call_args.kwargs
    assert "host" not in call_kwargs
    assert call_kwargs["port"] == 8000


def test_parse_args_overrides_http_host_and_port():
    args = parse_args([
        "--transport",
        "streamable-http",
        "--host",
        "127.0.0.1",
        "--port",
        "9000",
    ])

    assert args.transport == "streamable-http"
    assert args.host == "127.0.0.1"
    assert args.port == 9000


def test_run_server_omits_host_and_port_for_stdio(
    mock_main_app,
    mock_main_settings,
):
    run_server()

    assert mock_main_settings.called
    mock_main_app.run.assert_called_once_with(
        transport="stdio",
        show_banner=False,
    )


@pytest.mark.asyncio
async def test_set_logging_level_handler(skip_vector_store_init):
    app = create_app()

    async with Client(app) as client:
        await client.set_logging_level("info")

        assert client.is_connected() is True


def test_main_handles_file_not_found_exception(
    mocker,
    mock_main_app,
    mock_main_settings,
):
    mock_main_app.run.side_effect = FileNotFoundError("spec not found")
    mock_exit = mocker.patch("sys.exit")

    main([])

    assert mock_main_settings.called
    mock_exit.assert_called_once_with(1)


def test_main_handles_runtime_error(
    mocker,
    mock_main_app,
    mock_main_settings,
):
    mock_main_app.run.side_effect = RuntimeError("unexpected error")
    mock_exit = mocker.patch("sys.exit")

    main([])

    assert mock_main_settings.called
    mock_exit.assert_called_once_with(1)


def test_main_handles_os_error(
    mocker,
    mock_main_app,
    mock_main_settings,
):
    mock_main_app.run.side_effect = OSError("address in use")
    mock_exit = mocker.patch("sys.exit")

    main([])

    assert mock_main_settings.called
    mock_exit.assert_called_once_with(1)


def test_main_propagates_unexpected_exception(
    mocker,
    mock_main_app,
    mock_main_settings,
):
    mock_main_app.run.side_effect = KeyError("unhandled programming bug")
    mock_exit = mocker.patch("sys.exit")

    with pytest.raises(KeyError):
        main([])

    assert mock_main_settings.called
    mock_exit.assert_not_called()


def test_create_app_does_not_block_on_vector_store_init(mocker):
    init_spy = mocker.patch(
        "cisco_meraki_mcp.main.initialize_vector_store",
    )

    app = create_app()

    assert isinstance(app, FastMCP)
    init_spy.assert_not_called()


def test_index_builder_records_ready_on_success(mocker):
    state = IndexState()
    mock_store = mocker.MagicMock()

    IndexBuilder(lambda: mock_store, state=state).build_blocking()

    assert state.status is IndexStatus.READY
    assert state.error_message is None


def test_index_builder_closes_published_store_without_lifespan(mocker):
    state = IndexState()
    mock_store = mocker.MagicMock()
    builder = IndexBuilder(lambda: mock_store, state=state)

    builder.publish(mock_store)
    builder.close_published_store()

    mock_store.close.assert_called_once_with()


def test_index_builder_records_failed_on_missing_spec(mocker):
    state = IndexState()

    def factory() -> object:
        raise FileNotFoundError("spec missing")

    IndexBuilder(factory, state=state).build_blocking()

    assert state.status is IndexStatus.FAILED
    assert state.error_message == "FileNotFoundError: spec missing"


@pytest.mark.parametrize(
    ("exc", "message"),
    [
        (RuntimeError("ssl failure"), "ssl failure"),
        (OSError("network down"), "network down"),
        (ValueError("malformed spec"), "malformed spec"),
    ],
    ids=["runtime-error", "os-error", "value-error"],
)
def test_index_builder_records_failed_for_expected_errors(
    exc, message, mocker
):
    state = IndexState()

    def factory() -> object:
        raise exc

    IndexBuilder(factory, state=state).build_blocking()

    assert state.status is IndexStatus.FAILED
    assert state.error_message is not None
    assert message in state.error_message


def test_index_builder_propagates_unexpected_exception(mocker):
    state = IndexState()

    def factory() -> object:
        raise KeyError("unhandled programming bug")

    with pytest.raises(KeyError):
        IndexBuilder(factory, state=state).build_blocking()

    assert state.status is IndexStatus.FAILED
    assert state.error_message is not None
    assert "KeyError" in state.error_message


@pytest.mark.asyncio
async def test_index_builder_lifespan_yields_before_index_completes(
    mocker,
):
    def slow_factory() -> object:
        time.sleep(0.5)
        return mocker.MagicMock()

    state = IndexState()
    builder = IndexBuilder(slow_factory, state=state)

    started_at = asyncio.get_running_loop().time()
    async with builder.lifespan(mocker.MagicMock()) as ctx:
        yielded_at = asyncio.get_running_loop().time()

    yield_delay = yielded_at - started_at

    assert yield_delay < 0.25, (
        f"lifespan startup blocked for {yield_delay:.3f}s; must yield "
        "before background indexing runs"
    )
    assert "index_state" in ctx
    assert ctx["index_state"] is state


@pytest.mark.asyncio
async def test_index_builder_lifespan_cancels_task_on_shutdown(
    mocker,
):
    block_until_shutdown = threading.Event()

    def factory() -> object:
        block_until_shutdown.wait(timeout=5.0)
        return mocker.MagicMock()

    state = IndexState()
    builder = IndexBuilder(factory, state=state)

    async with builder.lifespan(mocker.MagicMock()) as ctx:
        await asyncio.sleep(0.05)
        index_state_before_exit = ctx["index_state"]

    block_until_shutdown.set()

    assert index_state_before_exit.status is not IndexStatus.READY
    assert index_state_before_exit.error_message is None


@pytest.mark.asyncio
async def test_index_builder_lifespan_closes_published_store_on_shutdown(
    wait_for_status,
    mocker,
):
    store = mocker.MagicMock()
    state = IndexState()
    builder = IndexBuilder(lambda: store, state=state)

    async with builder.lifespan(mocker.MagicMock()) as ctx:
        await wait_for_status(state, IndexStatus.READY)
        assert ctx["store"] is store

    store.close.assert_called_once_with()
    assert ctx["store"] is None


@pytest.mark.asyncio
async def test_index_builder_lifespan_closes_late_store_after_shutdown(
    mocker,
):
    build_can_finish = threading.Event()
    close_observed = threading.Event()
    store = mocker.MagicMock()
    store.close.side_effect = close_observed.set

    def factory() -> object:
        build_can_finish.wait(timeout=5.0)
        return store

    state = IndexState()
    builder = IndexBuilder(factory, state=state)

    async with builder.lifespan(mocker.MagicMock()) as ctx:
        await asyncio.sleep(0.05)

    build_can_finish.set()

    assert await asyncio.to_thread(close_observed.wait, 2.0) is True
    store.close.assert_called_once_with()
    assert state.status is not IndexStatus.READY
    assert ctx["store"] is None


@pytest.mark.asyncio
async def test_index_builder_lifespan_propagates_non_cancellation_errors(
    wait_for_status, mocker
):
    # The previous `cancel()` swallowed every exception out of the
    # background task. After narrowing the suppress to CancelledError
    # only, programming bugs and infra failures must propagate through
    # the lifespan teardown so they are observable in logs.
    def factory() -> object:
        raise KeyError("unhandled programming bug")

    state = IndexState()
    builder = IndexBuilder(factory, state=state)

    async def run_lifespan() -> None:
        async with builder.lifespan(mocker.MagicMock()):
            # Wait for the background task to surface its exception so
            # cancel() observes a completed task whose result is the
            # KeyError, not CancelledError.
            await wait_for_status(state, IndexStatus.FAILED)

    with pytest.raises(KeyError):
        await run_lifespan()


def test_bundled_spec_path_points_at_package_resource():
    result = bundled_spec_path()

    assert result.is_absolute()
    assert result.name == "meraki.json.gz"
    assert result.parent.name == "specs"
    assert result.parent.parent.name == "cisco_meraki_mcp"
    assert result.exists()


def test_initialize_vector_store_uses_bundled_spec_by_default(
    clear_settings_cache, mock_text_embedding, caplog
):
    caplog.set_level(logging.INFO)

    store = initialize_vector_store()

    assert len(store.endpoints) > 0
    joined = " ".join(rec.message for rec in caplog.records)
    assert "meraki.json.gz" in joined


def test_initialize_vector_store_accepts_spec_path_override(
    clear_settings_cache,
    mock_text_embedding,
    sample_openapi_spec,
    caplog,
):
    caplog.set_level(logging.INFO)

    initialize_vector_store(spec_path=sample_openapi_spec)

    joined = " ".join(rec.message for rec in caplog.records)
    assert str(sample_openapi_spec) in joined
    assert "Initializing vector store" in joined


def test_main_invokes_configure_logging(
    mocker,
    mock_main_app,
    mock_main_settings,
):
    mock_configure = mocker.patch(
        "cisco_meraki_mcp.main.configure_logging",
    )

    main([])

    assert mock_main_settings.called
    mock_main_app.run.assert_called_once()
    mock_configure.assert_called_once()


def test_configure_logging_sets_uvicorn_level(mocker):
    mocker.patch("logging.basicConfig")

    configure_logging()

    assert logging.getLogger("uvicorn").level == logging.WARNING
    assert logging.getLogger("uvicorn.access").level == logging.WARNING


def test_logging_level_from_env_defaults_to_info(mocker):
    mocker.patch.dict("os.environ", {}, clear=True)

    assert logging_level_from_env() == logging.INFO


def test_logging_level_from_env_honors_log_level_env(mocker):
    mocker.patch.dict("os.environ", {"LOG_LEVEL": "DEBUG"})

    assert logging_level_from_env() == logging.DEBUG


def test_logging_level_from_env_falls_back_on_unknown(mocker):
    mocker.patch.dict("os.environ", {"LOG_LEVEL": "NONSENSE"})

    assert logging_level_from_env() == logging.INFO


def test_configure_logging_honors_log_level_env(mocker):
    basic_config = mocker.patch("logging.basicConfig")
    mocker.patch.dict("os.environ", {"LOG_LEVEL": "WARNING"})

    configure_logging()

    assert basic_config.call_args.kwargs["level"] == logging.WARNING
