"""Envelope → model conversion and error mapping.

All HTTP status and business code → exception translation happens here. The
sync and async clients funnel every response through these helpers so the
mapping stays in one place.
"""

from __future__ import annotations

from typing import Any

from .config import MAX_ERROR_BODY_BYTES
from .errors import (
    IFlowAPIError,
    IFlowAuthError,
    IFlowBusinessError,
    IFlowError,
    IFlowInsufficientCreditsError,
    IFlowRateLimitError,
    IFlowValidationError,
)
from .models import (
    ImageResult,
    ImageSearchResponse,
    WebFetchResponse,
    WebSearchResponse,
    WebSearchResult,
)


def truncate_body(body: str | bytes | None) -> str | None:
    """Truncate a response body to :data:`MAX_ERROR_BODY_BYTES` characters.

    Accepts either ``str`` or ``bytes`` (decoded best-effort) and returns
    ``None`` if the input is ``None`` or empty.
    """
    if body is None:
        return None
    if isinstance(body, bytes):
        try:
            body = body.decode("utf-8", errors="replace")
        except Exception:  # pragma: no cover — decode("utf-8", errors=...) does not raise
            body = repr(body)
    if not body:
        return None
    if len(body) > MAX_ERROR_BODY_BYTES:
        return body[:MAX_ERROR_BODY_BYTES]
    return body


def _coerce_str(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return str(value)


def _coerce_int(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return None
    if isinstance(value, float):
        return int(value)
    return None


def _coerce_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower() in ("true", "1", "yes")
    if isinstance(value, (int, float)):
        return bool(value)
    return False


def raise_for_http_status(
    *,
    status_code: int,
    body: str | bytes | None,
    request_info: dict[str, Any],
) -> None:
    """Raise the appropriate :class:`IFlowError` subclass for a non-2xx HTTP status.

    2xx statuses must be handled by the envelope-level mapping in
    :func:`parse_envelope` instead.
    """
    truncated = truncate_body(body)
    if 200 <= status_code < 300:
        return
    if status_code == 400:
        raise IFlowValidationError(
            f"iFlow returned HTTP 400 Bad Request: {truncated or ''}",
            code="api_bad_request",
            request=request_info,
            response_body_truncated=truncated,
        )
    if status_code == 401:
        raise IFlowAuthError(
            "iFlow rejected the API key (HTTP 401 Unauthorized)",
            code="api_unauthorized",
            request=request_info,
            response_body_truncated=truncated,
        )
    if status_code == 403:
        raise IFlowAuthError(
            "iFlow refused the request (HTTP 403 Forbidden)",
            code="api_forbidden",
            request=request_info,
            response_body_truncated=truncated,
        )
    if status_code == 429:
        raise IFlowRateLimitError(
            "iFlow rate limit exceeded (HTTP 429)",
            code="api_rate_limited",
            request=request_info,
            response_body_truncated=truncated,
        )
    if 500 <= status_code < 600:
        raise IFlowAPIError(
            f"iFlow upstream error (HTTP {status_code})",
            code="api_server_error",
            status_code=status_code,
            request=request_info,
            response_body_truncated=truncated,
        )
    raise IFlowAPIError(
        f"iFlow returned unexpected HTTP {status_code}",
        code="api_http_error",
        status_code=status_code,
        request=request_info,
        response_body_truncated=truncated,
    )


def raise_for_business_code(
    *,
    code: str,
    message: str,
    request_info: dict[str, Any],
    raw_body_truncated: str | None,
) -> None:
    """Raise the appropriate :class:`IFlowError` subclass for a business-level
    failure (``success: false``).

    Code ``"200"`` (success) must be filtered out by the caller before this
    function is invoked.
    """
    if code == "400":
        raise IFlowValidationError(
            message or "iFlow rejected the request parameters",
            code="business_bad_request",
            request=request_info,
            response_body_truncated=raw_body_truncated,
        )
    if code == "40303":
        raise IFlowRateLimitError(
            message or "iFlow rate limit exceeded",
            code="business_rate_limited",
            request=request_info,
            response_body_truncated=raw_body_truncated,
        )
    if code == "60400":
        raise IFlowInsufficientCreditsError(
            message or "iFlow account has insufficient credits",
            code="business_insufficient_credits",
            request=request_info,
            response_body_truncated=raw_body_truncated,
        )
    if code == "90001":
        raise IFlowBusinessError(
            message or "iFlow webFetch failed to parse the target page",
            code="business_fetch_failed",
            business_code=code,
            business_message=message,
            request=request_info,
            response_body_truncated=raw_body_truncated,
        )
    if code == "90002":
        raise IFlowBusinessError(
            message or "iFlow search returned no results",
            code="business_no_results",
            business_code=code,
            business_message=message,
            request=request_info,
            response_body_truncated=raw_body_truncated,
        )
    if code == "90402":
        raise IFlowAuthError(
            message or "iFlow rejected the API key",
            code="business_invalid_api_key",
            request=request_info,
            response_body_truncated=raw_body_truncated,
        )
    if code == "500":
        raise IFlowAPIError(
            message or "iFlow upstream/internal error",
            code="business_server_error",
            status_code=None,
            request=request_info,
            response_body_truncated=raw_body_truncated,
        )
    raise IFlowBusinessError(
        message or f"iFlow returned business error code {code}",
        code="business_unknown",
        business_code=code,
        business_message=message,
        request=request_info,
        response_body_truncated=raw_body_truncated,
    )


def parse_envelope(
    *,
    envelope: dict[str, Any],
    request_info: dict[str, Any],
    raw_body_truncated: str | None,
) -> dict[str, Any]:
    """Validate the envelope shape and return ``data`` on success.

    Raises an :class:`IFlowError` subclass when ``success`` is False (regardless
    of HTTP status — the body is authoritative; this matches the JS SDK's
    behavior).
    """
    if not isinstance(envelope, dict):
        raise IFlowAPIError(
            "iFlow returned a non-object response body",
            code="api_invalid_json",
            status_code=None,
            request=request_info,
            response_body_truncated=raw_body_truncated,
        )

    success = envelope.get("success")
    code = _coerce_str(envelope.get("code"))
    message = _coerce_str(envelope.get("message"))

    if success is False or (success is None and code not in ("", "200")):
        raise_for_business_code(
            code=code or "unknown",
            message=message,
            request_info=request_info,
            raw_body_truncated=raw_body_truncated,
        )
        raise IFlowError(  # pragma: no cover — raise_for_business_code never returns
            "unreachable",
            code="internal_error",
        )

    data = envelope.get("data")
    if data is None:
        # iFlow occasionally returns success with no data — give the model
        # layer something to chew on rather than crashing here.
        data = {}
    return {"data": data, "raw": envelope}


def build_web_search_response(
    *,
    data: Any,
    raw: dict[str, Any],
    took_ms: int,
    query_echo: str,
) -> WebSearchResponse:
    if not isinstance(data, dict):
        data = {}
    organic = data.get("organic")
    results: list[WebSearchResult] = []
    if isinstance(organic, list):
        for item in organic:
            if not isinstance(item, dict):
                continue
            results.append(
                WebSearchResult(
                    title=_coerce_str(item.get("title")),
                    url=_coerce_str(item.get("link") or item.get("url")),
                    snippet=_coerce_str(item.get("snippet")),
                    position=_coerce_int(item.get("position")),
                    date=item.get("date") if isinstance(item.get("date"), str) else None,
                )
            )
    return WebSearchResponse(
        query=_coerce_str(data.get("query")) or query_echo,
        results=results,
        took_ms=took_ms,
        raw=raw,
    )


def build_image_search_response(
    *,
    data: Any,
    raw: dict[str, Any],
    took_ms: int,
    query_echo: str,
) -> ImageSearchResponse:
    # ``data`` may be either a bare list (documented inconsistency) or an
    # object containing a list under various keys. Handle both shapes.
    items: list[Any] = []
    if isinstance(data, list):
        items = data
    elif isinstance(data, dict):
        for key in ("images", "results", "items", "organic"):
            candidate = data.get(key)
            if isinstance(candidate, list):
                items = candidate
                break

    images: list[ImageResult] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        images.append(
            ImageResult(
                image_url=_coerce_str(item.get("url") or item.get("imageUrl") or item.get("image_url")),
                source_url=_coerce_str(item.get("refUrl") or item.get("sourceUrl") or item.get("source_url")),
                title=_coerce_str(item.get("title")),
                width=_coerce_int(item.get("width")),
                height=_coerce_int(item.get("height")),
                position=_coerce_int(item.get("position")),
            )
        )

    return ImageSearchResponse(
        query=query_echo,
        images=images,
        took_ms=took_ms,
        raw=raw,
    )


def build_web_fetch_response(
    *,
    data: Any,
    raw: dict[str, Any],
    took_ms: int,
    url_echo: str,
) -> WebFetchResponse:
    if not isinstance(data, dict):
        data = {}
    return WebFetchResponse(
        url=_coerce_str(data.get("url")) or url_echo,
        title=_coerce_str(data.get("title")),
        content=_coerce_str(data.get("content")),
        from_cache=_coerce_bool(data.get("fromCache") or data.get("from_cache")),
        took_ms=took_ms,
        raw=raw,
    )


__all__ = [
    "truncate_body",
    "raise_for_http_status",
    "raise_for_business_code",
    "parse_envelope",
    "build_web_search_response",
    "build_image_search_response",
    "build_web_fetch_response",
]
