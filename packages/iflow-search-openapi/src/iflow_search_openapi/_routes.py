"""Route handlers (design §6, §13.1).

Three POST tool endpoints plus ``/health``. Each tool route:

1. Validates the body against its Pydantic schema (FastAPI handles this).
2. Calls the matching method on :class:`AsyncIFlowSearchClient` from the core.
3. Catches :class:`IFlowError`; routes ``business_no_results`` to a synthetic
   success envelope (design §13.1); maps everything else via
   :func:`status_for_iflow_error` + :func:`iflow_error_to_envelope`.
4. On success, serialises with ``model_dump(mode="json", by_alias=False,
   exclude={"raw"})`` and wraps in ``{"ok": true, "data": ...}``.

Each tool route also declares ``response_model=...`` (the matching ``*Success``
class in :mod:`._schemas`). Because handlers return :class:`fastapi.responses.JSONResponse`
directly, Pydantic does NOT re-serialise the body — the runtime envelope is
unchanged. The sole purpose is the OpenAPI schema: without ``response_model``,
FastAPI emits ``"schema": {}`` for the 200 response, which Coze and other strict
tool hosts reject at import time and which causes payload-stripping at runtime
(see platform-smoke 2026-05-25).

The async client is shared across all requests — one connection pool per
process — and owned by ``_app.build_app``.

``asyncio.CancelledError`` is never caught here. Routes ``await`` the core
methods directly; cancellation propagates as itself.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from iflow_search import AsyncIFlowSearchClient
from iflow_search.errors import IFlowBusinessError, IFlowError

from ._errors import iflow_error_to_envelope, status_for_iflow_error
from ._schemas import (
    ImageSearchBody,
    ImageSearchSuccess,
    WebFetchBody,
    WebFetchSuccess,
    WebSearchBody,
    WebSearchSuccess,
)
from ._version import __version__


def _success(data: dict[str, Any]) -> dict[str, Any]:
    return {"ok": True, "data": data}


def _error_response(err: IFlowError) -> JSONResponse:
    return JSONResponse(
        iflow_error_to_envelope(err),
        status_code=status_for_iflow_error(err),
    )


def _no_results_web_search(query: str) -> dict[str, Any]:
    # Synthesised "zero hits" success (design §13.1). Shape matches what the
    # core would return for a normal-but-empty result set.
    return {
        "query": query,
        "results": [],
        "took_ms": 0,
    }


def _no_results_image_search(query: str) -> dict[str, Any]:
    return {
        "query": query,
        "images": [],
        "took_ms": 0,
    }


def build_router(
    *,
    client: AsyncIFlowSearchClient,
    auth_dependency: Any,
) -> APIRouter:
    """Build the FastAPI router. ``auth_dependency`` is the per-route bearer
    check; ``/health`` deliberately does not depend on it (design §7.3).
    """

    router = APIRouter()

    @router.get("/health", tags=["operational"])
    async def health() -> dict[str, Any]:
        return {"ok": True, "version": __version__}

    @router.post(
        "/tools/iflow_web_search",
        operation_id="iflow_web_search",
        tags=["tools"],
        dependencies=[Depends(auth_dependency)],
        response_model=WebSearchSuccess,
    )
    async def web_search(body: WebSearchBody, _request: Request) -> JSONResponse:
        try:
            result = await client.web_search(query=body.query, count=body.count)
        except IFlowBusinessError as err:
            if err.code == "business_no_results":
                return JSONResponse(_success(_no_results_web_search(body.query)))
            return _error_response(err)
        except IFlowError as err:
            return _error_response(err)
        data = result.model_dump(mode="json", by_alias=False, exclude={"raw"})
        return JSONResponse(_success(data))

    @router.post(
        "/tools/iflow_image_search",
        operation_id="iflow_image_search",
        tags=["tools"],
        dependencies=[Depends(auth_dependency)],
        response_model=ImageSearchSuccess,
    )
    async def image_search(body: ImageSearchBody, _request: Request) -> JSONResponse:
        try:
            result = await client.image_search(query=body.query, count=body.count)
        except IFlowBusinessError as err:
            if err.code == "business_no_results":
                return JSONResponse(_success(_no_results_image_search(body.query)))
            return _error_response(err)
        except IFlowError as err:
            return _error_response(err)
        data = result.model_dump(mode="json", by_alias=False, exclude={"raw"})
        return JSONResponse(_success(data))

    @router.post(
        "/tools/iflow_web_fetch",
        operation_id="iflow_web_fetch",
        tags=["tools"],
        dependencies=[Depends(auth_dependency)],
        response_model=WebFetchSuccess,
    )
    async def web_fetch(body: WebFetchBody, _request: Request) -> JSONResponse:
        try:
            result = await client.web_fetch(url=body.url)
        except IFlowError as err:
            # web_fetch has no "no results" success-fallback (design §13.1):
            # business_fetch_failed → 502 like any other upstream parse failure.
            return _error_response(err)
        data = result.model_dump(mode="json", by_alias=False, exclude={"raw"})
        return JSONResponse(_success(data))

    return router


__all__ = ["build_router"]
