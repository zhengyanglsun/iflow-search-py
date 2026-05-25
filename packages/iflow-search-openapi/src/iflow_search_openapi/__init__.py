"""iflow-search-openapi — OpenAPI 3.1 tool server for iFlow Search.

Only ``__version__`` is part of the supported public Python surface
(design §11). All other modules are underscore-prefixed and internal; the
user-facing entry point is the ``iflow-search-openapi`` console script.
"""

from __future__ import annotations

from ._version import __version__

__all__ = ("__version__",)
