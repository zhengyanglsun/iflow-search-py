"""Private ``BaseTool`` subclasses, one per iFlow Search endpoint.

These classes are not part of the public API — their identity may change
without a major bump. Use the factories in :mod:`iflow_search_langchain._factories`
instead.

Per design §10.1 and §15.5, every tool implements both ``_run`` and ``_arun``
explicitly; cross-delegation between sync and async is forbidden by the core
SDK's invariants. ``_run`` calls ``IFlowSearchClient``; ``_arun`` calls
``AsyncIFlowSearchClient``.

Per design §12.4, there is no ``try / except`` around the client calls — every
``IFlowError`` and ``asyncio.CancelledError`` propagates unchanged.
"""

from __future__ import annotations

from typing import Any, Literal

from iflow_search import AsyncIFlowSearchClient, IFlowSearchClient
from langchain_core.callbacks import (
    AsyncCallbackManagerForToolRun,
    CallbackManagerForToolRun,
)
from langchain_core.tools import BaseTool
from pydantic import PrivateAttr

from . import _format
from ._schemas import ImageSearchArgs, WebFetchArgs, WebSearchArgs

_DESC_WEB_SEARCH = (
    "Search the public web for pages matching a query. Returns a ranked list "
    "of titles, URLs, snippets, and (when available) publication dates. Use "
    "for current events, references, product comparisons, or whenever you "
    "need URLs to ground an answer."
)
_DESC_IMAGE_SEARCH = (
    "Search the public web for images matching a query. Returns image URLs "
    "and the page each image came from. Use when the user asks for pictures, "
    "diagrams, logos, or visual examples."
)
_DESC_WEB_FETCH = (
    "Fetch and extract the main readable content of a single web page by URL. "
    "Use when the user provides a URL or after `iflow_web_search` when you "
    "need the full text of a specific result."
)


class _WebSearchTool(BaseTool):
    name: str = "iflow_web_search"
    description: str = _DESC_WEB_SEARCH
    args_schema: type = WebSearchArgs
    response_format: Literal["content_and_artifact"] = "content_and_artifact"

    _sync_client: IFlowSearchClient = PrivateAttr()
    _async_client: AsyncIFlowSearchClient = PrivateAttr()

    def __init__(
        self,
        *,
        sync_client: IFlowSearchClient,
        async_client: AsyncIFlowSearchClient,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self._sync_client = sync_client
        self._async_client = async_client

    def _run(
        self,
        query: str,
        count: int | None = None,
        run_manager: CallbackManagerForToolRun | None = None,
    ) -> tuple[str, dict[str, Any]]:
        response = self._sync_client.web_search(query=query, count=count)
        return _format.format_web_search(response), response.model_dump(mode="json")

    async def _arun(
        self,
        query: str,
        count: int | None = None,
        run_manager: AsyncCallbackManagerForToolRun | None = None,
    ) -> tuple[str, dict[str, Any]]:
        response = await self._async_client.web_search(query=query, count=count)
        return _format.format_web_search(response), response.model_dump(mode="json")


class _ImageSearchTool(BaseTool):
    name: str = "iflow_image_search"
    description: str = _DESC_IMAGE_SEARCH
    args_schema: type = ImageSearchArgs
    response_format: Literal["content_and_artifact"] = "content_and_artifact"

    _sync_client: IFlowSearchClient = PrivateAttr()
    _async_client: AsyncIFlowSearchClient = PrivateAttr()

    def __init__(
        self,
        *,
        sync_client: IFlowSearchClient,
        async_client: AsyncIFlowSearchClient,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self._sync_client = sync_client
        self._async_client = async_client

    def _run(
        self,
        query: str,
        count: int | None = None,
        run_manager: CallbackManagerForToolRun | None = None,
    ) -> tuple[str, dict[str, Any]]:
        response = self._sync_client.image_search(query=query, count=count)
        return _format.format_image_search(response), response.model_dump(mode="json")

    async def _arun(
        self,
        query: str,
        count: int | None = None,
        run_manager: AsyncCallbackManagerForToolRun | None = None,
    ) -> tuple[str, dict[str, Any]]:
        response = await self._async_client.image_search(query=query, count=count)
        return _format.format_image_search(response), response.model_dump(mode="json")


class _WebFetchTool(BaseTool):
    name: str = "iflow_web_fetch"
    description: str = _DESC_WEB_FETCH
    args_schema: type = WebFetchArgs
    response_format: Literal["content_and_artifact"] = "content_and_artifact"

    _sync_client: IFlowSearchClient = PrivateAttr()
    _async_client: AsyncIFlowSearchClient = PrivateAttr()

    def __init__(
        self,
        *,
        sync_client: IFlowSearchClient,
        async_client: AsyncIFlowSearchClient,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self._sync_client = sync_client
        self._async_client = async_client

    def _run(
        self,
        url: str,
        run_manager: CallbackManagerForToolRun | None = None,
    ) -> tuple[str, dict[str, Any]]:
        response = self._sync_client.web_fetch(url=url)
        return _format.format_web_fetch(response), response.model_dump(mode="json")

    async def _arun(
        self,
        url: str,
        run_manager: AsyncCallbackManagerForToolRun | None = None,
    ) -> tuple[str, dict[str, Any]]:
        response = await self._async_client.web_fetch(url=url)
        return _format.format_web_fetch(response), response.model_dump(mode="json")


__all__ = ["_WebSearchTool", "_ImageSearchTool", "_WebFetchTool"]
