"""Environment and configuration resolution tests."""

from __future__ import annotations

import pytest

from iflow_search_crewai._config import resolve_tool_config
from iflow_search_crewai.tools import IFlowWebSearchTool


def test_resolve_prefers_explicit_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("IFLOW_API_KEY", "env-key")
    cfg = resolve_tool_config(api_key="explicit-key", base_url=None, timeout=None)
    assert cfg.api_key == "explicit-key"


def test_resolve_reads_env_when_api_key_omitted(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("IFLOW_API_KEY", "env-key")
    cfg = resolve_tool_config(api_key=None, base_url=None, timeout=None)
    assert cfg.api_key == "env-key"


def test_resolve_timeout_ms_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("IFLOW_TIMEOUT_MS", "15000")
    cfg = resolve_tool_config(api_key="k", base_url=None, timeout=None)
    assert cfg.timeout_s == 15.0


def test_missing_key_run_raises_clear_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("IFLOW_API_KEY", raising=False)
    tool = IFlowWebSearchTool()
    with pytest.raises(ValueError, match="IFLOW_API_KEY is required"):
        tool._run(query="test")
