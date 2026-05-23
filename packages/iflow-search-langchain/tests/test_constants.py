"""Attribution constants are stable and isolated to one module."""

from __future__ import annotations

from iflow_search_langchain import _constants


def test_source_constant() -> None:
    assert _constants.SOURCE == "langchain"


def test_integration_name_constant() -> None:
    assert _constants.INTEGRATION_NAME == "iflow-search-langchain"
