"""Attribution constants forwarded into the core SDK client."""

from __future__ import annotations

SOURCE: str = "crewai"
INTEGRATION_NAME: str = "iflow-search-crewai"

_MISSING_API_KEY_MESSAGE = (
    "IFLOW_API_KEY is required. Set it in your environment or pass api_key=..."
)

__all__ = ["SOURCE", "INTEGRATION_NAME", "_MISSING_API_KEY_MESSAGE"]
