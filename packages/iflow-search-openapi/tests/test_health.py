"""GET /health: always 200, exempt from auth even in closed mode (design §7.3)."""

from __future__ import annotations

from collections.abc import Callable

import httpx
import pytest
from conftest import make_config

from iflow_search_openapi._version import __version__


def _no_upstream(_request: httpx.Request) -> httpx.Response:  # pragma: no cover
    raise AssertionError("upstream must not be called for /health")


@pytest.mark.asyncio
async def test_health_open_mode(client_factory: Callable[..., tuple]) -> None:
    test_client, _core, _rec = client_factory(upstream_handler=_no_upstream)
    resp = await test_client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body == {"ok": True, "version": __version__}


@pytest.mark.asyncio
async def test_health_closed_mode_without_bearer(
    client_factory: Callable[..., tuple],
) -> None:
    cfg = make_config(auth_token="secret-token")
    test_client, _core, _rec = client_factory(upstream_handler=_no_upstream, config=cfg)
    resp = await test_client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["ok"] is True
