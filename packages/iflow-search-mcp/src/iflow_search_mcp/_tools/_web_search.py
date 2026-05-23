"""``iflow_web_search`` tool — calls ``AsyncIFlowSearchClient.web_search``."""

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
            "description": "Search query.",
        },
        "count": {
            "type": "integer",
            "minimum": 1,
            "description": "Number of results.",
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
    response = await client.web_search(query=query, count=count)

    if response.results:
        lines = [
            f"{i}. {r.title}\n   {r.url}\n   {r.snippet}"
            for i, r in enumerate(response.results, start=1)
        ]
        text = "\n\n".join(lines)
    else:
        text = f"No web results for {query!r}."

    structured = response.model_dump(mode="json", by_alias=False)
    return text, structured


web_search = ToolDefinition(
    name="iflow_web_search",
    title="iFlow Web Search",
    description=(
        "Search the web with iFlow. Use to find current information, news, "
        "papers, and reference pages. Returns titles, URLs, and snippets."
    ),
    input_schema=_INPUT_SCHEMA,
    handler=_handle,
)


__all__ = ["web_search"]
