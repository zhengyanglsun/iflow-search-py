"""Pydantic v2 request-body models for the three tool endpoints (design §6.2).

The same models are passed to FastAPI routes (so FastAPI validates inbound
bodies against them) **and** drive the schemas emitted in ``/openapi.json``.
That single-source-of-truth is the main reason FastAPI was chosen (design §4.2).

Field names (``query``, ``count``, ``url``) match the core SDK's public surface
and the LangChain adapter's args schemas. Wire-format renames
(``keywords`` / ``num``) happen inside the core — never here.

Constraints:

- ``extra="forbid"`` → unknown fields → HTTP 400 ``invalid_input``.
- ``query`` / ``url`` reject empty strings.
- ``count`` rejects ``< 1`` (sub-one count is a bug); no upper bound — the
  iFlow server is authoritative on ceilings (design §6.2, §13.3).
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


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


__all__ = ["ImageSearchBody", "WebFetchBody", "WebSearchBody"]
