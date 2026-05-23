"""Error → tool-result mapping (design §9).

Two entry points:

* :func:`iflow_error_to_tool_result` renders an :class:`IFlowError` (raised
  by the core SDK) into an MCP ``isError: true`` tool result. Dispatch is
  on ``err.code`` only — class identity is deliberately not part of the
  contract (design §9.4).
* :func:`unexpected_error_to_tool_result` is the catch-all for bugs in the
  adapter itself; it always emits ``code="internal_error"`` so MCP clients
  can distinguish "core SDK error we understand" from "adapter crashed".

Cancellation never enters either path: ``asyncio.CancelledError`` is
re-raised immediately so cooperative shutdown keeps working (design §9.3).
"""

from __future__ import annotations

import asyncio
from typing import Any

from iflow_search.errors import IFlowAPIError, IFlowBusinessError, IFlowError


def iflow_error_to_tool_result(err: IFlowError, *, tool_name: str) -> dict[str, Any]:
    error_payload: dict[str, Any] = {
        "code": err.code,
        "message": err.message,
    }

    if isinstance(err, IFlowAPIError) and err.status_code is not None:
        error_payload["status_code"] = err.status_code
    if isinstance(err, IFlowBusinessError):
        error_payload["business_code"] = err.business_code
    if err.response_body_truncated is not None:
        error_payload["response_body_truncated"] = err.response_body_truncated

    text = f"{tool_name} failed: [{err.code}] {err.message}"
    return {
        "content": [{"type": "text", "text": text}],
        "structuredContent": {"tool": tool_name, "error": error_payload},
        "isError": True,
    }


def unexpected_error_to_tool_result(
    err: BaseException, *, tool_name: str
) -> dict[str, Any]:
    # Cancellation always propagates; never swallowed, never mapped.
    if isinstance(err, asyncio.CancelledError):
        raise err

    text = f"{tool_name} failed: [internal_error] an unexpected error occurred"
    return {
        "content": [{"type": "text", "text": text}],
        "structuredContent": {
            "tool": tool_name,
            "error": {
                "code": "internal_error",
                "message": "an unexpected error occurred",
            },
        },
        "isError": True,
    }


__all__ = ["iflow_error_to_tool_result", "unexpected_error_to_tool_result"]
