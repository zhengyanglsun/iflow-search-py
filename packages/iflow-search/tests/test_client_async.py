"""Async client parity tests.

Mirrors the most important assertions from ``test_client_sync.py`` against
``AsyncIFlowSearchClient`` to confirm the two clients behave identically.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Callable
from typing import Any

import httpx
import pytest

from iflow_search import (
    AsyncIFlowSearchClient,
    IFlowAuthError,
    IFlowBusinessError,
    IFlowRateLimitError,
    IFlowTimeoutError,
)


def _envelope(*, success: bool = True, code: str = "200", message: str = "ok", data: Any = None) -> dict[str, Any]:
    return {
        "success": success,
        "code": code,
        "message": message,
        "data": data if data is not None else {},
        "extra": None,
        "exception": None,
    }


def _make_async_client(
    handler: Callable[[httpx.Request], httpx.Response],
) -> AsyncIFlowSearchClient:
    transport = httpx.MockTransport(handler)
    http = httpx.AsyncClient(transport=transport, timeout=5.0)
    return AsyncIFlowSearchClient(
        api_key="test-key",
        integration_version="0.1.0a0",
        http_client=http,
    )


@pytest.mark.asyncio
async def test_async_web_search_payload_and_headers() -> None:
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(
            200,
            json=_envelope(
                data={
                    "query": "q",
                    "organic": [
                        {"title": "T", "link": "https://x/1", "snippet": "s", "position": 1}
                    ],
                }
            ),
        )

    client = _make_async_client(handler)
    try:
        result = await client.web_search(query="q", count=3)
    finally:
        await client.aclose()

    body = json.loads(captured[0].content.decode("utf-8"))
    assert body == {"keywords": "q", "num": 3}
    assert captured[0].url.path == "/api/search/webSearch"
    assert captured[0].headers["authorization"] == "Bearer test-key"
    assert captured[0].headers["iflow-source"] == "python"
    assert result.results[0].url == "https://x/1"


@pytest.mark.asyncio
async def test_async_image_search() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json=_envelope(data=[{"url": "https://img", "refUrl": "https://src", "title": "t"}]),
        )

    client = _make_async_client(handler)
    try:
        result = await client.image_search(query="logo")
    finally:
        await client.aclose()

    assert len(result.images) == 1
    assert result.images[0].image_url == "https://img"
    assert result.images[0].source_url == "https://src"


@pytest.mark.asyncio
async def test_async_web_fetch_from_cache_rename() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json=_envelope(
                data={
                    "title": "T",
                    "content": "C",
                    "url": "https://u",
                    "fromCache": False,
                }
            ),
        )

    client = _make_async_client(handler)
    try:
        result = await client.web_fetch(url="https://u")
    finally:
        await client.aclose()

    assert result.from_cache is False
    assert result.title == "T"


@pytest.mark.asyncio
async def test_async_http_429_maps_to_rate_limit() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, text="x")

    client = _make_async_client(handler)
    try:
        with pytest.raises(IFlowRateLimitError):
            await client.web_search(query="q")
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_async_business_90402_maps_to_auth() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_envelope(success=False, code="90402", message="k"))

    client = _make_async_client(handler)
    try:
        with pytest.raises(IFlowAuthError) as exc:
            await client.web_search(query="q")
        assert exc.value.code == "business_invalid_api_key"
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_async_business_90002_returns_business_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_envelope(success=False, code="90002", message="empty"))

    client = _make_async_client(handler)
    try:
        with pytest.raises(IFlowBusinessError) as exc:
            await client.web_search(query="q")
        assert exc.value.business_code == "90002"
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_async_timeout_maps_to_timeout_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("x")

    client = _make_async_client(handler)
    try:
        with pytest.raises(IFlowTimeoutError):
            await client.web_search(query="q")
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_async_cancellation_propagates() -> None:
    """Caller-initiated ``asyncio.CancelledError`` must not be wrapped."""

    async def slow_handler() -> None:
        await asyncio.sleep(10)

    def handler(request: httpx.Request) -> httpx.Response:  # pragma: no cover
        return httpx.Response(200, json=_envelope())

    client = _make_async_client(handler)

    async def call() -> None:
        # Cancel ourselves before any I/O happens to verify the exception type.
        raise asyncio.CancelledError

    try:
        with pytest.raises(asyncio.CancelledError):
            await call()
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_async_context_manager() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_envelope(data={"organic": []}))

    transport = httpx.MockTransport(handler)
    http = httpx.AsyncClient(transport=transport, timeout=5.0)
    async with AsyncIFlowSearchClient(api_key="test-key", http_client=http) as client:
        result = await client.web_search(query="q")
    assert result.query == "q"
