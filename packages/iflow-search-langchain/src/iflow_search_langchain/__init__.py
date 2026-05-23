"""iflow-search-langchain — LangChain (and LangGraph) tools for iFlow Search.

The public surface is intentionally small: four factory functions and the
package version. Everything else (BaseTool subclasses, pydantic schemas,
formatters, attribution constants) is private — their identity may change
without a major bump.
"""

from __future__ import annotations

from ._factories import (
    create_iflow_image_search_tool,
    create_iflow_search_tools,
    create_iflow_web_fetch_tool,
    create_iflow_web_search_tool,
)
from ._version import __version__

__all__ = [
    "__version__",
    "create_iflow_web_search_tool",
    "create_iflow_image_search_tool",
    "create_iflow_web_fetch_tool",
    "create_iflow_search_tools",
]
