"""Error → JSON envelope mapping (design §8).

The uniform shape is::

    {"ok": false, "error": {"code": ..., "message": ..., ...}}

Dispatch is on the core's stable ``IFlowError.code`` string (design §8.2 of the
core; §8.3 here). Class identity is deliberately not part of the contract — new
``IFlowError`` subclasses in a future core release fall through to HTTP 502 with
the core's code preserved verbatim.

The adapter introduces a small set of its own codes for things the core never
sees (auth failure, bad route, oversized body, etc.); they live in
``_ADAPTER_STATUS``.

``asyncio.CancelledError`` is **never** handled here. Callers must catch
``IFlowError`` / ``Exception`` only — never ``BaseException``.
"""

from __future__ import annotations

from typing import Any

from iflow_search.errors import (
    IFlowAPIError,
    IFlowAuthError,
    IFlowBusinessError,
    IFlowConfigError,
    IFlowError,
    IFlowInsufficientCreditsError,
    IFlowNetworkError,
    IFlowRateLimitError,
    IFlowTimeoutError,
    IFlowValidationError,
)

# IFlowError.code → HTTP status (design §8.3). business_no_results is the only
# code that does NOT use this table: it is special-cased in the route layer
# (design §13.1) and synthesises a success envelope.
_IFLOW_CODE_STATUS: dict[str, int] = {
    "api_unauthorized": 401,
    "api_forbidden": 403,
    "business_invalid_api_key": 401,
    "api_bad_request": 400,
    "business_bad_request": 400,
    "api_rate_limited": 429,
    "business_rate_limited": 429,
    "business_insufficient_credits": 402,
    "business_fetch_failed": 502,
    "api_server_error": 502,
    "business_server_error": 502,
    "api_invalid_json": 502,
    "business_unknown": 502,
    "network_timeout": 504,
    "network_error": 502,
}

# Class-based fallback when the code is not in _IFLOW_CODE_STATUS (e.g. a core
# release introduces new codes, or IFlowValidationError uses code="validation_*").
_IFLOW_CLASS_STATUS: list[tuple[type[IFlowError], int]] = [
    (IFlowValidationError, 400),
    (IFlowAuthError, 401),
    (IFlowRateLimitError, 429),
    (IFlowInsufficientCreditsError, 402),
    (IFlowTimeoutError, 504),
    (IFlowNetworkError, 502),
    (IFlowAPIError, 502),
    (IFlowBusinessError, 502),
    (IFlowConfigError, 500),  # should never reach the request layer; defensive only
]

# Codes the adapter introduces. The mapping is exposed so route handlers and
# tests can look up the canonical status for an adapter-introduced code.
_ADAPTER_STATUS: dict[str, int] = {
    "unauthorized": 401,
    "method_not_allowed": 405,
    "not_found": 404,
    "invalid_input": 400,
    "payload_too_large": 413,
    "internal_error": 500,
}


def status_for_iflow_error(err: IFlowError) -> int:
    status = _IFLOW_CODE_STATUS.get(err.code)
    if status is not None:
        return status
    for cls, fallback in _IFLOW_CLASS_STATUS:
        if isinstance(err, cls):
            return fallback
    return 502


def iflow_error_to_envelope(err: IFlowError) -> dict[str, Any]:
    error_payload: dict[str, Any] = {
        "code": err.code,
        "message": err.message,
        "type": type(err).__name__,
    }
    if isinstance(err, IFlowAPIError) and err.status_code is not None:
        error_payload["status_code"] = err.status_code
    if isinstance(err, IFlowBusinessError):
        error_payload["business_code"] = err.business_code
    if err.response_body_truncated is not None:
        error_payload["response_body_truncated"] = err.response_body_truncated
    return {"ok": False, "error": error_payload}


def adapter_error_envelope(
    *,
    code: str,
    message: str,
    detail: Any = None,
) -> dict[str, Any]:
    """Build an envelope for an error the adapter itself raised (not from the core)."""
    error_payload: dict[str, Any] = {"code": code, "message": message}
    if detail is not None:
        error_payload["detail"] = detail
    return {"ok": False, "error": error_payload}


def status_for_adapter_code(code: str) -> int:
    return _ADAPTER_STATUS.get(code, 500)


__all__ = [
    "adapter_error_envelope",
    "iflow_error_to_envelope",
    "status_for_adapter_code",
    "status_for_iflow_error",
]
