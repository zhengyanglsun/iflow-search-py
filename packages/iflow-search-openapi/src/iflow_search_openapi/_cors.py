"""CORS middleware factory and body-size guard (design §9, §6.4).

CORS uses Starlette's built-in :class:`CORSMiddleware` — FastAPI is built on
Starlette, so this is the same middleware FastAPI's docs recommend. We only
wire it in when ``IFLOW_OPENAPI_CORS_ORIGIN`` is configured; in unset mode no
CORS headers are emitted at all.

The body-size guard is a small custom middleware. It inspects ``Content-Length``
and short-circuits to HTTP 413 with the uniform envelope when the declared body
exceeds 1 MiB. Chunked uploads without ``Content-Length`` are not capped at the
middleware layer — all sanctioned clients (Open WebUI, Coze, the smoke script)
send ``Content-Length`` on JSON POSTs, and ``uvicorn``'s own buffer ceilings
catch pathological streams before they reach a route handler.
"""

from __future__ import annotations

from starlette.middleware.cors import CORSMiddleware
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from ._errors import adapter_error_envelope

#: Maximum accepted request body size, in bytes (design §6.4).
MAX_BODY_BYTES: int = 1 * 1024 * 1024

#: Headers a browser is allowed to send on cross-origin requests (design §9.3).
_ALLOW_HEADERS: list[str] = ["Content-Type", "Authorization", "X-Session-Id"]

#: Methods the server actually accepts (design §9.4).
_ALLOW_METHODS: list[str] = ["GET", "POST", "OPTIONS"]


def configure_cors(app: ASGIApp, origin: str | None) -> None:
    """Attach Starlette's CORSMiddleware when an origin is configured.

    Accepts the FastAPI app (which subclasses Starlette's ``Starlette``); the
    type is widened to ``ASGIApp`` for testability.
    """
    if origin is None:
        return
    # Wildcard origin must not be combined with allow_credentials per browser
    # spec; we never use credentials anyway. Exact origin is echoed verbatim.
    app.add_middleware(  # type: ignore[attr-defined]
        CORSMiddleware,
        allow_origins=["*"] if origin == "*" else [origin],
        allow_credentials=False,
        allow_methods=_ALLOW_METHODS,
        allow_headers=_ALLOW_HEADERS,
        expose_headers=[],
    )


class BodySizeLimitMiddleware:
    """Reject requests whose ``Content-Length`` exceeds :data:`MAX_BODY_BYTES`.

    The response is the uniform error envelope ``{"ok": false, "error": ...}``
    with HTTP 413 and code ``payload_too_large``.
    """

    def __init__(self, app: ASGIApp, max_bytes: int = MAX_BODY_BYTES) -> None:
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        content_length = _content_length(scope)
        if content_length is not None and content_length > self.max_bytes:
            await self._reject(scope, receive, send)
            return

        await self.app(scope, receive, send)

    async def _reject(self, scope: Scope, receive: Receive, send: Send) -> None:
        envelope = adapter_error_envelope(
            code="payload_too_large",
            message=f"Request body exceeds {self.max_bytes} bytes.",
        )
        response = JSONResponse(envelope, status_code=413)
        await response(scope, receive, send)


def _content_length(scope: Scope) -> int | None:
    for name, value in scope.get("headers", []):
        if name.lower() == b"content-length":
            try:
                return int(value.decode("latin-1"))
            except ValueError:
                return None
    return None


__all__ = [
    "BodySizeLimitMiddleware",
    "MAX_BODY_BYTES",
    "configure_cors",
]
