"""Tool registry for iflow-search-mcp.

``ALL_TOOLS`` is the canonical declaration order. ``tools/list`` and the
adapter's dispatch must preserve this order (design §7).
"""

from __future__ import annotations

from ._base import ToolDefinition, ToolHandler
from ._image_search import image_search
from ._web_fetch import web_fetch
from ._web_search import web_search

ALL_TOOLS: tuple[ToolDefinition, ...] = (web_search, image_search, web_fetch)

__all__ = ["ALL_TOOLS", "ToolDefinition", "ToolHandler"]
