"""Inbound request validation (design §15, §8.3)."""

from __future__ import annotations

from collections.abc import Callable

import httpx
import pytest
from conftest import envelope


def _upstream_ok(_request: httpx.Request) -> httpx.Response:
    return httpx.Response(
        200,
        json=envelope(data={"query": "x", "results": [], "tookMs": 0}),
    )


@pytest.mark.asyncio
async def test_missing_required_field(
    client_factory: Callable[..., tuple],
) -> None:
    test_client, _core, _rec = client_factory(upstream_handler=_upstream_ok)
    resp = await test_client.post("/tools/iflow_web_search", json={})
    assert resp.status_code == 400
    body = resp.json()
    assert body["ok"] is False
    assert body["error"]["code"] == "invalid_input"


@pytest.mark.asyncio
async def test_empty_query_string(
    client_factory: Callable[..., tuple],
) -> None:
    test_client, _core, _rec = client_factory(upstream_handler=_upstream_ok)
    resp = await test_client.post("/tools/iflow_web_search", json={"query": ""})
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "invalid_input"


@pytest.mark.asyncio
async def test_count_zero_rejected(
    client_factory: Callable[..., tuple],
) -> None:
    test_client, _core, _rec = client_factory(upstream_handler=_upstream_ok)
    resp = await test_client.post("/tools/iflow_web_search", json={"query": "x", "count": 0})
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "invalid_input"


@pytest.mark.asyncio
async def test_count_non_integer_rejected(
    client_factory: Callable[..., tuple],
) -> None:
    test_client, _core, _rec = client_factory(upstream_handler=_upstream_ok)
    resp = await test_client.post("/tools/iflow_web_search", json={"query": "x", "count": "abc"})
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "invalid_input"


@pytest.mark.asyncio
async def test_extra_field_rejected(
    client_factory: Callable[..., tuple],
) -> None:
    test_client, _core, _rec = client_factory(upstream_handler=_upstream_ok)
    resp = await test_client.post(
        "/tools/iflow_web_search",
        json={"query": "x", "rogue_field": True},
    )
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "invalid_input"


@pytest.mark.asyncio
async def test_non_json_body_rejected(
    client_factory: Callable[..., tuple],
) -> None:
    test_client, _core, _rec = client_factory(upstream_handler=_upstream_ok)
    resp = await test_client.post(
        "/tools/iflow_web_search",
        content=b"not-json-at-all",
        headers={"Content-Type": "application/json"},
    )
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "invalid_input"


@pytest.mark.asyncio
async def test_json_array_rejected(
    client_factory: Callable[..., tuple],
) -> None:
    test_client, _core, _rec = client_factory(upstream_handler=_upstream_ok)
    resp = await test_client.post("/tools/iflow_web_search", json=["query", "x"])
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "invalid_input"


@pytest.mark.asyncio
async def test_oversized_body_rejected(
    client_factory: Callable[..., tuple],
) -> None:
    test_client, _core, _rec = client_factory(upstream_handler=_upstream_ok)
    big = "x" * (2 * 1024 * 1024)  # 2 MiB, exceeds 1 MiB cap
    resp = await test_client.post(
        "/tools/iflow_web_search",
        json={"query": big},
    )
    assert resp.status_code == 413
    body = resp.json()
    assert body["ok"] is False
    assert body["error"]["code"] == "payload_too_large"


@pytest.mark.asyncio
async def test_non_post_method_rejected(
    client_factory: Callable[..., tuple],
) -> None:
    test_client, _core, _rec = client_factory(upstream_handler=_upstream_ok)
    resp = await test_client.get("/tools/iflow_web_search")
    assert resp.status_code == 405
    body = resp.json()
    assert body["ok"] is False
    assert body["error"]["code"] == "method_not_allowed"


@pytest.mark.asyncio
async def test_unknown_route_returns_404(
    client_factory: Callable[..., tuple],
) -> None:
    test_client, _core, _rec = client_factory(upstream_handler=_upstream_ok)
    resp = await test_client.post("/tools/iflow_does_not_exist", json={"query": "x"})
    assert resp.status_code == 404
    body = resp.json()
    assert body["ok"] is False
    assert body["error"]["code"] == "not_found"


@pytest.mark.asyncio
async def test_image_search_extra_field_rejected(
    client_factory: Callable[..., tuple],
) -> None:
    test_client, _core, _rec = client_factory(upstream_handler=_upstream_ok)
    resp = await test_client.post("/tools/iflow_image_search", json={"query": "cats", "page": 1})
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "invalid_input"


@pytest.mark.asyncio
async def test_web_fetch_missing_url(
    client_factory: Callable[..., tuple],
) -> None:
    test_client, _core, _rec = client_factory(upstream_handler=_upstream_ok)
    resp = await test_client.post("/tools/iflow_web_fetch", json={})
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "invalid_input"


@pytest.mark.asyncio
async def test_web_fetch_empty_url(
    client_factory: Callable[..., tuple],
) -> None:
    test_client, _core, _rec = client_factory(upstream_handler=_upstream_ok)
    resp = await test_client.post("/tools/iflow_web_fetch", json={"url": ""})
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "invalid_input"
