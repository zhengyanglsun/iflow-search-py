"""Exception hierarchy for the iFlow Search SDK.

Every SDK-raised exception inherits from :class:`IFlowError`. Caller-initiated
``asyncio.CancelledError`` and ``KeyboardInterrupt`` propagate as themselves and
are never wrapped.

The ``code`` attribute is a stable string identifier (e.g.
``"api_unauthorized"``, ``"business_rate_limited"``). Downstream code should
switch on ``code`` rather than relying on exception class identity alone — this
matches the JS SDK's stable-string contract.
"""

from __future__ import annotations

from typing import Any


class IFlowError(Exception):
    """Base class for every exception raised by the iFlow Search SDK."""

    def __init__(
        self,
        message: str,
        *,
        code: str,
        request: dict[str, Any] | None = None,
        response_body_truncated: str | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.request = request
        self.response_body_truncated = response_body_truncated

    def __repr__(self) -> str:
        return (
            f"{type(self).__name__}(code={self.code!r}, message={self.message!r})"
        )


class IFlowConfigError(IFlowError):
    """Missing API key, invalid attribution, or invalid env var."""


class IFlowValidationError(IFlowError):
    """Client-side parameter validation failed before the request was sent."""


class IFlowAuthError(IFlowError):
    """HTTP 401/403, or business code ``90402`` (invalid API key)."""


class IFlowRateLimitError(IFlowError):
    """HTTP 429, or business code ``40303`` (1000 RPM cap exceeded)."""


class IFlowInsufficientCreditsError(IFlowError):
    """Business code ``60400`` — account is out of credits."""


class IFlowAPIError(IFlowError):
    """HTTP 5xx, non-JSON 2xx, or unexpected non-2xx response.

    Carries the HTTP ``status_code`` and (truncated) raw response body so
    callers can introspect upstream incidents.
    """

    def __init__(
        self,
        message: str,
        *,
        code: str,
        status_code: int | None = None,
        request: dict[str, Any] | None = None,
        response_body_truncated: str | None = None,
        response_id: str | None = None,
    ) -> None:
        super().__init__(
            message,
            code=code,
            request=request,
            response_body_truncated=response_body_truncated,
        )
        self.status_code = status_code
        self.response_id = response_id


class IFlowBusinessError(IFlowError):
    """``success: false`` with a code not otherwise mapped.

    Also raised for the known but non-fatal codes ``90001`` (web_fetch parse
    failure) and ``90002`` (search returned no results).
    """

    def __init__(
        self,
        message: str,
        *,
        code: str,
        business_code: str,
        business_message: str | None = None,
        request: dict[str, Any] | None = None,
        response_body_truncated: str | None = None,
    ) -> None:
        super().__init__(
            message,
            code=code,
            request=request,
            response_body_truncated=response_body_truncated,
        )
        self.business_code = business_code
        self.business_message = business_message


class IFlowTimeoutError(IFlowError):
    """SDK-initiated timeout. Wraps :class:`httpx.TimeoutException`.

    Caller-initiated ``asyncio.CancelledError`` is **not** wrapped — it
    propagates as itself so cooperative cancellation keeps working.
    """


class IFlowNetworkError(IFlowError):
    """DNS, connection refused, TLS handshake failure, etc. — anything below
    the HTTP layer that prevented a response from being received.
    """


__all__ = [
    "IFlowError",
    "IFlowConfigError",
    "IFlowValidationError",
    "IFlowAuthError",
    "IFlowRateLimitError",
    "IFlowInsufficientCreditsError",
    "IFlowAPIError",
    "IFlowBusinessError",
    "IFlowTimeoutError",
    "IFlowNetworkError",
]
