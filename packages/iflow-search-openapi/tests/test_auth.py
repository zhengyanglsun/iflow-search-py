"""Bearer auth dependency (design §7)."""

from __future__ import annotations

from collections.abc import Callable

import httpx
import pytest
from conftest import envelope, make_config


def _upstream_ok(request: httpx.Request) -> httpx.Response:
    return httpx.Response(
        200,
        json=envelope(
            data={
                "query": "x",
                "results": [],
                "tookMs": 1,
            }
        ),
    )


@pytest.mark.asyncio
async def test_open_mode_allows_unauthenticated(
    client_factory: Callable[..., tuple],
) -> None:
    test_client, _core, _rec = client_factory(upstream_handler=_upstream_ok)
    resp = await test_client.post("/tools/iflow_web_search", json={"query": "x"})
    assert resp.status_code == 200
    assert resp.json()["ok"] is True


@pytest.mark.asyncio
async def test_closed_mode_missing_header(client_factory: Callable[..., tuple]) -> None:
    cfg = make_config(auth_token="s3cret")
    test_client, _core, _rec = client_factory(upstream_handler=_upstream_ok, config=cfg)
    resp = await test_client.post("/tools/iflow_web_search", json={"query": "x"})
    assert resp.status_code == 401
    body = resp.json()
    assert body["ok"] is False
    assert body["error"]["code"] == "unauthorized"
    assert "Missing Authorization" in body["error"]["message"]


@pytest.mark.asyncio
async def test_closed_mode_malformed_header(client_factory: Callable[..., tuple]) -> None:
    cfg = make_config(auth_token="s3cret")
    test_client, _core, _rec = client_factory(upstream_handler=_upstream_ok, config=cfg)
    resp = await test_client.post(
        "/tools/iflow_web_search",
        json={"query": "x"},
        headers={"Authorization": "Basic xxx"},
    )
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "unauthorized"


@pytest.mark.asyncio
async def test_closed_mode_empty_token(client_factory: Callable[..., tuple]) -> None:
    cfg = make_config(auth_token="s3cret")
    test_client, _core, _rec = client_factory(upstream_handler=_upstream_ok, config=cfg)
    resp = await test_client.post(
        "/tools/iflow_web_search",
        json={"query": "x"},
        headers={"Authorization": "Bearer   "},
    )
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "unauthorized"


@pytest.mark.asyncio
async def test_closed_mode_wrong_token(client_factory: Callable[..., tuple]) -> None:
    cfg = make_config(auth_token="s3cret")
    test_client, _core, _rec = client_factory(upstream_handler=_upstream_ok, config=cfg)
    resp = await test_client.post(
        "/tools/iflow_web_search",
        json={"query": "x"},
        headers={"Authorization": "Bearer wrong"},
    )
    assert resp.status_code == 401
    body = resp.json()
    assert body["error"]["code"] == "unauthorized"
    # The configured token never appears in the error envelope.
    assert "s3cret" not in resp.text


@pytest.mark.asyncio
async def test_closed_mode_wrong_token_length_mismatch(
    client_factory: Callable[..., tuple],
) -> None:
    # Length mismatch path covered: provided length != expected length.
    cfg = make_config(auth_token="long-token-xxxxxxxxxx")
    test_client, _core, _rec = client_factory(upstream_handler=_upstream_ok, config=cfg)
    resp = await test_client.post(
        "/tools/iflow_web_search",
        json={"query": "x"},
        headers={"Authorization": "Bearer x"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_closed_mode_correct_token_succeeds(
    client_factory: Callable[..., tuple],
) -> None:
    cfg = make_config(auth_token="s3cret")
    test_client, _core, _rec = client_factory(upstream_handler=_upstream_ok, config=cfg)
    resp = await test_client.post(
        "/tools/iflow_web_search",
        json={"query": "x"},
        headers={"Authorization": "Bearer s3cret"},
    )
    assert resp.status_code == 200
    assert resp.json()["ok"] is True


@pytest.mark.asyncio
async def test_openapi_gated_when_closed(client_factory: Callable[..., tuple]) -> None:
    cfg = make_config(auth_token="s3cret")
    test_client, _core, _rec = client_factory(upstream_handler=_upstream_ok, config=cfg)

    unauth = await test_client.get("/openapi.json")
    assert unauth.status_code == 401

    authed = await test_client.get("/openapi.json", headers={"Authorization": "Bearer s3cret"})
    assert authed.status_code == 200


@pytest.mark.asyncio
async def test_openapi_open_when_no_token(client_factory: Callable[..., tuple]) -> None:
    test_client, _core, _rec = client_factory(upstream_handler=_upstream_ok)
    resp = await test_client.get("/openapi.json")
    assert resp.status_code == 200
