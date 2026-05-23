"""``iflow_image_search`` tool — calls ``AsyncIFlowSearchClient.image_search``."""

from __future__ import annotations

from typing import Any

from iflow_search import AsyncIFlowSearchClient

from ._base import ToolDefinition

_INPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "query": {
            "type": "string",
            "minLength": 1,
            "description": "Image search query.",
        },
        "count": {
            "type": "integer",
            "minimum": 1,
            "description": "Number of images.",
        },
    },
    "required": ["query"],
    "additionalProperties": False,
}


async def _handle(
    args: dict[str, Any], client: AsyncIFlowSearchClient
) -> tuple[str, dict[str, Any]]:
    query: str = args["query"]
    count = args.get("count")
    response = await client.image_search(query=query, count=count)

    if response.images:
        lines = [
            f"{i}. {img.title or '(untitled)'}\n   image: {img.image_url}"
            for i, img in enumerate(response.images, start=1)
        ]
        text = "\n\n".join(lines)
    else:
        text = f"No image results for {query!r}."

    structured = response.model_dump(mode="json", by_alias=False)
    return text, structured


image_search = ToolDefinition(
    name="iflow_image_search",
    title="iFlow Image Search",
    description=(
        "Search images with iFlow. Returns image URLs, titles, and the "
        "source pages they appear on."
    ),
    input_schema=_INPUT_SCHEMA,
    handler=_handle,
)


__all__ = ["image_search"]
