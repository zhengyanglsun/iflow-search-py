"""Error pass-through: every IFlowError subclass propagates through the tool
boundary with its ``code`` intact (design §12.1)."""

from __future__ import annotations

from collections.abc import Callable

import httpx
import pytest
from iflow_search import (
    AsyncIFlowSearchClient,
    IFlowAPIError,
    IFlowAuthError,
    IFlowError,
    IFlowInsufficientCreditsError,
    IFlowNetworkError,
    IFlowRateLimitError,
    IFlowSearchClient,
)

from iflow_search_langchain._factories import create_iflow_web_search_tool


def _make_sync(transport: httpx.MockTransport) -> IFlowSearchClient:
    return IFlowSearchClient(
        api_key="test-key",
        http_client=httpx.Client(transport=transport),
    )


def _tool(transport: httpx.MockTransport) -> object:
    return create_iflow_web_search_tool(
        client=_make_sync(transport),
        async_client=AsyncIFlowSearchClient(api_key="test-key"),
    )


@pytest.mark.parametrize(
    ("status", "expected_cls"),
    [
        (401, IFlowAuthError),
        (403, IFlowAuthError),
        (429, IFlowRateLimitError),
        (500, IFlowAPIError),
        (502, IFlowAPIError),
        (503, IFlowAPIError),
    ],
)
def test_http_status_propagates_as_expected_iflow_error(
    make_mock_transport: Callable, status: int, expected_cls: type
) -> None:
    transport, _ = make_mock_transport(lambda req: httpx.Response(status, text="server-side-text"))
    tool = _tool(transport)
    with pytest.raises(expected_cls) as exc:
        tool._run(query="x")  # type: ignore[attr-defined]
    assert isinstance(exc.value, IFlowError)
    assert exc.value.code


@pytest.mark.parametrize(
    ("business_code", "expected_cls"),
    [
        ("40303", IFlowRateLimitError),
        ("60400", IFlowInsufficientCreditsError),
        ("90402", IFlowAuthError),
    ],
)
def test_business_code_propagates(
    make_mock_transport: Callable,
    fake_envelope: Callable,
    business_code: str,
    expected_cls: type,
) -> None:
    """HTTP 200 with success=false; business code wins per core invariant."""
    transport, _ = make_mock_transport(
        lambda req: httpx.Response(
            200,
            json=fake_envelope(success=False, code=business_code, message="nope"),
        )
    )
    tool = _tool(transport)
    with pytest.raises(expected_cls):
        tool._run(query="x")  # type: ignore[attr-defined]


def test_network_error_propagates(make_mock_transport: Callable) -> None:
    def boom(_req: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("simulated DNS / connection failure")

    transport, _ = make_mock_transport(boom)
    tool = _tool(transport)
    with pytest.raises(IFlowNetworkError):
        tool._run(query="x")  # type: ignore[attr-defined]
