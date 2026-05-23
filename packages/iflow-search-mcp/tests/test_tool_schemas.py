"""Tool definitions (design §7) — the schemas exposed via ``tools/list`` are
the wire contract. They must match the design literally; any drift from
``additionalProperties: false`` or the no-``maximum`` rule means the
contract has silently changed.
"""

from __future__ import annotations


def test_all_tools_in_declared_order() -> None:
    from iflow_search_mcp._tools import ALL_TOOLS

    names = [t.name for t in ALL_TOOLS]
    assert names == ["iflow_web_search", "iflow_image_search", "iflow_web_fetch"]


def test_web_search_schema_literal() -> None:
    from iflow_search_mcp._tools._web_search import web_search

    assert web_search.name == "iflow_web_search"
    assert web_search.title == "iFlow Web Search"
    assert web_search.description == (
        "Search the web with iFlow. Use to find current information, news, "
        "papers, and reference pages. Returns titles, URLs, and snippets."
    )
    assert web_search.input_schema == {
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


def test_image_search_schema_literal() -> None:
    from iflow_search_mcp._tools._image_search import image_search

    assert image_search.name == "iflow_image_search"
    assert image_search.title == "iFlow Image Search"
    assert image_search.description == (
        "Search images with iFlow. Returns image URLs, titles, and the "
        "source pages they appear on."
    )
    assert image_search.input_schema == {
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


def test_web_fetch_schema_literal() -> None:
    from iflow_search_mcp._tools._web_fetch import web_fetch

    assert web_fetch.name == "iflow_web_fetch"
    assert web_fetch.title == "iFlow Web Fetch"
    assert web_fetch.description == (
        "Fetch the readable contents of a single URL via iFlow. Use after "
        "iflow_web_search picks a promising result and you want the full text."
    )
    assert web_fetch.input_schema == {
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


def test_no_count_maximum_anywhere() -> None:
    # Design §7.4: the core does not clamp count; the schema must not pretend
    # otherwise.
    from iflow_search_mcp._tools import ALL_TOOLS

    for tool in ALL_TOOLS:
        count_schema = tool.input_schema["properties"].get("count")
        if count_schema is not None:
            assert "maximum" not in count_schema, (
                f"{tool.name} schema has count.maximum; design §7.4 forbids it"
            )


def test_additional_properties_false_everywhere() -> None:
    from iflow_search_mcp._tools import ALL_TOOLS

    for tool in ALL_TOOLS:
        assert tool.input_schema.get("additionalProperties") is False, (
            f"{tool.name} schema must declare additionalProperties: false"
        )
