"""Shared test fixtures.

All tests run **offline**. The ``mock_iflow`` fixture returns a list of
captured requests so each test can assert exactly what hit the wire. No real
``IFLOW_API_KEY`` is ever read — every client is constructed with the literal
string ``"test-key"``.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

import httpx
import pytest


@pytest.fixture
def fake_envelope() -> Callable[..., dict[str, Any]]:
    """Build a canonical iFlow response envelope."""

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


class CapturedRequest:
    """A snapshot of an outbound request, taken before we return the response."""

    def __init__(self, request: httpx.Request) -> None:
        self.method = request.method
        self.url = str(request.url)
        self.headers = dict(request.headers)
        body = request.content
        try:
            self.body_json: Any = json.loads(body.decode("utf-8")) if body else None
        except Exception:
            self.body_json = None
        self.body_raw = body


@pytest.fixture
def make_mock_transport() -> Callable[..., tuple[httpx.MockTransport, list[CapturedRequest]]]:
    """Return a factory that builds an ``httpx.MockTransport`` recording every request.

    The factory takes a callable ``handler(captured) -> httpx.Response``.
    """

    def _build(
        handler: Callable[[CapturedRequest], httpx.Response],
    ) -> tuple[httpx.MockTransport, list[CapturedRequest]]:
        captured: list[CapturedRequest] = []

        def transport_handler(request: httpx.Request) -> httpx.Response:
            snapshot = CapturedRequest(request)
            captured.append(snapshot)
            return handler(snapshot)

        return httpx.MockTransport(transport_handler), captured

    return _build
