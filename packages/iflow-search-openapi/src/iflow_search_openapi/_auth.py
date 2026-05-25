"""Bearer-token authentication for the OpenAPI adapter (design §7).

Two modes:

- **Open** — ``IFLOW_OPENAPI_AUTH_TOKEN`` unset → ``make_auth_dependency``
  returns a no-op that always allows the request.
- **Closed** — token configured → every route except ``/health`` must present
  ``Authorization: Bearer <token>``. Compare is constant-time via
  :func:`hmac.compare_digest`. Length mismatches still trigger a compare
  against a same-length zero buffer so timing cannot leak the expected length
  (design §7.3, matching the JS sibling's ``safeEqual``).

The configured token never appears in any error message — only the literal
strings below. The header value is never logged or echoed.

OPTIONS preflight requests are handled by the CORS middleware *before* this
dependency runs (design §9.5), so browser tool-importers can complete preflight
without a bearer.
"""

from __future__ import annotations

import hmac
import re
from collections.abc import Awaitable, Callable

from fastapi import HTTPException, Request

from ._errors import adapter_error_envelope

# Matches the JS sibling's parser: case-insensitive "Bearer", at least one
# whitespace, then the token. We tolerate extra surrounding whitespace.
_BEARER_RE = re.compile(r"^Bearer\s+(.+)$", re.IGNORECASE)

# Detail body for the uniform 401 response. Re-built per call so the closure
# can't accidentally hold a reference to the configured token.
_UNAUTHORIZED_MISSING = 'Missing Authorization header. Send "Authorization: Bearer <token>".'
_UNAUTHORIZED_MALFORMED = 'Malformed Authorization header. Expected "Bearer <token>".'
_UNAUTHORIZED_EMPTY = "Empty bearer token."
_UNAUTHORIZED_WRONG = "Invalid bearer token."


def _constant_time_equal(provided: str, expected: str) -> bool:
    """Constant-time string compare with a same-length zero-buffer fallback.

    ``hmac.compare_digest`` is constant-time only when the two buffers are the
    same length; mismatched lengths return immediately. To prevent leaking the
    expected length via timing, we always perform a compare — falling back to
    a zero buffer of the *provided* length when lengths differ.
    """
    p = provided.encode("utf-8")
    e = expected.encode("utf-8")
    if len(p) == len(e):
        return hmac.compare_digest(p, e)
    # Same-length zero buffer keeps the work proportional to provided length.
    decoy = b"\x00" * len(p)
    hmac.compare_digest(p, decoy)
    return False


def _raise_unauthorized(message: str) -> None:
    raise HTTPException(
        status_code=401,
        detail=adapter_error_envelope(code="unauthorized", message=message)["error"],
    )


def make_auth_dependency(
    expected_token: str | None,
) -> Callable[[Request], Awaitable[None]]:
    """Return a FastAPI dependency that enforces bearer auth when configured.

    When ``expected_token`` is ``None`` the dependency is a no-op (open mode).
    Otherwise it raises ``HTTPException(401)`` with a uniform envelope on any
    missing / malformed / empty / wrong header.
    """

    if expected_token is None:

        async def _allow(_request: Request) -> None:
            return None

        return _allow

    async def _require_bearer(request: Request) -> None:
        header = request.headers.get("authorization")
        if header is None:
            _raise_unauthorized(_UNAUTHORIZED_MISSING)
            return  # pragma: no cover — _raise_unauthorized always raises
        match = _BEARER_RE.match(header.strip())
        if match is None:
            _raise_unauthorized(_UNAUTHORIZED_MALFORMED)
            return  # pragma: no cover
        provided = match.group(1).strip()
        if not provided:
            _raise_unauthorized(_UNAUTHORIZED_EMPTY)
            return  # pragma: no cover
        if not _constant_time_equal(provided, expected_token):
            _raise_unauthorized(_UNAUTHORIZED_WRONG)

    return _require_bearer


__all__ = ["make_auth_dependency"]
