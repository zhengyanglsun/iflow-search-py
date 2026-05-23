"""Factory contracts per design §10 and §11."""

from __future__ import annotations

from collections.abc import Callable

import httpx
import pytest
from iflow_search import AsyncIFlowSearchClient, IFlowSearchClient
from langchain_core.tools import BaseTool

from iflow_search_langchain._factories import (
    create_iflow_image_search_tool,
    create_iflow_search_tools,
    create_iflow_web_fetch_tool,
    create_iflow_web_search_tool,
)
from iflow_search_langchain._tools import (
    _ImageSearchTool,
    _WebFetchTool,
    _WebSearchTool,
)


def _ok(envelope: dict) -> httpx.Response:
    return httpx.Response(200, json=envelope)


# ---- shape / return-type ----


@pytest.mark.parametrize(
    ("factory", "expected_cls"),
    [
        (create_iflow_web_search_tool, _WebSearchTool),
        (create_iflow_image_search_tool, _ImageSearchTool),
        (create_iflow_web_fetch_tool, _WebFetchTool),
    ],
)
def test_factory_returns_basetool_subclass_instance(factory: Callable, expected_cls: type) -> None:
    tool = factory(api_key="test-key")
    assert isinstance(tool, BaseTool)
    assert isinstance(tool, expected_cls)


# ---- auto-build path: api_key from kwarg ----


def test_auto_build_uses_provided_api_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("IFLOW_API_KEY", raising=False)
    tool = create_iflow_web_search_tool(api_key="explicit-key")
    assert isinstance(tool, _WebSearchTool)


# ---- auto-build path: api_key from env ----


def test_auto_build_falls_back_to_env_var(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("IFLOW_API_KEY", "env-key")
    tool = create_iflow_web_search_tool()
    assert isinstance(tool, _WebSearchTool)


def test_auto_build_missing_api_key_raises_at_factory_time(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from iflow_search import IFlowConfigError

    monkeypatch.delenv("IFLOW_API_KEY", raising=False)
    with pytest.raises(IFlowConfigError):
        create_iflow_web_search_tool()


# ---- caller-supplied client passthrough ----


def test_caller_supplied_clients_used_verbatim(
    make_mock_transport: Callable, fake_envelope: Callable, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("IFLOW_API_KEY", raising=False)
    transport, _recorder = make_mock_transport(lambda req: _ok(fake_envelope(data={"organic": []})))
    sync = IFlowSearchClient(api_key="caller-sync", http_client=httpx.Client(transport=transport))
    async_ = AsyncIFlowSearchClient(
        api_key="caller-async", http_client=httpx.AsyncClient(transport=transport)
    )
    tool = create_iflow_web_search_tool(client=sync, async_client=async_)
    assert isinstance(tool, _WebSearchTool)
    assert tool._sync_client is sync
    assert tool._async_client is async_


# ---- mixed clients: one supplied, one auto-built ----


def test_mixed_client_auto_builds_missing_counterpart(
    make_mock_transport: Callable, fake_envelope: Callable, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("IFLOW_API_KEY", raising=False)
    transport, _recorder = make_mock_transport(lambda req: _ok(fake_envelope(data={"organic": []})))
    sync = IFlowSearchClient(api_key="caller-sync", http_client=httpx.Client(transport=transport))
    tool = create_iflow_web_search_tool(client=sync, api_key="for-async")
    assert tool._sync_client is sync
    assert tool._async_client is not sync
    assert isinstance(tool._async_client, AsyncIFlowSearchClient)


def test_one_supplied_client_still_needs_api_key_for_other(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """If only one client is supplied and api_key/env is missing for the
    auto-built counterpart, fail fast at factory time (design §12.3)."""
    from iflow_search import IFlowConfigError

    monkeypatch.delenv("IFLOW_API_KEY", raising=False)
    sync = IFlowSearchClient(api_key="caller-sync")
    with pytest.raises(IFlowConfigError):
        create_iflow_web_search_tool(client=sync)


# ---- both clients supplied: env is not required ----


def test_both_clients_supplied_no_env_required(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("IFLOW_API_KEY", raising=False)
    sync = IFlowSearchClient(api_key="caller-sync")
    async_ = AsyncIFlowSearchClient(api_key="caller-async")
    tool = create_iflow_web_search_tool(client=sync, async_client=async_)
    assert tool._sync_client is sync
    assert tool._async_client is async_


# ---- base_url / timeout forwarding ----


def test_base_url_and_timeout_forwarded(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("IFLOW_API_KEY", "k")
    tool = create_iflow_web_search_tool(base_url="https://staging.example.com", timeout=5.0)
    assert isinstance(tool, _WebSearchTool)


# ---- sanity: each factory produces a different tool ----


def test_factories_produce_distinct_tools(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("IFLOW_API_KEY", "k")
    w = create_iflow_web_search_tool()
    i = create_iflow_image_search_tool()
    f = create_iflow_web_fetch_tool()
    assert w.name == "iflow_web_search"
    assert i.name == "iflow_image_search"
    assert f.name == "iflow_web_fetch"


# ============================================================================
# create_iflow_search_tools — design §10.3
# ============================================================================


def test_create_iflow_search_tools_returns_three_in_fixed_order(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("IFLOW_API_KEY", "k")
    tools = create_iflow_search_tools()
    assert [t.name for t in tools] == [
        "iflow_web_search",
        "iflow_image_search",
        "iflow_web_fetch",
    ]


def test_create_iflow_search_tools_all_tools_share_one_client_pair(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("IFLOW_API_KEY", "k")
    tools = create_iflow_search_tools()
    sync_a = tools[0]._sync_client  # type: ignore[attr-defined]
    async_a = tools[0]._async_client  # type: ignore[attr-defined]
    for t in tools[1:]:
        assert t._sync_client is sync_a  # type: ignore[attr-defined]
        assert t._async_client is async_a  # type: ignore[attr-defined]


def test_create_iflow_search_tools_accepts_caller_supplied_clients(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("IFLOW_API_KEY", raising=False)
    sync = IFlowSearchClient(api_key="sync-k")
    async_ = AsyncIFlowSearchClient(api_key="async-k")
    tools = create_iflow_search_tools(client=sync, async_client=async_)
    for t in tools:
        assert t._sync_client is sync  # type: ignore[attr-defined]
        assert t._async_client is async_  # type: ignore[attr-defined]


def test_create_iflow_search_tools_missing_key_fails_at_factory_time(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from iflow_search import IFlowConfigError

    monkeypatch.delenv("IFLOW_API_KEY", raising=False)
    with pytest.raises(IFlowConfigError):
        create_iflow_search_tools()
