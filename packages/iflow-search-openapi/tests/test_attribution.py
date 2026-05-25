"""Outbound attribution headers (design §15, core invariant §3)."""

from __future__ import annotations

from collections.abc import Callable

import httpx
import pytest
from conftest import envelope

from iflow_search_openapi._constants import INTEGRATION_NAME, SOURCE
from iflow_search_openapi._version import __version__


def _upstream_ok(_request: httpx.Request) -> httpx.Response:
    return httpx.Response(
        200,
        json=envelope(data={"query": "x", "results": [], "tookMs": 0}),
    )


@pytest.mark.asyncio
async def test_outbound_carries_source_header(
    client_factory: Callable[..., tuple],
) -> None:
    test_client, _core, recorder = client_factory(upstream_handler=_upstream_ok)
    await test_client.post("/tools/iflow_web_search", json={"query": "x"})
    assert recorder.calls[0].headers["iflow-source"] == SOURCE
    assert SOURCE == "openapi"


@pytest.mark.asyncio
async def test_outbound_carries_integration_name(
    client_factory: Callable[..., tuple],
) -> None:
    test_client, _core, recorder = client_factory(upstream_handler=_upstream_ok)
    await test_client.post("/tools/iflow_web_search", json={"query": "x"})
    assert recorder.calls[0].headers["iflow-integration"] == INTEGRATION_NAME
    assert INTEGRATION_NAME == "iflow-search-openapi"


@pytest.mark.asyncio
async def test_outbound_carries_integration_version(
    client_factory: Callable[..., tuple],
) -> None:
    test_client, _core, recorder = client_factory(upstream_handler=_upstream_ok)
    await test_client.post("/tools/iflow_web_search", json={"query": "x"})
    assert recorder.calls[0].headers["iflow-integration-version"] == __version__


@pytest.mark.asyncio
async def test_outbound_does_not_carry_mcp_headers(
    client_factory: Callable[..., tuple],
) -> None:
    test_client, _core, recorder = client_factory(upstream_handler=_upstream_ok)
    await test_client.post("/tools/iflow_web_search", json={"query": "x"})
    headers = recorder.calls[0].headers
    assert "iflow-mcp-client" not in headers
    assert "iflow-mcp-client-version" not in headers


@pytest.mark.asyncio
async def test_outbound_carries_bearer_to_upstream(
    client_factory: Callable[..., tuple],
) -> None:
    test_client, _core, recorder = client_factory(upstream_handler=_upstream_ok)
    await test_client.post("/tools/iflow_web_search", json={"query": "x"})
    auth = recorder.calls[0].headers.get("authorization", "")
    assert auth.startswith("Bearer ")
    # The api_key configured in conftest.make_config is "test-key".
    assert auth.endswith("test-key")


@pytest.mark.asyncio
async def test_attribution_consistent_across_three_tools(
    client_factory: Callable[..., tuple],
) -> None:
    def _h(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json=envelope(
                data={
                    "query": "x",
                    "organic": [],
                    "images": [],
                    "url": "https://example.com",
                    "title": "t",
                    "content": "c",
                    "fromCache": False,
                    "tookMs": 0,
                }
            ),
        )

    test_client, _core, recorder = client_factory(upstream_handler=_h)
    await test_client.post("/tools/iflow_web_search", json={"query": "x"})
    await test_client.post("/tools/iflow_image_search", json={"query": "x"})
    await test_client.post("/tools/iflow_web_fetch", json={"url": "https://example.com"})
    assert len(recorder.calls) == 3
    for call in recorder.calls:
        assert call.headers["iflow-source"] == SOURCE
        assert call.headers["iflow-integration"] == INTEGRATION_NAME
        assert call.headers["iflow-integration-version"] == __version__
        assert "iflow-mcp-client" not in call.headers
