"""Pydantic v2 models for normalized iFlow Search responses.

The wire format uses inconsistent casing and a handful of field names that
read awkwardly in Python (``link``, ``refUrl``, ``fromCache``, ``tookMs``).
This module re-shapes them into snake_case and keeps the raw envelope on
``.raw`` for callers who need access to fields the SDK did not model.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class _BaseResponse(BaseModel):
    """Common base: ``model_config`` allows extra fields so iFlow can grow the
    payload without breaking older SDK versions, and the raw envelope is
    always preserved on ``.raw``.
    """

    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    raw: dict[str, Any] = Field(default_factory=dict)
    took_ms: int = Field(default=0)


class WebSearchResult(BaseModel):
    """One organic result in a :class:`WebSearchResponse`."""

    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    title: str = ""
    url: str = ""
    snippet: str = ""
    position: int | None = None
    date: str | None = None


class WebSearchResponse(_BaseResponse):
    """Normalized response for :py:meth:`IFlowSearchClient.web_search`."""

    query: str = ""
    results: list[WebSearchResult] = Field(default_factory=list)


class ImageResult(BaseModel):
    """One image hit in an :class:`ImageSearchResponse`."""

    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    image_url: str = ""
    source_url: str = ""
    title: str = ""
    width: int | None = None
    height: int | None = None
    position: int | None = None


class ImageSearchResponse(_BaseResponse):
    """Normalized response for :py:meth:`IFlowSearchClient.image_search`."""

    query: str = ""
    images: list[ImageResult] = Field(default_factory=list)


class WebFetchResponse(_BaseResponse):
    """Normalized response for :py:meth:`IFlowSearchClient.web_fetch`."""

    url: str = ""
    title: str = ""
    content: str = ""
    from_cache: bool = False


__all__ = [
    "WebSearchResult",
    "WebSearchResponse",
    "ImageResult",
    "ImageSearchResponse",
    "WebFetchResponse",
]
