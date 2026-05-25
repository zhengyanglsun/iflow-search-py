"""CORS middleware behaviour (design §9)."""

from __future__ import annotations

from collections.abc import Callable

import httpx
import pytest
from conftest import envelope, make_config


def _upstream_ok(_request: httpx.Request) -> httpx.Response:
    return httpx.Response(
        200,
        json=envelope(data={"query": "x", "results": [], "tookMs": 0}),
    )


@pytest.mark.asyncio
async def test_no_cors_when_unset(client_factory: Callable[..., tuple]) -> None:
    test_client, _core, _rec = client_factory(upstream_handler=_upstream_ok)
    resp = await test_client.get(
        "/health",
        headers={"Origin": "https://chat.example.com"},
    )
    assert resp.status_code == 200
    assert "access-control-allow-origin" not in {k.lower() for k in resp.headers}


@pytest.mark.asyncio
async def test_cors_wildcard(client_factory: Callable[..., tuple]) -> None:
    cfg = make_config(cors_origin="*")
    test_client, _core, _rec = client_factory(upstream_handler=_upstream_ok, config=cfg)
    resp = await test_client.get(
        "/health",
        headers={"Origin": "https://chat.example.com"},
    )
    assert resp.status_code == 200
    assert resp.headers.get("access-control-allow-origin") == "*"


@pytest.mark.asyncio
async def test_cors_exact_origin_echoed(
    client_factory: Callable[..., tuple],
) -> None:
    cfg = make_config(cors_origin="https://chat.example.com")
    test_client, _core, _rec = client_factory(upstream_handler=_upstream_ok, config=cfg)
    resp = await test_client.get(
        "/health",
        headers={"Origin": "https://chat.example.com"},
    )
    assert resp.status_code == 200
    assert resp.headers.get("access-control-allow-origin") == "https://chat.example.com"


@pytest.mark.asyncio
async def test_preflight_short_circuits_without_bearer(
    client_factory: Callable[..., tuple],
) -> None:
    cfg = make_config(auth_token="s3cret", cors_origin="https://chat.example.com")
    test_client, _core, _rec = client_factory(upstream_handler=_upstream_ok, config=cfg)
    # Browser preflight: OPTIONS with Origin and Access-Control-Request-Method.
    resp = await test_client.options(
        "/tools/iflow_web_search",
        headers={
            "Origin": "https://chat.example.com",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type,authorization",
        },
    )
    # 200 or 204 are both spec-compliant for a successful preflight; what
    # matters is that the bearer wasn't enforced.
    assert resp.status_code in (200, 204)
    assert resp.headers.get("access-control-allow-origin") == "https://chat.example.com"


@pytest.mark.asyncio
async def test_preflight_allows_x_session_id(
    client_factory: Callable[..., tuple],
) -> None:
    cfg = make_config(cors_origin="*")
    test_client, _core, _rec = client_factory(upstream_handler=_upstream_ok, config=cfg)
    resp = await test_client.options(
        "/tools/iflow_web_search",
        headers={
            "Origin": "https://chat.example.com",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "x-session-id",
        },
    )
    assert resp.status_code in (200, 204)
    allow = resp.headers.get("access-control-allow-headers", "").lower()
    assert "x-session-id" in allow
