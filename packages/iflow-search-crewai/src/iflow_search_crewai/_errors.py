"""Map iFlow SDK errors to CrewAI-friendly JSON error strings."""

from __future__ import annotations

import json
from typing import Any

from iflow_search import (
    IFlowAuthError,
    IFlowError,
    IFlowInsufficientCreditsError,
    IFlowNetworkError,
    IFlowRateLimitError,
    IFlowTimeoutError,
)


def format_iflow_error(exc: IFlowError) -> str:
    """Return a short JSON error string; never includes secrets."""
    hint = _hint_for_error(exc)
    payload: dict[str, Any] = {
        "error": hint,
        "code": exc.code,
    }
    return json.dumps(payload, ensure_ascii=False)


def _hint_for_error(exc: IFlowError) -> str:
    if isinstance(exc, IFlowAuthError):
        return "Authentication failed. Check that IFLOW_API_KEY is valid."
    if isinstance(exc, IFlowRateLimitError):
        return "Rate limit exceeded. Retry later or reduce concurrent tool calls."
    if isinstance(exc, IFlowInsufficientCreditsError):
        return "Insufficient iFlow account credits. Check your iFlow account balance."
    if isinstance(exc, IFlowTimeoutError):
        return "Request timed out. Retry with a smaller query or increase IFLOW_TIMEOUT_MS."
    if isinstance(exc, IFlowNetworkError):
        return "Network error while contacting iFlow Search. Check connectivity and retry."
    message = exc.message.strip() if exc.message else "iFlow Search request failed."
    if _looks_like_secret(message):
        return "iFlow Search request failed."
    return message


def _looks_like_secret(text: str) -> bool:
    lowered = text.lower()
    return "authorization" in lowered or "bearer" in lowered or "api_key" in lowered


__all__ = ["format_iflow_error"]
