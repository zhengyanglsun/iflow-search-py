"""Pydantic input schemas for CrewAI tool arguments."""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator

_COUNT_MIN = 1
_COUNT_MAX = 50


class WebSearchInput(BaseModel):
    query: str = Field(..., min_length=1, description="Search query string.")
    count: int = Field(
        default=10,
        ge=_COUNT_MIN,
        le=_COUNT_MAX,
        description="Number of results to return (1-50).",
    )


class ImageSearchInput(BaseModel):
    query: str = Field(..., min_length=1, description="Image search query string.")
    count: int = Field(
        default=10,
        ge=_COUNT_MIN,
        le=_COUNT_MAX,
        description="Number of images to return (1-50).",
    )


class WebFetchInput(BaseModel):
    url: str = Field(..., min_length=1, description="HTTP or HTTPS URL to fetch.")

    @field_validator("url")
    @classmethod
    def validate_http_url(cls, value: str) -> str:
        if not (value.startswith("http://") or value.startswith("https://")):
            raise ValueError("url must start with http:// or https://")
        return value


__all__ = ["WebSearchInput", "ImageSearchInput", "WebFetchInput"]
