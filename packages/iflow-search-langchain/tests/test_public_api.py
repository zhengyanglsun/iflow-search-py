"""``__init__`` exports exactly the four factories and ``__version__`` — no more,
no less. Private symbols (the BaseTool subclasses) are not part of __all__."""

from __future__ import annotations

import iflow_search_langchain as ifsl


def test_dunder_all_is_exactly_the_documented_surface() -> None:
    assert set(ifsl.__all__) == {
        "create_iflow_web_search_tool",
        "create_iflow_image_search_tool",
        "create_iflow_web_fetch_tool",
        "create_iflow_search_tools",
        "__version__",
    }


def test_factories_are_callable() -> None:
    assert callable(ifsl.create_iflow_web_search_tool)
    assert callable(ifsl.create_iflow_image_search_tool)
    assert callable(ifsl.create_iflow_web_fetch_tool)
    assert callable(ifsl.create_iflow_search_tools)


def test_version_is_string() -> None:
    assert isinstance(ifsl.__version__, str)
    assert ifsl.__version__


def test_basetool_subclasses_not_in_public_surface() -> None:
    for forbidden in ("_WebSearchTool", "_ImageSearchTool", "_WebFetchTool"):
        assert forbidden not in ifsl.__all__
