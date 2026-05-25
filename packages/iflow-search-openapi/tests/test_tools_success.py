"""Successful tool invocations: outbound shape + inbound envelope (design §6, §8.1)."""

from __future__ import annotations

from collections.abc import Callable

import httpx
import pytest
from conftest import envelope


def _web_search_handler(request: httpx.Request) -> httpx.Response:
    body = request.read()
    assert b"keywords" in body, "wire body must use 'keywords', not 'query'"
    return httpx.Response(
        200,
        json=envelope(
            data={
                "query": "great wall",
                "organic": [
                    {
                        "title": "T1",
                        "link": "https://example.com/1",
                        "snippet": "S1",
                        "position": 1,
                    },
                ],
                "tookMs": 12,
            }
        ),
    )


def _image_search_handler(request: httpx.Request) -> httpx.Response:
    return httpx.Response(
        200,
        json=envelope(
            data={
                "images": [
                    {
                        "url": "https://img.example.com/1.jpg",
                        "refUrl": "https://src.example.com/page1",
                        "title": "Image 1",
                        "width": 800,
                        "height": 600,
                        "position": 1,
                    },
                ],
                "tookMs": 8,
            }
        ),
    )


def _web_fetch_handler(request: httpx.Request) -> httpx.Response:
    return httpx.Response(
        200,
        json=envelope(
            data={
                "url": "https://example.com",
                "title": "Example Domain",
                "content": "Hello world",
                "fromCache": True,
                "tookMs": 5,
            }
        ),
    )


@pytest.mark.asyncio
async def test_web_search_success(client_factory: Callable[..., tuple]) -> None:
    test_client, _core, recorder = client_factory(upstream_handler=_web_search_handler)
    resp = await test_client.post(
        "/tools/iflow_web_search", json={"query": "great wall", "count": 3}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    data = body["data"]
    assert data["query"] == "great wall"
    assert data["results"][0]["title"] == "T1"
    # snake_case + wire-rename happened in the core.
    assert data["results"][0]["url"] == "https://example.com/1"
    assert "took_ms" in data
    # `raw` excluded by design §13.2.
    assert "raw" not in data
    # Outbound request was correct.
    assert len(recorder.calls) == 1
    call = recorder.calls[0]
    assert call.method == "POST"
    assert call.url.endswith("/api/search/webSearch")
    assert call.body_json == {"keywords": "great wall", "num": 3}


@pytest.mark.asyncio
async def test_image_search_success(client_factory: Callable[..., tuple]) -> None:
    test_client, _core, recorder = client_factory(upstream_handler=_image_search_handler)
    resp = await test_client.post("/tools/iflow_image_search", json={"query": "cats"})
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["query"] == "cats"
    img = data["images"][0]
    assert img["image_url"] == "https://img.example.com/1.jpg"
    assert img["source_url"] == "https://src.example.com/page1"
    assert "raw" not in data
    call = recorder.calls[0]
    assert call.body_json == {"keywords": "cats"}


@pytest.mark.asyncio
async def test_web_fetch_success(client_factory: Callable[..., tuple]) -> None:
    test_client, _core, recorder = client_factory(upstream_handler=_web_fetch_handler)
    resp = await test_client.post("/tools/iflow_web_fetch", json={"url": "https://example.com"})
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["url"] == "https://example.com"
    assert data["title"] == "Example Domain"
    assert data["content"] == "Hello world"
    assert data["from_cache"] is True
    assert "raw" not in data
    call = recorder.calls[0]
    assert call.body_json == {"url": "https://example.com"}
