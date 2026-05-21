"""Tests for HTTP status and business code → exception mapping."""

from __future__ import annotations

import pytest

from iflow_search._normalize import (
    parse_envelope,
    raise_for_business_code,
    raise_for_http_status,
)
from iflow_search.errors import (
    IFlowAPIError,
    IFlowAuthError,
    IFlowBusinessError,
    IFlowInsufficientCreditsError,
    IFlowRateLimitError,
    IFlowValidationError,
)

REQ = {"method": "POST", "url": "https://example/api/x", "endpoint": "x"}


@pytest.mark.parametrize(
    ("status", "expected_cls", "expected_code"),
    [
        (400, IFlowValidationError, "api_bad_request"),
        (401, IFlowAuthError, "api_unauthorized"),
        (403, IFlowAuthError, "api_forbidden"),
        (429, IFlowRateLimitError, "api_rate_limited"),
        (500, IFlowAPIError, "api_server_error"),
        (502, IFlowAPIError, "api_server_error"),
        (599, IFlowAPIError, "api_server_error"),
        (418, IFlowAPIError, "api_http_error"),
    ],
)
def test_http_status_to_exception(
    status: int,
    expected_cls: type[Exception],
    expected_code: str,
) -> None:
    with pytest.raises(expected_cls) as exc:
        raise_for_http_status(status_code=status, body=b"err", request_info=REQ)
    assert exc.value.code == expected_code  # type: ignore[attr-defined]


def test_http_2xx_does_not_raise() -> None:
    raise_for_http_status(status_code=200, body=b"{}", request_info=REQ)
    raise_for_http_status(status_code=204, body=None, request_info=REQ)


def test_http_5xx_carries_status_code() -> None:
    with pytest.raises(IFlowAPIError) as exc:
        raise_for_http_status(status_code=503, body=b"down", request_info=REQ)
    assert exc.value.status_code == 503
    assert exc.value.response_body_truncated == "down"


def test_http_body_truncated_to_500() -> None:
    big = b"x" * 5000
    with pytest.raises(IFlowAPIError) as exc:
        raise_for_http_status(status_code=500, body=big, request_info=REQ)
    assert exc.value.response_body_truncated is not None
    assert len(exc.value.response_body_truncated) == 500


@pytest.mark.parametrize(
    ("code", "expected_cls", "expected_code"),
    [
        ("400", IFlowValidationError, "business_bad_request"),
        ("40303", IFlowRateLimitError, "business_rate_limited"),
        ("60400", IFlowInsufficientCreditsError, "business_insufficient_credits"),
        ("90001", IFlowBusinessError, "business_fetch_failed"),
        ("90002", IFlowBusinessError, "business_no_results"),
        ("90402", IFlowAuthError, "business_invalid_api_key"),
        ("500", IFlowAPIError, "business_server_error"),
        ("99999", IFlowBusinessError, "business_unknown"),
    ],
)
def test_business_code_to_exception(
    code: str,
    expected_cls: type[Exception],
    expected_code: str,
) -> None:
    with pytest.raises(expected_cls) as exc:
        raise_for_business_code(
            code=code, message="m", request_info=REQ, raw_body_truncated=None
        )
    assert exc.value.code == expected_code  # type: ignore[attr-defined]


def test_business_error_preserves_business_code() -> None:
    with pytest.raises(IFlowBusinessError) as exc:
        raise_for_business_code(
            code="90001",
            message="parse fail",
            request_info=REQ,
            raw_body_truncated=None,
        )
    assert exc.value.business_code == "90001"
    assert exc.value.business_message == "parse fail"


def test_parse_envelope_trusts_body_over_http_status() -> None:
    envelope = {
        "success": False,
        "code": "40303",
        "message": "throttled",
        "data": None,
    }
    with pytest.raises(IFlowRateLimitError):
        parse_envelope(envelope=envelope, request_info=REQ, raw_body_truncated=None)


def test_parse_envelope_returns_data_on_success() -> None:
    envelope = {
        "success": True,
        "code": "200",
        "message": "ok",
        "data": {"hello": "world"},
    }
    out = parse_envelope(envelope=envelope, request_info=REQ, raw_body_truncated=None)
    assert out["data"] == {"hello": "world"}
    assert out["raw"] is envelope


def test_parse_envelope_rejects_non_dict_body() -> None:
    with pytest.raises(IFlowAPIError) as exc:
        parse_envelope(envelope="garbage", request_info=REQ, raw_body_truncated=None)  # type: ignore[arg-type]
    assert exc.value.code == "api_invalid_json"
