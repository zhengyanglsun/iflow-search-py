"""Version and attribution constants for the iflow-search-mcp adapter.

These constants are forwarded to ``AsyncIFlowSearchClient`` so the core SDK
can emit the correct ``IFlow-Source``, ``IFlow-Integration``, and
``IFlow-Integration-Version`` headers (design §8 of python-mcp-design.md).
"""

from __future__ import annotations

__version__: str = "0.1.0"
INTEGRATION_NAME: str = "iflow-search-mcp"
SOURCE: str = "mcp"

__all__ = ["INTEGRATION_NAME", "SOURCE", "__version__"]
