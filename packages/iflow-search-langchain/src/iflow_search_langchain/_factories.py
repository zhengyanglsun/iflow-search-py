"""Public factory functions — the only client-construction entry points users
should call.

Per design §10, each factory accepts ``api_key``, ``base_url``, ``timeout``,
``client``, and ``async_client`` (all kw-only). Auto-built clients carry the
adapter's attribution (``source="langchain"``, ``integration_name=
"iflow-search-langchain"``, ``integration_version=__version__``).
Caller-supplied clients are taken verbatim — the factory never mutates them
(design §11.2, §15.7).

``IFlowConfigError`` surfaces at factory-call time, not at first tool invocation
(design §12.3), so agent-setup failures fail fast before any LLM round-trip.
"""

from __future__ import annotations

from iflow_search import AsyncIFlowSearchClient, IFlowSearchClient
from langchain_core.tools import BaseTool

from . import _constants
from ._tools import _ImageSearchTool, _WebFetchTool, _WebSearchTool
from ._version import __version__


def _build_sync_client(
    *,
    api_key: str | None,
    base_url: str | None,
    timeout: float | None,
) -> IFlowSearchClient:
    return IFlowSearchClient(
        api_key=api_key,
        base_url=base_url,
        timeout=timeout,
        source=_constants.SOURCE,
        integration_name=_constants.INTEGRATION_NAME,
        integration_version=__version__,
    )


def _build_async_client(
    *,
    api_key: str | None,
    base_url: str | None,
    timeout: float | None,
) -> AsyncIFlowSearchClient:
    return AsyncIFlowSearchClient(
        api_key=api_key,
        base_url=base_url,
        timeout=timeout,
        source=_constants.SOURCE,
        integration_name=_constants.INTEGRATION_NAME,
        integration_version=__version__,
    )


def _resolve_clients(
    *,
    api_key: str | None,
    base_url: str | None,
    timeout: float | None,
    client: IFlowSearchClient | None,
    async_client: AsyncIFlowSearchClient | None,
) -> tuple[IFlowSearchClient, AsyncIFlowSearchClient]:
    resolved_sync = (
        client
        if client is not None
        else _build_sync_client(api_key=api_key, base_url=base_url, timeout=timeout)
    )
    resolved_async = (
        async_client
        if async_client is not None
        else _build_async_client(api_key=api_key, base_url=base_url, timeout=timeout)
    )
    return resolved_sync, resolved_async


def create_iflow_web_search_tool(
    *,
    api_key: str | None = None,
    base_url: str | None = None,
    timeout: float | None = None,
    client: IFlowSearchClient | None = None,
    async_client: AsyncIFlowSearchClient | None = None,
) -> BaseTool:
    sync_c, async_c = _resolve_clients(
        api_key=api_key,
        base_url=base_url,
        timeout=timeout,
        client=client,
        async_client=async_client,
    )
    return _WebSearchTool(sync_client=sync_c, async_client=async_c)


def create_iflow_image_search_tool(
    *,
    api_key: str | None = None,
    base_url: str | None = None,
    timeout: float | None = None,
    client: IFlowSearchClient | None = None,
    async_client: AsyncIFlowSearchClient | None = None,
) -> BaseTool:
    sync_c, async_c = _resolve_clients(
        api_key=api_key,
        base_url=base_url,
        timeout=timeout,
        client=client,
        async_client=async_client,
    )
    return _ImageSearchTool(sync_client=sync_c, async_client=async_c)


def create_iflow_web_fetch_tool(
    *,
    api_key: str | None = None,
    base_url: str | None = None,
    timeout: float | None = None,
    client: IFlowSearchClient | None = None,
    async_client: AsyncIFlowSearchClient | None = None,
) -> BaseTool:
    sync_c, async_c = _resolve_clients(
        api_key=api_key,
        base_url=base_url,
        timeout=timeout,
        client=client,
        async_client=async_client,
    )
    return _WebFetchTool(sync_client=sync_c, async_client=async_c)


def create_iflow_search_tools(
    *,
    api_key: str | None = None,
    base_url: str | None = None,
    timeout: float | None = None,
    client: IFlowSearchClient | None = None,
    async_client: AsyncIFlowSearchClient | None = None,
) -> list[BaseTool]:
    """Return ``[web_search, image_search, web_fetch]`` — three tools sharing a
    single sync + async client pair.

    The returned list is in fixed order (asserted by tests; downstream code
    may rely on it). Per design §10.3 / §15.6, sharing the client pair across
    all three tools means one sync connection pool and one async connection
    pool, not three of each.
    """
    sync_c, async_c = _resolve_clients(
        api_key=api_key,
        base_url=base_url,
        timeout=timeout,
        client=client,
        async_client=async_client,
    )
    return [
        _WebSearchTool(sync_client=sync_c, async_client=async_c),
        _ImageSearchTool(sync_client=sync_c, async_client=async_c),
        _WebFetchTool(sync_client=sync_c, async_client=async_c),
    ]


__all__ = [
    "create_iflow_web_search_tool",
    "create_iflow_image_search_tool",
    "create_iflow_web_fetch_tool",
    "create_iflow_search_tools",
]
