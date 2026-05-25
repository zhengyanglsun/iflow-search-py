"""Shared pytest fixtures for iflow-search-openapi.

All tests are offline. The upstream iFlow client is built with an
``httpx.AsyncClient`` whose transport is an :class:`httpx.MockTransport`, so
outbound iFlow requests are intercepted and asserted on. The inbound side is
exercised through :class:`httpx.ASGITransport` against the real FastAPI app —
so middleware, dependencies, exception handlers, and the OpenAPI generator all
run for every test.

No test reads ``IFLOW_API_KEY`` from the process env; the literal string
``"test-key"`` is used everywhere.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass, field
from typing import Any

import httpx
import pytest
import pytest_asyncio
from iflow_search import AsyncIFlowSearchClient

from iflow_search_openapi._app import build_app
from iflow_search_openapi._config import ResolvedConfig
from iflow_search_openapi._constants import INTEGRATION_NAME, SOURCE
from iflow_search_openapi._version import __version__


@dataclass
class CapturedUpstream:
    method: str
    url: str
    headers: dict[str, str]
    body: bytes

    @property
    def body_json(self) -> Any:
        if not self.body:
            return None
        try:
            return json.loads(self.body.decode("utf-8"))
        except Exception:
            return None


@dataclass
class _Recorder:
    calls: list[CapturedUpstream] = field(default_factory=list)


def make_config(
    *,
    api_key: str = "test-key",
    base_url: str | None = "https://upstream.example.invalid",
    timeout_s: float | None = 5.0,
    host: str = "127.0.0.1",
    port: int = 8787,
    auth_token: str | None = None,
    cors_origin: str | None = None,
    client_name: str | None = None,
) -> ResolvedConfig:
    return ResolvedConfig(
        api_key=api_key,
        base_url=base_url,
        timeout_s=timeout_s,
        host=host,
        port=port,
        auth_token=auth_token,
        cors_origin=cors_origin,
        client_name=client_name,
    )


def make_mock_transport(
    handler: Callable[[httpx.Request], httpx.Response],
) -> tuple[httpx.MockTransport, _Recorder]:
    recorder = _Recorder()

    def _intercept(request: httpx.Request) -> httpx.Response:
        recorder.calls.append(
            CapturedUpstream(
                method=request.method,
                url=str(request.url),
                headers={k.lower(): v for k, v in request.headers.items()},
                body=request.content,
            )
        )
        return handler(request)

    return httpx.MockTransport(_intercept), recorder


def make_app_and_client(
    *,
    upstream_handler: Callable[[httpx.Request], httpx.Response],
    config: ResolvedConfig | None = None,
) -> tuple[Any, AsyncIFlowSearchClient, _Recorder]:
    """Build (app, core_client, recorder).

    The core client is constructed with our mock transport. Attribution kwargs
    are passed verbatim so outbound headers match what the CLI would produce.
    """
    config = config or make_config()
    transport, recorder = make_mock_transport(upstream_handler)
    http_client = httpx.AsyncClient(
        transport=transport,
        timeout=config.timeout_s if config.timeout_s is not None else 5.0,
    )
    core_client = AsyncIFlowSearchClient(
        api_key=config.api_key,
        base_url=config.base_url,
        timeout=config.timeout_s,
        source=SOURCE,
        integration_name=INTEGRATION_NAME,
        integration_version=__version__,
        http_client=http_client,
    )
    app = build_app(client=core_client, config=config)
    return app, core_client, recorder


@pytest_asyncio.fixture
async def client_factory() -> AsyncIterator[
    Callable[
        ...,
        tuple[httpx.AsyncClient, AsyncIFlowSearchClient, _Recorder],
    ]
]:
    """Yield a factory that builds (httpx test client, core client, recorder).

    The factory is parametrised by ``upstream_handler`` and an optional
    ``config``. Multiple invocations are allowed per test; every constructed
    client + core_client is closed at fixture teardown.
    """
    opened: list[tuple[httpx.AsyncClient, AsyncIFlowSearchClient]] = []

    def _build(
        *,
        upstream_handler: Callable[[httpx.Request], httpx.Response],
        config: ResolvedConfig | None = None,
    ) -> tuple[httpx.AsyncClient, AsyncIFlowSearchClient, _Recorder]:
        app, core_client, recorder = make_app_and_client(
            upstream_handler=upstream_handler, config=config
        )
        test_client = httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://testserver",
        )
        opened.append((test_client, core_client))
        return test_client, core_client, recorder

    yield _build

    for test_client, core_client in opened:
        await test_client.aclose()
        await core_client.aclose()


def envelope(
    *,
    success: bool = True,
    code: str = "200",
    message: str = "ok",
    data: Any = None,
) -> dict[str, Any]:
    """Canonical iFlow response envelope, matching the core's test fixture shape."""
    return {
        "success": success,
        "code": code,
        "message": message,
        "data": data if data is not None else {},
        "extra": None,
        "exception": None,
    }


__all__ = [
    "CapturedUpstream",
    "client_factory",
    "envelope",
    "make_app_and_client",
    "make_config",
    "make_mock_transport",
]


@pytest.fixture
def envelope_factory() -> Callable[..., dict[str, Any]]:
    return envelope
