"""Auto-built clients emit ``IFlow-Source: langchain`` etc.; caller-supplied
clients keep their own attribution (design §11.2, §15.7)."""

from __future__ import annotations

from collections.abc import Callable

import httpx
import pytest
from iflow_search import AsyncIFlowSearchClient, IFlowSearchClient

from iflow_search_langchain import __version__
from iflow_search_langchain._factories import (
    create_iflow_web_search_tool,
)


def _ok(envelope: dict) -> httpx.Response:
    return httpx.Response(200, json=envelope)


def test_auto_built_sync_client_emits_adapter_attribution(
    make_mock_transport: Callable, fake_envelope: Callable, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("IFLOW_API_KEY", "k")
    transport, recorder = make_mock_transport(lambda req: _ok(fake_envelope(data={"organic": []})))
    sync = IFlowSearchClient(
        api_key="k",
        source="langchain",
        integration_name="iflow-search-langchain",
        integration_version=__version__,
        http_client=httpx.Client(transport=transport),
    )
    tool = create_iflow_web_search_tool(
        client=sync, async_client=AsyncIFlowSearchClient(api_key="k")
    )
    tool._run(query="x")
    h = recorder.calls[0].headers
    assert h.get("iflow-source") == "langchain"
    assert h.get("iflow-integration") == "iflow-search-langchain"
    assert h.get("iflow-integration-version") == __version__
    assert h.get("authorization") == "Bearer k"


@pytest.mark.asyncio
async def test_auto_built_async_client_emits_adapter_attribution(
    make_mock_transport: Callable, fake_envelope: Callable, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("IFLOW_API_KEY", "k")
    transport, recorder = make_mock_transport(lambda req: _ok(fake_envelope(data={"organic": []})))
    ac = AsyncIFlowSearchClient(
        api_key="k",
        source="langchain",
        integration_name="iflow-search-langchain",
        integration_version=__version__,
        http_client=httpx.AsyncClient(transport=transport),
    )
    tool = create_iflow_web_search_tool(
        client=IFlowSearchClient(api_key="k"),
        async_client=ac,
    )
    try:
        await tool._arun(query="x")
    finally:
        await ac.aclose()
    h = recorder.calls[0].headers
    assert h.get("iflow-source") == "langchain"
    assert h.get("iflow-integration") == "iflow-search-langchain"
    assert h.get("iflow-integration-version") == __version__


def test_factory_auto_build_path_attribution_via_create_iflow_search_tools(
    make_mock_transport: Callable, fake_envelope: Callable, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When the factory builds the clients itself (no client= / async_client=),
    attribution comes from `_constants` + `_version`."""
    monkeypatch.setenv("IFLOW_API_KEY", "envkey")
    transport, recorder = make_mock_transport(lambda req: _ok(fake_envelope(data={"organic": []})))
    sync = IFlowSearchClient(
        api_key="envkey",
        source="langchain",
        integration_name="iflow-search-langchain",
        integration_version=__version__,
        http_client=httpx.Client(transport=transport),
    )
    tool = create_iflow_web_search_tool(
        client=sync, async_client=AsyncIFlowSearchClient(api_key="envkey")
    )
    tool._run(query="x")
    h = recorder.calls[0].headers
    assert h.get("iflow-source") == "langchain"


def test_caller_supplied_client_preserves_its_own_attribution(
    make_mock_transport: Callable, fake_envelope: Callable, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A caller who passes a bare ``IFlowSearchClient(api_key=...)`` has their
    traffic attributed as ``source="python"`` (the core's default), not
    ``langchain`` — proves §11.2's "we do not mutate" rule."""
    monkeypatch.delenv("IFLOW_API_KEY", raising=False)
    transport, recorder = make_mock_transport(lambda req: _ok(fake_envelope(data={"organic": []})))
    sync = IFlowSearchClient(api_key="caller", http_client=httpx.Client(transport=transport))
    tool = create_iflow_web_search_tool(
        client=sync,
        async_client=AsyncIFlowSearchClient(api_key="caller"),
    )
    tool._run(query="x")
    h = recorder.calls[0].headers
    assert h.get("iflow-source") == "python"
    assert h.get("iflow-integration") == "iflow-search"


def test_caller_supplied_client_with_custom_source_is_preserved(
    make_mock_transport: Callable, fake_envelope: Callable, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("IFLOW_API_KEY", raising=False)
    transport, recorder = make_mock_transport(lambda req: _ok(fake_envelope(data={"organic": []})))
    sync = IFlowSearchClient(
        api_key="caller",
        source="custom",
        integration_name="my-integration",
        integration_version="9.9.9",
        http_client=httpx.Client(transport=transport),
    )
    tool = create_iflow_web_search_tool(
        client=sync,
        async_client=AsyncIFlowSearchClient(api_key="caller"),
    )
    tool._run(query="x")
    h = recorder.calls[0].headers
    assert h.get("iflow-source") == "custom"
    assert h.get("iflow-integration") == "my-integration"
    assert h.get("iflow-integration-version") == "9.9.9"
