"""Serialize normalized iFlow responses into compact JSON-friendly dicts."""

from __future__ import annotations

import json
from typing import Any

from iflow_search import ImageSearchResponse, WebFetchResponse, WebSearchResponse

_SNIPPET_MAX = 400
_FETCH_CONTENT_MAX = 2000


def serialize_web_search(response: WebSearchResponse) -> dict[str, Any]:
    results = []
    for item in response.results:
        snippet = item.snippet or ""
        if len(snippet) > _SNIPPET_MAX:
            snippet = snippet[:_SNIPPET_MAX].rstrip() + "..."
        entry: dict[str, Any] = {
            "title": item.title,
            "url": item.url,
            "snippet": snippet,
        }
        if item.date:
            entry["date"] = item.date
        if item.position is not None:
            entry["position"] = item.position
        results.append(entry)
    return {
        "query": response.query,
        "result_count": len(results),
        "results": results,
        "took_ms": response.took_ms,
    }


def serialize_image_search(response: ImageSearchResponse) -> dict[str, Any]:
    images = []
    for item in response.images:
        entry: dict[str, Any] = {
            "title": item.title,
            "image_url": item.image_url,
            "source_url": item.source_url,
        }
        if item.width is not None:
            entry["width"] = item.width
        if item.height is not None:
            entry["height"] = item.height
        if item.position is not None:
            entry["position"] = item.position
        images.append(entry)
    return {
        "query": response.query,
        "image_count": len(images),
        "images": images,
        "took_ms": response.took_ms,
    }


def serialize_web_fetch(response: WebFetchResponse) -> dict[str, Any]:
    content = response.content or ""
    content_length = len(content)
    preview = content[:_FETCH_CONTENT_MAX]
    if content_length > _FETCH_CONTENT_MAX:
        preview = preview.rstrip() + "..."
    payload: dict[str, Any] = {
        "url": response.url,
        "title": response.title,
        "content": preview,
        "content_length": content_length,
        "from_cache": response.from_cache,
        "took_ms": response.took_ms,
    }
    return payload


def to_json_string(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False)


__all__ = [
    "serialize_web_search",
    "serialize_image_search",
    "serialize_web_fetch",
    "to_json_string",
]
