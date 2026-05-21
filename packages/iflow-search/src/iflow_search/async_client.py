"""Asynchronous iFlow Search client.

Mirror of :class:`iflow_search.IFlowSearchClient` over :class:`httpx.AsyncClient`.
Both clients share the pure helpers in :mod:`iflow_search._http` and
:mod:`iflow_search._normalize` — they do *not* delegate to each other (running
sync code from async via a thread pool deadlocks under FastAPI/asyncio).
"""

from __future__ import annotations

import json
import os
from types import TracebackType
from typing import Any

import httpx

from . import _http, _normalize
from ._attribution import build_attribution_headers
from ._version import __version__ as _PACKAGE_VERSION
from .config import (
    DEFAULT_BASE_URL,
    DEFAULT_INTEGRATION_NAME,
    DEFAULT_SOURCE,
    DEFAULT_TIMEOUT_S,
    ENV_API_KEY,
    IMAGE_SEARCH_PATH,
    WEB_FETCH_PATH,
    WEB_SEARCH_PATH,
)
from .errors import (
    IFlowConfigError,
    IFlowNetworkError,
    IFlowTimeoutError,
)
from .models import ImageSearchResponse, WebFetchResponse, WebSearchResponse


class AsyncIFlowSearchClient:
    """Async client for the iFlow Search REST API.

    Construction either takes an explicit ``api_key=`` or reads ``IFLOW_API_KEY``
    from the process environment. Missing keys raise
    :class:`~iflow_search.errors.IFlowConfigError`.

    Pass ``http_client=`` to share an existing :class:`httpx.AsyncClient` (e.g.
    for connection pooling across many clients or for injecting an
    :class:`httpx.MockTransport` in tests).
    """

    def __init__(
        self,
        *,
        api_key: str | None = None,
        source: str | None = None,
        integration_name: str | None = None,
        integration_version: str | None = None,
        base_url: str | None = None,
        timeout: float | None = None,
        http_client: httpx.AsyncClient | None = None,
        mcp_client_name: str | None = None,
        mcp_client_version: str | None = None,
    ) -> None:
        resolved_key = api_key if api_key is not None else os.environ.get(ENV_API_KEY)
        if not resolved_key:
            raise IFlowConfigError(
                f"api_key not provided and {ENV_API_KEY} is not set",
                code="missing_api_key",
            )

        self._api_key: str = resolved_key
        self._source: str = source or DEFAULT_SOURCE
        self._integration_name: str = integration_name or DEFAULT_INTEGRATION_NAME
        self._integration_version: str = integration_version or _PACKAGE_VERSION
        self._base_url: str = base_url or DEFAULT_BASE_URL
        self._timeout: float = float(timeout if timeout is not None else DEFAULT_TIMEOUT_S)
        self._mcp_client_name: str | None = mcp_client_name
        self._mcp_client_version: str | None = mcp_client_version

        self._headers: dict[str, str] = build_attribution_headers(
            api_key=self._api_key,
            source=self._source,
            integration_name=self._integration_name,
            integration_version=self._integration_version,
            mcp_client_name=self._mcp_client_name,
            mcp_client_version=self._mcp_client_version,
        )

        self._owns_client: bool = http_client is None
        self._client: httpx.AsyncClient = http_client or httpx.AsyncClient(timeout=self._timeout)

    # -- context manager protocol -------------------------------------------------

    async def __aenter__(self) -> AsyncIFlowSearchClient:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    # -- public methods -----------------------------------------------------------

    async def web_search(
        self,
        *,
        query: str,
        count: int | None = None,
    ) -> WebSearchResponse:
        payload = _http.build_web_search_payload(query=query, count=count)
        envelope, took_ms = await self._post(WEB_SEARCH_PATH, payload)
        parsed = _normalize.parse_envelope(
            envelope=envelope,
            request_info=_http.make_request_info(
                method="POST",
                full_url=_http.join_url(self._base_url, WEB_SEARCH_PATH),
                endpoint="web_search",
            ),
            raw_body_truncated=_normalize.truncate_body(_safe_json_repr(envelope)),
        )
        return _normalize.build_web_search_response(
            data=parsed["data"],
            raw=parsed["raw"],
            took_ms=took_ms,
            query_echo=query,
        )

    async def image_search(
        self,
        *,
        query: str,
        count: int | None = None,
    ) -> ImageSearchResponse:
        payload = _http.build_image_search_payload(query=query, count=count)
        envelope, took_ms = await self._post(IMAGE_SEARCH_PATH, payload)
        parsed = _normalize.parse_envelope(
            envelope=envelope,
            request_info=_http.make_request_info(
                method="POST",
                full_url=_http.join_url(self._base_url, IMAGE_SEARCH_PATH),
                endpoint="image_search",
            ),
            raw_body_truncated=_normalize.truncate_body(_safe_json_repr(envelope)),
        )
        return _normalize.build_image_search_response(
            data=parsed["data"],
            raw=parsed["raw"],
            took_ms=took_ms,
            query_echo=query,
        )

    async def web_fetch(self, *, url: str) -> WebFetchResponse:
        payload = _http.build_web_fetch_payload(url=url)
        envelope, took_ms = await self._post(WEB_FETCH_PATH, payload)
        parsed = _normalize.parse_envelope(
            envelope=envelope,
            request_info=_http.make_request_info(
                method="POST",
                full_url=_http.join_url(self._base_url, WEB_FETCH_PATH),
                endpoint="web_fetch",
            ),
            raw_body_truncated=_normalize.truncate_body(_safe_json_repr(envelope)),
        )
        return _normalize.build_web_fetch_response(
            data=parsed["data"],
            raw=parsed["raw"],
            took_ms=took_ms,
            url_echo=url,
        )

    # -- internals ----------------------------------------------------------------

    async def _post(
        self,
        path: str,
        payload: dict[str, Any],
    ) -> tuple[dict[str, Any], int]:
        full_url = _http.join_url(self._base_url, path)
        request_info = _http.make_request_info(
            method="POST",
            full_url=full_url,
            endpoint=path,
        )
        start = _http.now_ns()
        try:
            response = await self._client.post(
                full_url,
                json=payload,
                headers=self._headers,
                timeout=self._timeout,
            )
        except httpx.TimeoutException as exc:
            raise IFlowTimeoutError(
                f"iFlow request timed out after {self._timeout:.1f}s",
                code="network_timeout",
                request=request_info,
            ) from exc
        except httpx.NetworkError as exc:
            raise IFlowNetworkError(
                f"network error calling iFlow: {exc}",
                code="network_error",
                request=request_info,
            ) from exc
        took_ms = _http.elapsed_ms(start)

        _normalize.raise_for_http_status(
            status_code=response.status_code,
            body=response.content,
            request_info=request_info,
        )

        envelope = _http.parse_json_body(
            body=response.content,
            request_info=request_info,
            status_code=response.status_code,
        )
        return envelope, took_ms


def _safe_json_repr(envelope: dict[str, Any]) -> str:
    try:
        return json.dumps(envelope, ensure_ascii=False)
    except Exception:  # pragma: no cover — defensive
        return repr(envelope)


__all__ = ["AsyncIFlowSearchClient"]
