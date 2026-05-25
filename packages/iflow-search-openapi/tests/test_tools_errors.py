"""Error → HTTP status + envelope mapping (design §8.3, §13.1)."""

from __future__ import annotations

from collections.abc import Callable

import httpx
import pytest
from conftest import envelope

# (http_status, business_code, expected_envelope_code, expected_http_status, expected_class_name)
ERROR_CASES = [
    # HTTP-level failures
    (401, None, "api_unauthorized", 401, "IFlowAuthError"),
    (403, None, "api_forbidden", 403, "IFlowAuthError"),
    (400, None, "api_bad_request", 400, "IFlowValidationError"),
    (429, None, "api_rate_limited", 429, "IFlowRateLimitError"),
    (500, None, "api_server_error", 502, "IFlowAPIError"),
    (502, None, "api_server_error", 502, "IFlowAPIError"),
    # Business-level failures (HTTP 200 with success:false)
    (200, "400", "business_bad_request", 400, "IFlowValidationError"),
    (200, "40303", "business_rate_limited", 429, "IFlowRateLimitError"),
    (200, "60400", "business_insufficient_credits", 402, "IFlowInsufficientCreditsError"),
    (200, "90001", "business_fetch_failed", 502, "IFlowBusinessError"),
    (200, "90402", "business_invalid_api_key", 401, "IFlowAuthError"),
    (200, "500", "business_server_error", 502, "IFlowAPIError"),
    (200, "999999", "business_unknown", 502, "IFlowBusinessError"),
]


def _make_handler(
    http_status: int, business_code: str | None
) -> Callable[[httpx.Request], httpx.Response]:
    if business_code is None:

        def _h(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(http_status, text="upstream said no")

        return _h

    def _h(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            http_status,
            json=envelope(success=False, code=business_code, message="business failure"),
        )

    return _h


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "http_status,business_code,expected_code,expected_http,expected_class",
    ERROR_CASES,
)
async def test_error_mapping(
    client_factory: Callable[..., tuple],
    http_status: int,
    business_code: str | None,
    expected_code: str,
    expected_http: int,
    expected_class: str,
) -> None:
    handler = _make_handler(http_status, business_code)
    test_client, _core, _rec = client_factory(upstream_handler=handler)
    resp = await test_client.post("/tools/iflow_web_search", json={"query": "x"})
    assert resp.status_code == expected_http
    body = resp.json()
    assert body["ok"] is False
    assert body["error"]["code"] == expected_code
    assert body["error"]["type"] == expected_class


@pytest.mark.asyncio
async def test_no_results_is_success_for_web_search(
    client_factory: Callable[..., tuple],
) -> None:
    handler = _make_handler(200, "90002")
    test_client, _core, _rec = client_factory(upstream_handler=handler)
    resp = await test_client.post("/tools/iflow_web_search", json={"query": "what no hits"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body["data"]["query"] == "what no hits"
    assert body["data"]["results"] == []


@pytest.mark.asyncio
async def test_no_results_is_success_for_image_search(
    client_factory: Callable[..., tuple],
) -> None:
    handler = _make_handler(200, "90002")
    test_client, _core, _rec = client_factory(upstream_handler=handler)
    resp = await test_client.post("/tools/iflow_image_search", json={"query": "obscure cats"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body["data"]["query"] == "obscure cats"
    assert body["data"]["images"] == []


@pytest.mark.asyncio
async def test_no_results_does_not_apply_to_web_fetch(
    client_factory: Callable[..., tuple],
) -> None:
    # web_fetch's "no results" code is 90001 (business_fetch_failed → 502).
    handler = _make_handler(200, "90001")
    test_client, _core, _rec = client_factory(upstream_handler=handler)
    resp = await test_client.post("/tools/iflow_web_fetch", json={"url": "https://example.com"})
    assert resp.status_code == 502
    body = resp.json()
    assert body["ok"] is False
    assert body["error"]["code"] == "business_fetch_failed"


@pytest.mark.asyncio
async def test_business_error_carries_business_code(
    client_factory: Callable[..., tuple],
) -> None:
    handler = _make_handler(200, "999999")
    test_client, _core, _rec = client_factory(upstream_handler=handler)
    resp = await test_client.post("/tools/iflow_web_search", json={"query": "x"})
    body = resp.json()
    assert body["error"].get("business_code") == "999999"


@pytest.mark.asyncio
async def test_network_timeout_maps_to_504(
    client_factory: Callable[..., tuple],
) -> None:
    def _h(_request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("simulated timeout")

    test_client, _core, _rec = client_factory(upstream_handler=_h)
    resp = await test_client.post("/tools/iflow_web_search", json={"query": "x"})
    assert resp.status_code == 504
    assert resp.json()["error"]["code"] == "network_timeout"


@pytest.mark.asyncio
async def test_network_error_maps_to_502(
    client_factory: Callable[..., tuple],
) -> None:
    def _h(_request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("simulated connect failure")

    test_client, _core, _rec = client_factory(upstream_handler=_h)
    resp = await test_client.post("/tools/iflow_web_search", json={"query": "x"})
    assert resp.status_code == 502
    assert resp.json()["error"]["code"] == "network_error"
