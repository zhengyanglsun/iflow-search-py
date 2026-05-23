"""``iflow_web_fetch`` tool — calls ``AsyncIFlowSearchClient.web_fetch``."""

from __future__ import annotations

from typing import Any

from iflow_search import AsyncIFlowSearchClient

from ._base import ToolDefinition

_INPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "url": {
            "type": "string",
            "minLength": 1,
            "description": "Absolute URL of the page to fetch.",
        },
    },
    "required": ["url"],
    "additionalProperties": False,
}


async def _handle(
    args: dict[str, Any], client: AsyncIFlowSearchClient
) -> tuple[str, dict[str, Any]]:
    url: str = args["url"]
    response = await client.web_fetch(url=url)

    title = response.title or "(untitled)"
    text = f"{title}\n{response.url}\n\n{response.content}"
    structured = response.model_dump(mode="json", by_alias=False)
    return text, structured


web_fetch = ToolDefinition(
    name="iflow_web_fetch",
    title="iFlow Web Fetch",
    description=(
        "Fetch the readable contents of a single URL via iFlow. Use after "
        "iflow_web_search picks a promising result and you want the full text."
    ),
    input_schema=_INPUT_SCHEMA,
    handler=_handle,
)


__all__ = ["web_fetch"]
