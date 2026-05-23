"""Private attribution constants for the adapter.

These are the only places in the package where the literals ``"langchain"``
and ``"iflow-search-langchain"`` appear. Other modules import from here so the
two source-of-truth strings stay in one place.

These values are forwarded into ``IFlowSearchClient`` / ``AsyncIFlowSearchClient``
constructors via ``source=`` and ``integration_name=`` kwargs. The core SDK's
``_attribution.py`` then composes them into the wire headers.
"""

from __future__ import annotations

SOURCE: str = "langchain"
INTEGRATION_NAME: str = "iflow-search-langchain"

__all__ = ["SOURCE", "INTEGRATION_NAME"]
