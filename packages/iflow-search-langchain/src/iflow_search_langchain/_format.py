"""Build short, LLM-friendly text summaries of normalized iFlow responses.

These functions produce the ``content`` half of the ``(content, artifact)``
tuple returned by the tools (design §9). The format is deliberately terse —
agents pay for every token, and the structured data is already available in
the ``artifact`` half.
"""

from __future__ import annotations

from iflow_search import (
    ImageSearchResponse,
    WebFetchResponse,
    WebSearchResponse,
)

_SNIPPET_MAX = 200
_FETCH_CONTENT_MAX = 400


def format_web_search(response: WebSearchResponse) -> str:
    n = len(response.results)
    header = f'{n} results for "{response.query}":'
    if n == 0:
        return header
    lines = [header]
    for i, r in enumerate(response.results, start=1):
        snippet = r.snippet or ""
        if len(snippet) > _SNIPPET_MAX:
            snippet = snippet[:_SNIPPET_MAX].rstrip() + "..."
        title = r.title or "(untitled)"
        url = r.url or ""
        if snippet:
            lines.append(f"{i}. {title} ({url}) — {snippet}")
        else:
            lines.append(f"{i}. {title} ({url})")
    return "\n".join(lines)


def format_image_search(response: ImageSearchResponse) -> str:
    n = len(response.images)
    header = f'{n} images for "{response.query}":'
    if n == 0:
        return header
    lines = [header]
    for i, im in enumerate(response.images, start=1):
        lines.append(f"{i}. {im.image_url} (from {im.source_url})")
    return "\n".join(lines)


def format_web_fetch(response: WebFetchResponse) -> str:
    title_line = f"Title: {response.title}" if response.title else "Title: (none)"
    content = response.content or ""
    n_chars = len(content)
    body = content[:_FETCH_CONTENT_MAX]
    if n_chars > _FETCH_CONTENT_MAX:
        body = body.rstrip() + "..."
    return f"{title_line}\nContent ({n_chars} chars): {body}"


__all__ = ["format_web_search", "format_image_search", "format_web_fetch"]
