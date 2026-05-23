"""Shared pytest fixtures for iflow-search-langchain.

All tests are offline. Every client is constructed with the literal string
``"test-key"`` and an injected ``httpx.MockTransport``. No real ``IFLOW_API_KEY``
is ever read.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

import httpx
import pytest


@dataclass
class CapturedRequest:
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
    calls: list[CapturedRequest] = field(default_factory=list)


@pytest.fixture
def make_mock_transport() -> Callable[..., tuple[httpx.MockTransport, _Recorder]]:
    """Return a factory that wraps an ``httpx.MockTransport`` and records every
    outbound request as a :class:`CapturedRequest`.
    """

    def _build(
        handler: Callable[[httpx.Request], httpx.Response],
    ) -> tuple[httpx.MockTransport, _Recorder]:
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

    return _build


@pytest.fixture
def fake_envelope() -> Callable[..., dict[str, Any]]:
    """Build a canonical iFlow response envelope (mirrors the core's fixture)."""

    def _build(
        *,
        success: bool = True,
        code: str = "200",
        message: str = "ok",
        data: Any = None,
    ) -> dict[str, Any]:
        return {
            "success": success,
            "code": code,
            "message": message,
            "data": data if data is not None else {},
            "extra": None,
            "exception": None,
        }

    return _build
