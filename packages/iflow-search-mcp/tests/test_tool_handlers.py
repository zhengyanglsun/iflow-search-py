"""Tool handler dispatch behavior.

Handlers are exercised in-process with a mock-transport-backed
``AsyncIFlowSearchClient`` — driving the actual stdio transport is reserved
for ``scripts/smoke_stdio.py``.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Any

import httpx

from iflow_search_mcp._server import build_server
from iflow_search_mcp._tools._image_search import image_search as image_tool
from iflow_search_mcp._tools._web_fetch import web_fetch as fetch_tool
from iflow_search_mcp._tools._web_search import web_search as search_tool

# --------- helpers --------------------------------------------------------


def _env_ok(data: Any) -> dict[str, Any]:
    return {
        "success": True,
        "code": "200",
        "message": "OK",
        "data": data,
        "extra": None,
        "exception": None,
    }


def _env_business(code: str, message: str = "fail") -> dict[str, Any]:
    return {
        "success": False,
        "code": code,
        "message": message,
        "data": None,
        "extra": None,
        "exception": None,
    }


def _json_response(body: dict[str, Any], status: int = 200) -> httpx.Response:
    return httpx.Response(status, json=body)


def _run(coro: Any) -> Any:
    return asyncio.run(coro)


# --------- happy path -----------------------------------------------------


def test_web_search_handler_success_text_and_structured(make_async_client_factory: Callable[..., Any]) -> None:
    canned = _env_ok(
        {
            "query": "flash attention",
            "organic": [
                {
                    "title": "Flash Attention Paper",
                    "link": "https://arxiv.org/abs/2205.14135",
                    "snippet": "An exact attention algorithm.",
                    "position": 1,
                    "date": None,
                }
            ],
        }
    )
    client, _ = make_async_client_factory(lambda req: _json_response(canned))

    text, structured = _run(
        search_tool.handler({"query": "flash attention", "count": 1}, client)
    )

    assert "Flash Attention Paper" in text
    assert "https://arxiv.org/abs/2205.14135" in text
    assert structured["query"] == "flash attention"
    assert structured["results"][0]["url"] == "https://arxiv.org/abs/2205.14135"
    # snake_case enforcement
    assert "took_ms" in structured
    assert "tookMs" not in structured


def test_image_search_handler_success(make_async_client_factory: Callable[..., Any]) -> None:
    # Bare-array data shape (documented inconsistency).
    canned = _env_ok(
        [
            {"url": "https://img.example/a.jpg", "refUrl": "https://ex/a", "title": "A pic"},
        ]
    )
    client, _ = make_async_client_factory(lambda req: _json_response(canned))

    text, structured = _run(image_tool.handler({"query": "cats"}, client))

    assert "A pic" in text
    assert "https://img.example/a.jpg" in text
    assert structured["images"][0]["image_url"] == "https://img.example/a.jpg"
    assert structured["images"][0]["source_url"] == "https://ex/a"


def test_web_fetch_handler_success(make_async_client_factory: Callable[..., Any]) -> None:
    canned = _env_ok(
        {
            "title": "Example",
            "content": "Hello world",
            "url": "https://example.com",
            "fromCache": True,
        }
    )
    client, _ = make_async_client_factory(lambda req: _json_response(canned))

    text, structured = _run(fetch_tool.handler({"url": "https://example.com"}, client))

    assert "Example" in text
    assert "Hello world" in text
    assert structured["url"] == "https://example.com"
    assert structured["from_cache"] is True
    assert "fromCache" not in structured


# --------- server-level dispatch ------------------------------------------


def test_build_server_returns_named_server(make_async_client_factory: Callable[..., Any]) -> None:
    client, _ = make_async_client_factory(lambda req: _json_response(_env_ok({})))
    server = build_server(client=client, version="0.1.0a0")
    assert server.name == "iflow-search-mcp"
    assert server.version == "0.1.0a0"


def test_tools_list_returns_three_in_order(make_async_client_factory: Callable[..., Any]) -> None:
    client, _ = make_async_client_factory(lambda req: _json_response(_env_ok({})))
    server = build_server(client=client, version="0.1.0a0")

    from mcp import types as mtypes

    # The Server stores request handlers keyed by request type. Invoke
    # ListToolsRequest handler directly with None (matches SDK internals).
    handler = server.request_handlers[mtypes.ListToolsRequest]
    result = _run(handler(None))
    # Unwrap ServerResult → ListToolsResult
    names = [t.name for t in result.root.tools]
    assert names == ["iflow_web_search", "iflow_image_search", "iflow_web_fetch"]


def test_unknown_tool_returns_is_error_with_structured_payload(
    make_async_client_factory: Callable[..., Any],
) -> None:
    client, _ = make_async_client_factory(lambda req: _json_response(_env_ok({})))
    server = build_server(client=client, version="0.1.0a0")

    from mcp import types as mtypes

    req = mtypes.CallToolRequest(
        method="tools/call",
        params=mtypes.CallToolRequestParams(name="iflow_unknown_tool", arguments={}),
    )
    result = _run(server.request_handlers[mtypes.CallToolRequest](req))
    call_result = result.root  # CallToolResult

    assert call_result.isError is True
    assert call_result.structuredContent is not None
    assert call_result.structuredContent["error"]["code"] == "unknown_tool"
    assert "iflow_unknown_tool" in call_result.structuredContent["error"]["message"]
    # text content also names the tool
    assert any("iflow_unknown_tool" in c.text for c in call_result.content)  # type: ignore[attr-defined]


def test_known_tool_business_error_becomes_isError_with_code(
    make_async_client_factory: Callable[..., Any],
) -> None:
    # 60400 → business_insufficient_credits
    canned = _env_business("60400", "out of credits")
    client, _ = make_async_client_factory(lambda req: _json_response(canned))
    server = build_server(client=client, version="0.1.0a0")

    from mcp import types as mtypes

    req = mtypes.CallToolRequest(
        method="tools/call",
        params=mtypes.CallToolRequestParams(
            name="iflow_web_search", arguments={"query": "x"}
        ),
    )
    result = _run(server.request_handlers[mtypes.CallToolRequest](req))
    call_result = result.root

    assert call_result.isError is True
    assert call_result.structuredContent is not None
    assert call_result.structuredContent["error"]["code"] == "business_insufficient_credits"


def test_known_tool_success_returns_structured_snake_case(
    make_async_client_factory: Callable[..., Any],
) -> None:
    canned = _env_ok(
        {
            "query": "x",
            "organic": [
                {
                    "title": "T",
                    "link": "https://u",
                    "snippet": "S",
                    "position": 1,
                    "date": None,
                }
            ],
        }
    )
    client, _ = make_async_client_factory(lambda req: _json_response(canned))
    server = build_server(client=client, version="0.1.0a0")

    from mcp import types as mtypes

    req = mtypes.CallToolRequest(
        method="tools/call",
        params=mtypes.CallToolRequestParams(name="iflow_web_search", arguments={"query": "x"}),
    )
    result = _run(server.request_handlers[mtypes.CallToolRequest](req))
    call_result = result.root

    assert call_result.isError is False
    assert call_result.structuredContent is not None
    assert call_result.structuredContent["results"][0]["url"] == "https://u"
    assert "took_ms" in call_result.structuredContent
    # text rendering exists
    assert any("T" in c.text for c in call_result.content)  # type: ignore[attr-defined]


def test_missing_required_argument_produces_isError(
    make_async_client_factory: Callable[..., Any],
) -> None:
    canned = _env_ok({"query": "x", "organic": []})
    client, _ = make_async_client_factory(lambda req: _json_response(canned))
    server = build_server(client=client, version="0.1.0a0")

    from mcp import types as mtypes

    req = mtypes.CallToolRequest(
        method="tools/call",
        params=mtypes.CallToolRequestParams(
            name="iflow_web_search", arguments={}  # missing 'query'
        ),
    )
    result = _run(server.request_handlers[mtypes.CallToolRequest](req))
    call_result = result.root
    assert call_result.isError is True


def test_additional_property_produces_isError(
    make_async_client_factory: Callable[..., Any],
) -> None:
    canned = _env_ok({"query": "x", "organic": []})
    client, _ = make_async_client_factory(lambda req: _json_response(canned))
    server = build_server(client=client, version="0.1.0a0")

    from mcp import types as mtypes

    req = mtypes.CallToolRequest(
        method="tools/call",
        params=mtypes.CallToolRequestParams(
            name="iflow_web_search", arguments={"query": "x", "extra_unknown": 1}
        ),
    )
    result = _run(server.request_handlers[mtypes.CallToolRequest](req))
    call_result = result.root
    assert call_result.isError is True
