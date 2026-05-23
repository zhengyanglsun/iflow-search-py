"""``asyncio.CancelledError`` propagates as itself through ``_arun`` (design §12.2)."""

from __future__ import annotations

import asyncio
from collections.abc import Callable

import httpx
import pytest
from iflow_search import AsyncIFlowSearchClient, IFlowSearchClient

from iflow_search_langchain._factories import create_iflow_web_search_tool


@pytest.mark.asyncio
async def test_cancelled_error_propagates_unwrapped(
    make_mock_transport: Callable,
) -> None:
    """Cancel the in-flight task; the raised exception must be exactly
    ``asyncio.CancelledError``, not anything wrapped or replaced."""
    started = asyncio.Event()

    async def blocking(_req: httpx.Request) -> httpx.Response:
        started.set()
        await asyncio.sleep(60)
        return httpx.Response(200, json={})  # pragma: no cover

    transport, _ = make_mock_transport(blocking)
    ac = AsyncIFlowSearchClient(
        api_key="test-key",
        http_client=httpx.AsyncClient(transport=transport),
    )
    sync = IFlowSearchClient(api_key="test-key")
    tool = create_iflow_web_search_tool(client=sync, async_client=ac)

    task = asyncio.create_task(tool._arun(query="x"))  # type: ignore[attr-defined]
    try:
        await started.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    finally:
        await ac.aclose()
