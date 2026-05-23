"""Error-to-tool-result mapping (design §9).

Every ``IFlowError`` raised by the core is rendered as an MCP
``isError: true`` result whose ``structuredContent.error.code`` matches the
core's stable string. Class identity is not part of the contract.

The unexpected-exception path produces ``code="internal_error"`` so MCP
clients can distinguish "core SDK raised something we know about" from "the
adapter itself crashed".
"""

from __future__ import annotations

import asyncio

import pytest
from iflow_search.errors import (
    IFlowAPIError,
    IFlowAuthError,
    IFlowBusinessError,
    IFlowConfigError,
    IFlowInsufficientCreditsError,
    IFlowNetworkError,
    IFlowRateLimitError,
    IFlowTimeoutError,
    IFlowValidationError,
)

from iflow_search_mcp._errors import (
    iflow_error_to_tool_result,
    unexpected_error_to_tool_result,
)


def test_iflow_error_basic_shape() -> None:
    err = IFlowAuthError("HTTP 401 from /api/search/webSearch", code="api_unauthorized")

    result = iflow_error_to_tool_result(err, tool_name="iflow_web_search")

    assert result["isError"] is True
    assert result["content"] == [
        {
            "type": "text",
            "text": "iflow_web_search failed: [api_unauthorized] HTTP 401 from /api/search/webSearch",
        }
    ]
    assert result["structuredContent"] == {
        "tool": "iflow_web_search",
        "error": {
            "code": "api_unauthorized",
            "message": "HTTP 401 from /api/search/webSearch",
        },
    }


def test_iflow_api_error_carries_status_code() -> None:
    err = IFlowAPIError(
        "HTTP 500", code="api_server_error", status_code=500, response_body_truncated="oops"
    )

    result = iflow_error_to_tool_result(err, tool_name="iflow_web_fetch")

    assert result["structuredContent"]["error"]["status_code"] == 500
    assert result["structuredContent"]["error"]["response_body_truncated"] == "oops"


def test_iflow_business_error_carries_business_code() -> None:
    err = IFlowBusinessError(
        "fetch failed",
        code="business_fetch_failed",
        business_code="90001",
    )

    result = iflow_error_to_tool_result(err, tool_name="iflow_web_fetch")

    assert result["structuredContent"]["error"]["business_code"] == "90001"
    assert result["structuredContent"]["error"]["code"] == "business_fetch_failed"


def test_optional_fields_absent_when_not_set() -> None:
    err = IFlowRateLimitError("slow down", code="business_rate_limited")

    result = iflow_error_to_tool_result(err, tool_name="iflow_web_search")
    err_payload = result["structuredContent"]["error"]

    assert "status_code" not in err_payload
    assert "business_code" not in err_payload
    assert "response_body_truncated" not in err_payload


@pytest.mark.parametrize(
    ("err", "expected_code"),
    [
        (IFlowConfigError("missing key", code="missing_api_key"), "missing_api_key"),
        (IFlowValidationError("bad q", code="business_bad_request"), "business_bad_request"),
        (IFlowAuthError("401", code="api_unauthorized"), "api_unauthorized"),
        (IFlowRateLimitError("429", code="api_rate_limited"), "api_rate_limited"),
        (
            IFlowInsufficientCreditsError("topup", code="business_insufficient_credits"),
            "business_insufficient_credits",
        ),
        (IFlowTimeoutError("slow", code="network_timeout"), "network_timeout"),
        (IFlowNetworkError("dns", code="network_error"), "network_error"),
    ],
)
def test_every_subclass_dispatches_on_code(err: object, expected_code: str) -> None:
    result = iflow_error_to_tool_result(err, tool_name="iflow_web_search")  # type: ignore[arg-type]
    assert result["structuredContent"]["error"]["code"] == expected_code
    assert result["isError"] is True


def test_unexpected_exception_becomes_internal_error() -> None:
    err = ValueError("oops")

    result = unexpected_error_to_tool_result(err, tool_name="iflow_web_search")

    assert result["isError"] is True
    assert result["structuredContent"]["error"]["code"] == "internal_error"
    assert "iflow_web_search" in result["content"][0]["text"]


def test_cancellation_must_not_be_wrapped() -> None:
    # Defensive: the adapter must never catch CancelledError. We document that
    # by checking the mapper raises if asked to wrap it.
    with pytest.raises(asyncio.CancelledError):
        unexpected_error_to_tool_result(
            asyncio.CancelledError(), tool_name="iflow_web_search"
        )


def test_internal_error_message_does_not_leak_repr() -> None:
    err = RuntimeError("api_key=sk-secret-leak")

    result = unexpected_error_to_tool_result(err, tool_name="iflow_web_search")

    # We never echo the exception's str() into structured/text output —
    # internal_error is opaque on purpose.
    assert "sk-secret-leak" not in result["content"][0]["text"]
    assert "sk-secret-leak" not in str(result["structuredContent"])
