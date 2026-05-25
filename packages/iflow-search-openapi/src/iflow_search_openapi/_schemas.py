"""Pydantic v2 request- and response-body models for the three tool endpoints
(design §6.2, §7.4).

The request models are passed to FastAPI routes (so FastAPI validates inbound
bodies against them) **and** drive the request schemas emitted in
``/openapi.json``. That single-source-of-truth is the main reason FastAPI was
chosen (design §4.2).

The response models are passed via ``response_model=`` on each route. Routes
return :class:`fastapi.responses.JSONResponse` directly, so Pydantic does NOT
re-serialise the body — runtime payload shape is unchanged. Their purpose is
to make the 200 schemas in ``/openapi.json`` non-empty and tool-host-friendly.
Without them FastAPI emits ``"schema": {}`` for the 200 response, which Coze
rejects at import time and which causes payload-stripping at runtime (see the
platform-smoke report 2026-05-25).

Field names match what the routes already emit (``query``, ``took_ms``,
``from_cache`` — all snake_case, ``raw`` excluded by design §13.2). Wire
renames (``keywords`` / ``num`` / ``link`` / ``refUrl`` / ``fromCache``) happen
inside the core — never here.

Request constraints:

- ``extra="forbid"`` → unknown fields → HTTP 400 ``invalid_input``.
- ``query`` / ``url`` reject empty strings.
- ``count`` rejects ``< 1`` (sub-one count is a bug); no upper bound — the
  iFlow server is authoritative on ceilings (design §6.2, §13.3).
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

# ---------------------------------------------------------------------------
# Request bodies.
# ---------------------------------------------------------------------------


class WebSearchBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str = Field(min_length=1, description="Search query.")
    count: int | None = Field(default=None, ge=1, description="Number of results to return.")


class ImageSearchBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str = Field(min_length=1, description="Image search query.")
    count: int | None = Field(default=None, ge=1, description="Number of images to return.")


class WebFetchBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    url: str = Field(min_length=1, description="Absolute URL of the page to fetch.")


# ---------------------------------------------------------------------------
# Response data shapes. Mirror the runtime envelope ``data`` payload — i.e.
# what the core SDK's response models emit after ``model_dump(exclude={"raw"})``.
# Field types match the core models in ``iflow_search.models``; declaring them
# here (instead of re-exporting) keeps the OpenAPI schema readable by inlining
# the field list under tool-specific names rather than core-SDK-specific ones.
# ---------------------------------------------------------------------------


class WebSearchResultItem(BaseModel):
    model_config = ConfigDict(extra="ignore")

    title: str = Field(description="Page title.")
    url: str = Field(description="Page URL.")
    snippet: str = Field(default="", description="Short text excerpt of the page.")
    position: int | None = Field(default=None, description="1-based ranking position.")
    date: str | None = Field(default=None, description="Page publish date if known.")


class WebSearchData(BaseModel):
    model_config = ConfigDict(extra="ignore")

    query: str = Field(description="Echo of the input query.")
    results: list[WebSearchResultItem] = Field(description="Search results, ranked by position.")
    took_ms: int = Field(description="Server-side latency in milliseconds.")


class ImageSearchResultItem(BaseModel):
    model_config = ConfigDict(extra="ignore")

    image_url: str = Field(description="Direct URL of the image.")
    source_url: str = Field(default="", description="URL of the page hosting the image.")
    title: str = Field(default="", description="Image title or caption.")
    width: int | None = Field(default=None, description="Image width in pixels.")
    height: int | None = Field(default=None, description="Image height in pixels.")
    position: int | None = Field(default=None, description="1-based ranking position.")


class ImageSearchData(BaseModel):
    model_config = ConfigDict(extra="ignore")

    query: str = Field(description="Echo of the input query.")
    images: list[ImageSearchResultItem] = Field(description="Image results, ranked by position.")
    took_ms: int = Field(description="Server-side latency in milliseconds.")


class WebFetchData(BaseModel):
    model_config = ConfigDict(extra="ignore")

    url: str = Field(description="Echo of the input URL.")
    title: str = Field(default="", description="Page title if extracted.")
    content: str = Field(description="Parsed text content of the page.")
    from_cache: bool = Field(default=False, description="True if served from iFlow's cache.")
    took_ms: int = Field(description="Server-side latency in milliseconds.")


# ---------------------------------------------------------------------------
# Success envelopes. ``ok`` is pinned to literal ``True`` on the success branch
# so the schema unambiguously distinguishes success from error responses (the
# error envelope is built ad-hoc in :mod:`._errors`; its 4xx/5xx responses are
# not declared as response models on individual routes).
# ---------------------------------------------------------------------------


class WebSearchSuccess(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ok: Literal[True] = Field(description="True on success.")
    data: WebSearchData


class ImageSearchSuccess(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ok: Literal[True] = Field(description="True on success.")
    data: ImageSearchData


class WebFetchSuccess(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ok: Literal[True] = Field(description="True on success.")
    data: WebFetchData


__all__ = [
    "ImageSearchBody",
    "ImageSearchData",
    "ImageSearchResultItem",
    "ImageSearchSuccess",
    "WebFetchBody",
    "WebFetchData",
    "WebFetchSuccess",
    "WebSearchBody",
    "WebSearchData",
    "WebSearchResultItem",
    "WebSearchSuccess",
]
