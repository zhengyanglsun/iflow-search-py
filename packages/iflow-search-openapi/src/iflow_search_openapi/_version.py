"""Version string for the iflow-search-openapi adapter.

Kept in its own module so :mod:`__init__` can import ``__version__`` without
pulling in FastAPI, uvicorn, or the core SDK at package-import time.
"""

from __future__ import annotations

__version__: str = "0.1.0a1"

__all__ = ["__version__"]
