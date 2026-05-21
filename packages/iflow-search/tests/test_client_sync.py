"""End-to-end-ish tests for ``IFlowSearchClient`` against ``httpx.MockTransport``.

These tests never touch the network — every test wires a ``MockTransport`` into
the client via the ``http_client=`` constructor argument and captures the
outbound request to assert payload shape, headers, and method signature.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

import httpx
import pytest

from iflow_search import (
    IFlowAPIError,
    IFlowAuthError,
    IFlowBusinessError,
    IFlowInsufficientCreditsError,
    IFlowNetworkError,
    IFlowRateLimitError,
    IFlowSearchClient,
    IFlowTimeoutError,
    IFlowValidationError,
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


def _make_client(
    handler: Callable[[httpx.Request], httpx.Response],
) -> IFlowSearchClient:
    transport = httpx.MockTransport(handler)
    http = httpx.Client(transport=transport, timeout=5.0)
    return IFlowSearchClient(
        api_key="test-key",
        integration_version="0.1.0a0",
        http_client=http,
    )


def test_web_search_payload_keywords_and_num() -> None:
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(
            200,
            json=_envelope(
                data={
                    "query": "flash attention",
                    "organic": [
                        {"title": "T", "link": "https://example/1", "snippet": "s", "position": 1}
                    ],
                }
            ),
        )

    client = _make_client(handler)
    try:
        result = client.web_search(query="flash attention", count=5)
    finally:
        client.close()

    assert len(captured) == 1
    body = json.loads(captured[0].content.decode("utf-8"))
    assert body == {"keywords": "flash attention", "num": 5}
    assert captured[0].url.path == "/api/search/webSearch"
    assert captured[0].method == "POST"
    assert result.query == "flash attention"
    assert result.results[0].url == "https://example/1"
    assert result.took_ms >= 0


def test_web_search_drops_num_when_count_is_none() -> None:
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(200, json=_envelope(data={"organic": []}))

    client = _make_client(handler)
    try:
        client.web_search(query="anything")
    finally:
        client.close()

    body = json.loads(captured[0].content.decode("utf-8"))
    assert body == {"keywords": "anything"}
    assert "num" not in body


def test_web_search_no_hard_cap_on_count() -> None:
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(200, json=_envelope(data={"organic": []}))

    client = _make_client(handler)
    try:
        client.web_search(query="q", count=500)
    finally:
        client.close()

    body = json.loads(captured[0].content.decode("utf-8"))
    assert body["num"] == 500  # not clamped


def test_authorization_bearer_header_sent() -> None:
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(200, json=_envelope(data={"organic": []}))

    client = _make_client(handler)
    try:
        client.web_search(query="q")
    finally:
        client.close()

    assert captured[0].headers["authorization"] == "Bearer test-key"
    assert captured[0].headers["iflow-source"] == "python"
    assert captured[0].headers["iflow-integration"] == "iflow-search"
    assert captured[0].headers["iflow-integration-version"] == "0.1.0a0"
    assert captured[0].headers["user-agent"] == "iflow-search/0.1.0a0"


def test_image_search_request_and_response() -> None:
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(
            200,
            json=_envelope(
                data=[
                    {"url": "https://img/1", "refUrl": "https://src/1", "title": "i1"},
                    {"url": "https://img/2", "refUrl": "https://src/2", "title": "i2"},
                ]
            ),
        )

    client = _make_client(handler)
    try:
        result = client.image_search(query="logo", count=2)
    finally:
        client.close()

    body = json.loads(captured[0].content.decode("utf-8"))
    assert body == {"keywords": "logo", "num": 2}
    assert captured[0].url.path == "/api/search/imageSearch"
    assert len(result.images) == 2
    assert result.images[0].image_url == "https://img/1"
    assert result.images[0].source_url == "https://src/1"


def test_web_fetch_request_and_response() -> None:
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(
            200,
            json=_envelope(
                data={
                    "title": "iFlow",
                    "content": "body",
                    "url": "https://platform.iflow.cn/",
                    "fromCache": True,
                }
            ),
        )

    client = _make_client(handler)
    try:
        result = client.web_fetch(url="https://platform.iflow.cn/")
    finally:
        client.close()

    body = json.loads(captured[0].content.decode("utf-8"))
    assert body == {"url": "https://platform.iflow.cn/"}
    assert captured[0].url.path == "/api/search/webFetch"
    assert result.title == "iFlow"
    assert result.content == "body"
    assert result.from_cache is True


def test_http_429_maps_to_rate_limit() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, text="rate limited")

    client = _make_client(handler)
    try:
        with pytest.raises(IFlowRateLimitError) as exc:
            client.web_search(query="q")
        assert exc.value.code == "api_rate_limited"
    finally:
        client.close()


def test_http_401_maps_to_auth_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, text="bad key")

    client = _make_client(handler)
    try:
        with pytest.raises(IFlowAuthError) as exc:
            client.web_search(query="q")
        assert exc.value.code == "api_unauthorized"
    finally:
        client.close()


def test_http_500_maps_to_api_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="upstream")

    client = _make_client(handler)
    try:
        with pytest.raises(IFlowAPIError) as exc:
            client.web_search(query="q")
        assert exc.value.code == "api_server_error"
        assert exc.value.status_code == 500
    finally:
        client.close()


def test_business_40303_maps_to_rate_limit() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_envelope(success=False, code="40303", message="rpm"))

    client = _make_client(handler)
    try:
        with pytest.raises(IFlowRateLimitError) as exc:
            client.web_search(query="q")
        assert exc.value.code == "business_rate_limited"
    finally:
        client.close()


def test_business_90402_maps_to_auth_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_envelope(success=False, code="90402", message="key"))

    client = _make_client(handler)
    try:
        with pytest.raises(IFlowAuthError) as exc:
            client.web_search(query="q")
        assert exc.value.code == "business_invalid_api_key"
    finally:
        client.close()


def test_business_60400_maps_to_credits() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_envelope(success=False, code="60400", message="no $$"))

    client = _make_client(handler)
    try:
        with pytest.raises(IFlowInsufficientCreditsError):
            client.web_search(query="q")
    finally:
        client.close()


def test_business_90001_on_fetch_returns_business_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_envelope(success=False, code="90001", message="parse"))

    client = _make_client(handler)
    try:
        with pytest.raises(IFlowBusinessError) as exc:
            client.web_fetch(url="https://x")
        assert exc.value.business_code == "90001"
        assert exc.value.code == "business_fetch_failed"
    finally:
        client.close()


def test_business_90002_on_search_returns_business_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_envelope(success=False, code="90002", message="empty"))

    client = _make_client(handler)
    try:
        with pytest.raises(IFlowBusinessError) as exc:
            client.web_search(query="q")
        assert exc.value.business_code == "90002"
        assert exc.value.code == "business_no_results"
    finally:
        client.close()


def test_invalid_json_returns_api_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"not-json-at-all")

    client = _make_client(handler)
    try:
        with pytest.raises(IFlowAPIError) as exc:
            client.web_search(query="q")
        assert exc.value.code == "api_invalid_json"
    finally:
        client.close()


def test_timeout_maps_to_timeout_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("read timed out")

    client = _make_client(handler)
    try:
        with pytest.raises(IFlowTimeoutError) as exc:
            client.web_search(query="q")
        assert exc.value.code == "network_timeout"
    finally:
        client.close()


def test_network_error_maps_to_network_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("dns")

    client = _make_client(handler)
    try:
        with pytest.raises(IFlowNetworkError) as exc:
            client.web_search(query="q")
        assert exc.value.code == "network_error"
    finally:
        client.close()


def test_validation_error_on_empty_query() -> None:
    def handler(request: httpx.Request) -> httpx.Response:  # pragma: no cover — never reached
        return httpx.Response(200, json=_envelope())

    client = _make_client(handler)
    try:
        with pytest.raises(IFlowValidationError):
            client.web_search(query="")
    finally:
        client.close()


def test_response_raw_preserved() -> None:
    canned = _envelope(
        data={"query": "q", "organic": [{"title": "T", "link": "u", "snippet": "", "position": 1}]}
    )

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=canned)

    client = _make_client(handler)
    try:
        result = client.web_search(query="q")
    finally:
        client.close()
    assert result.raw == canned


def test_context_manager_closes_client() -> None:
    closed: list[bool] = []

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_envelope(data={"organic": []}))

    transport = httpx.MockTransport(handler)
    http = httpx.Client(transport=transport, timeout=5.0)
    original_close = http.close

    def tracking_close() -> None:
        closed.append(True)
        original_close()

    http.close = tracking_close  # type: ignore[method-assign]

    with IFlowSearchClient(api_key="test-key", http_client=http) as client:
        client.web_search(query="q")

    # http_client was injected → owns_client is False, so we don't close it.
    # Verify the context manager does not double-close the injected client.
    assert closed == []
