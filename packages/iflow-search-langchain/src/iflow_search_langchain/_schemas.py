"""Pydantic v2 args schemas used by the LangChain tools.

These schemas are passed to ``BaseTool.args_schema`` and are what LangChain
validates inputs against before invoking ``_run`` / ``_arun``. Constraints are
intentionally minimal — only the validations that are obviously safe:

* ``query`` / ``url`` reject empty strings.
* ``count`` rejects ``< 1`` (a request for fewer than one result is a bug).
* ``count`` has no upper bound — the iFlow server is authoritative on
  ceilings (see ``python-sdk-design.md`` §6.3 "Input validation").

The Python-side parameter names (``query``, ``count``, ``url``) match the core
SDK. Wire-format renames (``keywords``, ``num``) happen inside the core SDK; the
adapter does not duplicate them.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class WebSearchArgs(BaseModel):
    query: str = Field(..., min_length=1)
    count: int | None = Field(None, ge=1)


class ImageSearchArgs(BaseModel):
    query: str = Field(..., min_length=1)
    count: int | None = Field(None, ge=1)


class WebFetchArgs(BaseModel):
    url: str = Field(..., min_length=1)


__all__ = ["WebSearchArgs", "ImageSearchArgs", "WebFetchArgs"]
