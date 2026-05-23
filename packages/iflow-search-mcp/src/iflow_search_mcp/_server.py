"""MCP server wiring (design §7, §9).

``build_server`` returns a fully configured ``mcp.server.lowlevel.Server`` with
``tools/list`` and ``tools/call`` handlers attached. The CLI entry point in
``_bin.py`` is responsible for binding the stdio transport to it.

We disable the SDK's default ``validate_input`` only because we want to
control the failure shape (``isError`` with ``structuredContent``). The
SDK's default text-only error is replaced by our richer payload that
distinguishes ``unknown_tool``, ``invalid_arguments``, IFlow error codes,
and ``internal_error``.
"""

from __future__ import annotations

from typing import Any

import jsonschema
from iflow_search import AsyncIFlowSearchClient
from iflow_search.errors import IFlowError
from mcp import types as mtypes
from mcp.server.lowlevel import Server

from ._errors import iflow_error_to_tool_result, unexpected_error_to_tool_result
from ._tools import ALL_TOOLS, ToolDefinition
from ._version import INTEGRATION_NAME


def build_server(*, client: AsyncIFlowSearchClient, version: str) -> Server:
    server: Server = Server(name=INTEGRATION_NAME, version=version)

    tool_objects: list[mtypes.Tool] = [_to_mcp_tool(t) for t in ALL_TOOLS]
    by_name: dict[str, ToolDefinition] = {t.name: t for t in ALL_TOOLS}

    @server.list_tools()  # type: ignore[no-untyped-call, untyped-decorator]
    async def _list_tools() -> list[mtypes.Tool]:
        return tool_objects

    @server.call_tool(validate_input=False)  # type: ignore[untyped-decorator]
    async def _call_tool(
        name: str, arguments: dict[str, Any]
    ) -> mtypes.CallToolResult:
        tool = by_name.get(name)
        if tool is None:
            return _dict_to_call_tool_result(_unknown_tool_result(name))

        # Local jsonschema validation produces an isError result with structured
        # content — replacing the SDK's text-only default.
        try:
            jsonschema.validate(instance=arguments, schema=tool.input_schema)
        except jsonschema.ValidationError as exc:
            return _dict_to_call_tool_result(
                _invalid_arguments_result(name, exc.message)
            )

        try:
            text, structured = await tool.handler(arguments, client)
        except IFlowError as exc:
            return _dict_to_call_tool_result(
                iflow_error_to_tool_result(exc, tool_name=name)
            )
        except Exception as exc:
            # asyncio.CancelledError is a BaseException in 3.8+, so it does NOT
            # match Exception here. It propagates as itself (design §9.3).
            return _dict_to_call_tool_result(
                unexpected_error_to_tool_result(exc, tool_name=name)
            )

        return mtypes.CallToolResult(
            content=[mtypes.TextContent(type="text", text=text)],
            structuredContent=structured,
            isError=False,
        )

    return server


def _to_mcp_tool(t: ToolDefinition) -> mtypes.Tool:
    return mtypes.Tool(
        name=t.name,
        title=t.title,
        description=t.description,
        inputSchema=t.input_schema,
    )


def _unknown_tool_result(name: str) -> dict[str, Any]:
    available = ", ".join(t.name for t in ALL_TOOLS)
    message = f"Unknown tool: {name}"
    return {
        "content": [
            {"type": "text", "text": f"{message}. Available: {available}."}
        ],
        "structuredContent": {
            "tool": name,
            "error": {"code": "unknown_tool", "message": message},
        },
        "isError": True,
    }


def _invalid_arguments_result(name: str, detail: str) -> dict[str, Any]:
    text = f"{name} failed: [invalid_arguments] {detail}"
    return {
        "content": [{"type": "text", "text": text}],
        "structuredContent": {
            "tool": name,
            "error": {"code": "invalid_arguments", "message": detail},
        },
        "isError": True,
    }


def _dict_to_call_tool_result(payload: dict[str, Any]) -> mtypes.CallToolResult:
    return mtypes.CallToolResult(
        content=[
            mtypes.TextContent(type=c["type"], text=c["text"])
            for c in payload["content"]
        ],
        structuredContent=payload.get("structuredContent"),
        isError=payload.get("isError", False),
    )


__all__ = ["build_server"]
