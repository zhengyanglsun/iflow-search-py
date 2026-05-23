"""The tools satisfy LangChain's externally documented BaseTool contract
(design §13.3). Deliberately narrow — do not snapshot LangChain internals."""

from __future__ import annotations

from collections.abc import Callable

import httpx
import pytest
from iflow_search import AsyncIFlowSearchClient, IFlowSearchClient
from langchain_core.tools import BaseTool
from pydantic import BaseModel

from iflow_search_langchain._factories import (
    create_iflow_image_search_tool,
    create_iflow_search_tools,
    create_iflow_web_fetch_tool,
    create_iflow_web_search_tool,
)
from iflow_search_langchain._schemas import (
    ImageSearchArgs,
    WebFetchArgs,
    WebSearchArgs,
)


@pytest.mark.parametrize(
    ("factory", "expected_name", "expected_args"),
    [
        (create_iflow_web_search_tool, "iflow_web_search", WebSearchArgs),
        (create_iflow_image_search_tool, "iflow_image_search", ImageSearchArgs),
        (create_iflow_web_fetch_tool, "iflow_web_fetch", WebFetchArgs),
    ],
)
def test_each_tool_is_a_valid_basetool(
    factory: Callable,
    expected_name: str,
    expected_args: type,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("IFLOW_API_KEY", "k")
    tool = factory()
    assert isinstance(tool, BaseTool)
    assert tool.name == expected_name
    assert isinstance(tool.description, str) and len(tool.description) > 0
    assert tool.args_schema is expected_args
    assert issubclass(tool.args_schema, BaseModel)


def test_invoke_returns_content_string(
    make_mock_transport: Callable, fake_envelope: Callable, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``response_format='content_and_artifact'`` means ``tool.invoke(...)``
    returns the content string (per LangChain semantics)."""
    monkeypatch.delenv("IFLOW_API_KEY", raising=False)
    transport, _ = make_mock_transport(
        lambda req: httpx.Response(
            200,
            json=fake_envelope(
                data={"organic": [{"title": "A", "link": "https://a", "snippet": "x"}]}
            ),
        )
    )
    sync = IFlowSearchClient(api_key="k", http_client=httpx.Client(transport=transport))
    tool = create_iflow_web_search_tool(
        client=sync, async_client=AsyncIFlowSearchClient(api_key="k")
    )
    out = tool.invoke({"query": "q", "count": 1})
    assert isinstance(out, str)
    assert "https://a" in out


def test_create_iflow_search_tools_returns_list_of_basetool(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("IFLOW_API_KEY", "k")
    tools = create_iflow_search_tools()
    assert isinstance(tools, list)
    assert all(isinstance(t, BaseTool) for t in tools)
    assert len(tools) == 3
