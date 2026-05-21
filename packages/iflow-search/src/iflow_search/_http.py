"""Shared pure helpers between the sync and async clients.

Keeping these as free functions (no ``self``) avoids the temptation to run the
sync client inside a thread pool to satisfy the async one — that pattern
deadlocks under FastAPI/asyncio. Both clients now share validation and
payload-shaping logic, while the actual ``httpx`` call lives in each client
class.
"""

from __future__ import annotations

import json
import time
from typing import Any

from .errors import IFlowAPIError, IFlowValidationError


def build_web_search_payload(*, query: str, count: int | None) -> dict[str, Any]:
    if not isinstance(query, str) or not query.strip():
        raise IFlowValidationError(
            "query must be a non-empty string",
            code="missing_param",
        )
    payload: dict[str, Any] = {"keywords": query}
    if count is not None:
        if not isinstance(count, int) or isinstance(count, bool):
            raise IFlowValidationError(
                "count must be an int when provided",
                code="invalid_param",
            )
        if count < 1:
            raise IFlowValidationError(
                "count must be >= 1 when provided",
                code="invalid_param",
            )
        payload["num"] = count
    return payload


def build_image_search_payload(*, query: str, count: int | None) -> dict[str, Any]:
    # Identical to web_search payload shape.
    if not isinstance(query, str) or not query.strip():
        raise IFlowValidationError(
            "query must be a non-empty string",
            code="missing_param",
        )
    payload: dict[str, Any] = {"keywords": query}
    if count is not None:
        if not isinstance(count, int) or isinstance(count, bool):
            raise IFlowValidationError(
                "count must be an int when provided",
                code="invalid_param",
            )
        if count < 1:
            raise IFlowValidationError(
                "count must be >= 1 when provided",
                code="invalid_param",
            )
        payload["num"] = count
    return payload


def build_web_fetch_payload(*, url: str) -> dict[str, Any]:
    if not isinstance(url, str) or not url.strip():
        raise IFlowValidationError(
            "url must be a non-empty string",
            code="missing_param",
        )
    return {"url": url}


def make_request_info(*, method: str, full_url: str, endpoint: str) -> dict[str, Any]:
    """Build the ``request`` attribute attached to raised exceptions.

    Deliberately omits headers and body — we never want to leak the API key
    or request payloads through error attributes.
    """
    return {"method": method, "url": full_url, "endpoint": endpoint}


def now_ns() -> int:
    return time.monotonic_ns()


def elapsed_ms(start_ns: int) -> int:
    return (time.monotonic_ns() - start_ns) // 1_000_000


def parse_json_body(
    *,
    body: bytes | str,
    request_info: dict[str, Any],
    status_code: int,
) -> dict[str, Any]:
    """Best-effort JSON decode. Wraps decode failures as :class:`IFlowAPIError`."""
    if isinstance(body, bytes):
        try:
            text = body.decode("utf-8", errors="replace")
        except Exception:  # pragma: no cover
            text = ""
    else:
        text = body

    try:
        parsed = json.loads(text)
    except (ValueError, json.JSONDecodeError) as exc:
        truncated = text[:500] if text else None
        raise IFlowAPIError(
            f"iFlow returned a non-JSON response (HTTP {status_code})",
            code="api_invalid_json",
            status_code=status_code,
            request=request_info,
            response_body_truncated=truncated,
        ) from exc
    if not isinstance(parsed, dict):
        truncated = text[:500] if text else None
        raise IFlowAPIError(
            "iFlow response root must be a JSON object",
            code="api_invalid_json",
            status_code=status_code,
            request=request_info,
            response_body_truncated=truncated,
        )
    return parsed


def join_url(base_url: str, path: str) -> str:
    base = base_url.rstrip("/")
    if not path.startswith("/"):
        path = "/" + path
    return base + path


__all__ = [
    "build_web_search_payload",
    "build_image_search_payload",
    "build_web_fetch_payload",
    "make_request_info",
    "now_ns",
    "elapsed_ms",
    "parse_json_body",
    "join_url",
]
