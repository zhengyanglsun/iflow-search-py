"""Shared pytest fixtures and helpers for the iflow-search-mcp test suite.

All tests are offline. The MCP adapter never hits the network from unit tests —
the end-to-end stdio path is covered by ``scripts/smoke_stdio.py`` (opt-in via
``IFLOW_MCP_SMOKE=1``).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

import httpx
import pytest
from iflow_search import AsyncIFlowSearchClient


@dataclass
class CapturedRequest:
    method: str
    url: str
    headers: dict[str, str]
    body: bytes


@dataclass
class _Recorder:
    calls: list[CapturedRequest] = field(default_factory=list)


def make_mock_transport(
    handler: Callable[[httpx.Request], httpx.Response],
) -> tuple[httpx.MockTransport, _Recorder]:
    """Wrap an httpx.MockTransport so every outbound request is recorded."""

    recorder = _Recorder()

    def _intercept(request: httpx.Request) -> httpx.Response:
        recorder.calls.append(
            CapturedRequest(
                method=request.method,
                url=str(request.url),
                headers={k.lower(): v for k, v in request.headers.items()},
                body=request.content,
            )
        )
        return handler(request)

    return httpx.MockTransport(_intercept), recorder


def make_async_client(
    handler: Callable[[httpx.Request], httpx.Response],
    *,
    api_key: str = "test-key",
    **kwargs: Any,
) -> tuple[AsyncIFlowSearchClient, _Recorder]:
    transport, recorder = make_mock_transport(handler)
    http_client = httpx.AsyncClient(transport=transport)
    client = AsyncIFlowSearchClient(api_key=api_key, http_client=http_client, **kwargs)
    return client, recorder


@pytest.fixture
def make_async_client_factory() -> Callable[..., tuple[AsyncIFlowSearchClient, _Recorder]]:
    return make_async_client
