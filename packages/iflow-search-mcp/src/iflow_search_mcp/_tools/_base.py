"""Tool definition shape shared by all three MCP tools (design §7).

Each tool is a frozen dataclass carrying its name, title, description,
JSON-Schema input definition, and an async handler that takes the parsed
arguments and an :class:`AsyncIFlowSearchClient` and returns a
``(text_summary, structured_payload)`` pair. The pair is wrapped into an
MCP tool result by ``_server.py``.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from iflow_search import AsyncIFlowSearchClient

ToolHandler = Callable[
    [dict[str, Any], AsyncIFlowSearchClient],
    Awaitable[tuple[str, dict[str, Any]]],
]


@dataclass(frozen=True)
class ToolDefinition:
    name: str
    title: str
    description: str
    input_schema: dict[str, Any]
    handler: ToolHandler


__all__ = ["ToolDefinition", "ToolHandler"]
