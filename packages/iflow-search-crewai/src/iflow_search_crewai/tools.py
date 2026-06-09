"""CrewAI BaseTool implementations for iFlow Search."""

from __future__ import annotations

from typing import Any

from crewai.tools import BaseTool, EnvVar
from iflow_search import IFlowError, IFlowSearchClient
from pydantic import BaseModel, Field, PrivateAttr

from ._config import ToolConfig, resolve_tool_config
from ._constants import _MISSING_API_KEY_MESSAGE, INTEGRATION_NAME, SOURCE
from ._errors import format_iflow_error
from ._schemas import ImageSearchInput, WebFetchInput, WebSearchInput
from ._serialize import (
    serialize_image_search,
    serialize_web_fetch,
    serialize_web_search,
    to_json_string,
)
from ._version import __version__

_DESC_WEB_SEARCH = (
    "Search the public web for pages matching a query. Returns titles, URLs, "
    "snippets, and publication dates when available. Use for current events, "
    "references, or whenever you need grounded URLs."
)
_DESC_IMAGE_SEARCH = (
    "Search the public web for images matching a query. Returns image URLs and "
    "source pages. Use when the user asks for pictures, diagrams, or visual examples."
)
_DESC_WEB_FETCH = (
    "Fetch and extract the main readable content of a single web page by URL. "
    "Use when the user provides a URL or when you need full text from a search result."
)

_ENV_VARS: list[EnvVar] = [
    EnvVar(
        name="IFLOW_API_KEY",
        description="API key for iFlow Search (心流搜索).",
        required=True,
    ),
    EnvVar(
        name="IFLOW_BASE_URL",
        description="Optional override for the iFlow platform base URL.",
        required=False,
    ),
    EnvVar(
        name="IFLOW_TIMEOUT_MS",
        description="Optional request timeout in milliseconds.",
        required=False,
    ),
]


class _IFlowSearchToolBase(BaseTool):
    """Shared configuration and client lifecycle for iFlow Search tools."""

    api_key: str | None = Field(
        default=None,
        description="iFlow API key. Overrides IFLOW_API_KEY when set.",
    )
    base_url: str | None = Field(
        default=None,
        description="Optional iFlow platform base URL override.",
    )
    timeout: float | None = Field(
        default=None,
        description="Optional request timeout in seconds.",
    )
    env_vars: list[EnvVar] = Field(default_factory=lambda: list(_ENV_VARS))

    _config: ToolConfig = PrivateAttr()
    _client: IFlowSearchClient | None = PrivateAttr(default=None)
    _injected_client: IFlowSearchClient | None = PrivateAttr(default=None)

    def __init__(
        self,
        client: IFlowSearchClient | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self._injected_client = client
        self._config = resolve_tool_config(
            api_key=self.api_key,
            base_url=self.base_url,
            timeout=self.timeout,
        )

    def _require_api_key(self) -> str:
        key = self._config.api_key
        if not key:
            raise ValueError(_MISSING_API_KEY_MESSAGE)
        return key

    def _get_client(self) -> IFlowSearchClient:
        if self._injected_client is not None:
            return self._injected_client
        if self._client is None:
            self._client = IFlowSearchClient(
                api_key=self._require_api_key(),
                base_url=self._config.base_url,
                timeout=self._config.timeout_s,
                source=SOURCE,
                integration_name=INTEGRATION_NAME,
                integration_version=__version__,
            )
        return self._client

    def _execute(self, operation: Any) -> str:
        try:
            response = operation(self._get_client())
        except IFlowError as exc:
            return format_iflow_error(exc)
        return to_json_string(response)

    async def _aexecute(self, operation: Any) -> str:
        return self._execute(operation)


class IFlowWebSearchTool(_IFlowSearchToolBase):
    name: str = "iflow_web_search"
    description: str = _DESC_WEB_SEARCH
    args_schema: type[BaseModel] = WebSearchInput

    def _run(self, query: str, count: int = 10, **_: Any) -> str:
        return self._execute(
            lambda client: serialize_web_search(
                client.web_search(query=query, count=count)
            )
        )

    async def _arun(self, query: str, count: int = 10, **_: Any) -> str:
        return self._run(query=query, count=count)


class IFlowImageSearchTool(_IFlowSearchToolBase):
    name: str = "iflow_image_search"
    description: str = _DESC_IMAGE_SEARCH
    args_schema: type[BaseModel] = ImageSearchInput

    def _run(self, query: str, count: int = 10, **_: Any) -> str:
        return self._execute(
            lambda client: serialize_image_search(
                client.image_search(query=query, count=count)
            )
        )

    async def _arun(self, query: str, count: int = 10, **_: Any) -> str:
        return self._run(query=query, count=count)


class IFlowWebFetchTool(_IFlowSearchToolBase):
    name: str = "iflow_web_fetch"
    description: str = _DESC_WEB_FETCH
    args_schema: type[BaseModel] = WebFetchInput

    def _run(self, url: str, **_: Any) -> str:
        return self._execute(
            lambda client: serialize_web_fetch(client.web_fetch(url=url))
        )

    async def _arun(self, url: str, **_: Any) -> str:
        return self._run(url=url)


def create_iflow_search_tools(
    *,
    api_key: str | None = None,
    base_url: str | None = None,
    timeout: float | None = None,
    client: IFlowSearchClient | None = None,
) -> list[BaseTool]:
    """Return web search, image search, and web fetch tools in fixed order."""
    shared_kwargs: dict[str, Any] = {
        "api_key": api_key,
        "base_url": base_url,
        "timeout": timeout,
        "client": client,
    }
    return [
        IFlowWebSearchTool(**shared_kwargs),
        IFlowImageSearchTool(**shared_kwargs),
        IFlowWebFetchTool(**shared_kwargs),
    ]


__all__ = [
    "IFlowWebSearchTool",
    "IFlowImageSearchTool",
    "IFlowWebFetchTool",
    "create_iflow_search_tools",
]
