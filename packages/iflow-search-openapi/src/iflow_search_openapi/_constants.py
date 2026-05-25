"""Private attribution constants for the OpenAPI adapter (design §10).

These are the only places in the package where the literals ``"openapi"`` and
``"iflow-search-openapi"`` appear. Other modules import from here so the two
source-of-truth strings stay in one place.

They are forwarded into ``AsyncIFlowSearchClient`` via ``source=`` and
``integration_name=`` kwargs; the core SDK's ``_attribution.py`` then composes
them into the wire headers. The adapter never constructs ``IFlow-*``,
``Authorization``, or ``User-Agent`` headers itself.
"""

from __future__ import annotations

SOURCE: str = "openapi"
INTEGRATION_NAME: str = "iflow-search-openapi"

__all__ = ["INTEGRATION_NAME", "SOURCE"]
