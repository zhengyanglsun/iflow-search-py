"""``_arun`` exercises the async client, returns ``(content, artifact)``, and
emits the same wire payload as ``_run``."""

from __future__ import annotations

import json
from collections.abc import Callable

import httpx
import pytest
from iflow_search import AsyncIFlowSearchClient

from iflow_search_langchain._tools import (
    _ImageSearchTool,
    _WebFetchTool,
    _WebSearchTool,
)


def _ok_response(envelope: dict) -> httpx.Response:
    return httpx.Response(200, json=envelope)


def _make_async(transport: httpx.MockTransport) -> AsyncIFlowSearchClient:
    return AsyncIFlowSearchClient(
        api_key="test-key",
        http_client=httpx.AsyncClient(transport=transport),
    )


@pytest.mark.asyncio
async def test_web_search_arun_calls_endpoint(
    make_mock_transport: Callable, fake_envelope: Callable
) -> None:
    envelope = fake_envelope(
        data={"organic": [{"title": "A", "link": "https://a", "snippet": "alpha"}]}
    )
    transport, recorder = make_mock_transport(lambda req: _ok_response(envelope))
    ac = _make_async(transport)
    tool = _WebSearchTool(sync_client=ac, async_client=ac)  # type: ignore[arg-type]

    try:
        content, artifact = await tool._arun(query="q", count=1)
    finally:
        await ac.aclose()

    assert recorder.calls[0].url.endswith("/api/search/webSearch")
    assert json.loads(recorder.calls[0].body) == {"keywords": "q", "num": 1}
    assert "q" in content
    assert artifact["query"] == "q"
    assert artifact["raw"] == envelope


@pytest.mark.asyncio
async def test_image_search_arun_calls_endpoint(
    make_mock_transport: Callable, fake_envelope: Callable
) -> None:
    envelope = fake_envelope(data=[{"url": "https://i", "refUrl": "https://p", "title": "T"}])
    transport, recorder = make_mock_transport(lambda req: _ok_response(envelope))
    ac = _make_async(transport)
    tool = _ImageSearchTool(sync_client=ac, async_client=ac)  # type: ignore[arg-type]

    try:
        content, artifact = await tool._arun(query="cat", count=None)
    finally:
        await ac.aclose()

    assert recorder.calls[0].url.endswith("/api/search/imageSearch")
    assert json.loads(recorder.calls[0].body) == {"keywords": "cat"}
    assert "https://i" in content
    assert artifact["images"][0]["image_url"] == "https://i"


@pytest.mark.asyncio
async def test_web_fetch_arun_calls_endpoint(
    make_mock_transport: Callable, fake_envelope: Callable
) -> None:
    envelope = fake_envelope(
        data={"url": "https://e", "title": "Ex", "content": "Hi", "fromCache": False}
    )
    transport, recorder = make_mock_transport(lambda req: _ok_response(envelope))
    ac = _make_async(transport)
    tool = _WebFetchTool(sync_client=ac, async_client=ac)  # type: ignore[arg-type]

    try:
        content, artifact = await tool._arun(url="https://e")
    finally:
        await ac.aclose()

    assert recorder.calls[0].url.endswith("/api/search/webFetch")
    assert json.loads(recorder.calls[0].body) == {"url": "https://e"}
    assert "Ex" in content
    assert artifact["from_cache"] is False
