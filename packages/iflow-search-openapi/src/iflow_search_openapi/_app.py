"""FastAPI app factory (design §11; private — not part of the public API).

``build_app`` wires together middlewares, routes, exception handlers, and the
custom OpenAPI schema generator. The async client is owned by the caller of
``build_app`` (typically :func:`iflow_search_openapi._bin.main`); the app does
not aclose it on shutdown — the CLI's ``finally`` block does.

Middleware order matters (design §9.5):

1. CORS (Starlette's :class:`CORSMiddleware`) — runs first so OPTIONS preflight
   completes before the auth dependency, which would otherwise 401.
2. Body-size limit.
3. (per-route) bearer auth dependency.

Exception handlers re-shape FastAPI's default error responses into the uniform
``{"ok": false, "error": ...}`` envelope (design §8.5).
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from fastapi import Depends, FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from iflow_search import AsyncIFlowSearchClient
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.requests import Request

from ._auth import make_auth_dependency
from ._config import ResolvedConfig
from ._cors import BodySizeLimitMiddleware, configure_cors
from ._errors import adapter_error_envelope, status_for_adapter_code
from ._openapi import install_openapi
from ._routes import build_router


def build_app(
    *,
    client: AsyncIFlowSearchClient,
    config: ResolvedConfig,
) -> FastAPI:
    bearer_required = config.auth_token is not None
    auth_dependency = make_auth_dependency(config.auth_token)

    # ``openapi_url=None`` disables FastAPI's built-in /openapi.json route so we
    # can mount our own that flows through the bearer dependency (design §7.3).
    app = FastAPI(
        title="iFlow Search OpenAPI Tools",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )

    # Body-size limit is wired *before* the CORS middleware so the 413 short-
    # circuits regardless of origin. CORS still gets a chance to add response
    # headers because it runs as an outer-layer middleware (`add_middleware`
    # pushes onto the stack in reverse-execution order).
    app.add_middleware(BodySizeLimitMiddleware)
    configure_cors(app, config.cors_origin)

    router = build_router(client=client, auth_dependency=auth_dependency)
    app.include_router(router)

    @app.get(
        "/openapi.json",
        include_in_schema=False,
        dependencies=[Depends(auth_dependency)],
    )
    async def _openapi_schema() -> JSONResponse:
        return JSONResponse(app.openapi())

    install_openapi(app, bearer_required=bearer_required)

    _install_exception_handlers(app)

    return app


def _install_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(RequestValidationError)
    async def _validation_handler(_request: Request, exc: RequestValidationError) -> JSONResponse:
        envelope = adapter_error_envelope(
            code="invalid_input",
            message="Request body failed validation.",
            detail=_safe_validation_errors(exc.errors()),
        )
        return JSONResponse(envelope, status_code=status_for_adapter_code("invalid_input"))

    @app.exception_handler(StarletteHTTPException)
    async def _http_exception_handler(
        _request: Request, exc: StarletteHTTPException
    ) -> JSONResponse:
        # Auth handler already produced a uniform envelope as the detail; keep it.
        if isinstance(exc, HTTPException) and isinstance(exc.detail, dict) and "code" in exc.detail:
            return JSONResponse({"ok": False, "error": exc.detail}, status_code=exc.status_code)

        # Map well-known status codes that Starlette emits before any of our
        # handlers run (typically 404 / 405 from the router).
        if exc.status_code == 404:
            return JSONResponse(
                adapter_error_envelope(code="not_found", message="No such route."),
                status_code=404,
            )
        if exc.status_code == 405:
            return JSONResponse(
                adapter_error_envelope(
                    code="method_not_allowed",
                    message="HTTP method not allowed on this path.",
                ),
                status_code=405,
            )

        # Fallback for any other HTTPException raised inside the stack.
        message = exc.detail if isinstance(exc.detail, str) else "Request failed."
        return JSONResponse(
            adapter_error_envelope(code="internal_error", message=message),
            status_code=exc.status_code,
        )

    @app.exception_handler(Exception)
    async def _catchall(_request: Request, exc: Exception) -> JSONResponse:
        # Never reaches asyncio.CancelledError — it inherits BaseException,
        # not Exception. That preserves cooperative cancellation (design §8.4).
        return JSONResponse(
            adapter_error_envelope(
                code="internal_error",
                message="An unexpected error occurred.",
            ),
            status_code=status_for_adapter_code("internal_error"),
        )


def _safe_validation_errors(errors: Sequence[Any]) -> list[dict[str, Any]]:
    """Strip non-JSON-serialisable fields (typically ``ctx``) from Pydantic
    validation error dicts so the envelope round-trips through ``JSONResponse``.
    """
    cleaned: list[dict[str, Any]] = []
    for err in errors:
        cleaned.append(
            {
                "loc": [str(segment) for segment in err.get("loc", [])],
                "msg": str(err.get("msg", "")),
                "type": str(err.get("type", "")),
            }
        )
    return cleaned


__all__ = ["build_app"]
