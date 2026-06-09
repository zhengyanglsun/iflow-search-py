"""Import smoke tests."""

from __future__ import annotations

import iflow_search_crewai as pkg
from iflow_search_crewai import (
    IFlowImageSearchTool,
    IFlowWebFetchTool,
    IFlowWebSearchTool,
    create_iflow_search_tools,
)


def test_public_exports() -> None:
    assert pkg.__version__ == "0.1.0"
    assert IFlowWebSearchTool().name == "iflow_web_search"
    assert IFlowImageSearchTool().name == "iflow_image_search"
    assert IFlowWebFetchTool().name == "iflow_web_fetch"
    names = [tool.name for tool in create_iflow_search_tools()]
    assert names == ["iflow_web_search", "iflow_image_search", "iflow_web_fetch"]
