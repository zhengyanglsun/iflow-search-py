"""``import iflow_search_langchain`` is side-effect-free (design §5)."""

from __future__ import annotations

import os
import subprocess
import sys
import textwrap

import pytest


def test_import_with_no_env_and_no_api_key_does_not_raise(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("IFLOW_API_KEY", raising=False)
    monkeypatch.delenv("IFLOW_BASE_URL", raising=False)
    script = textwrap.dedent(
        """
        import os
        os.environ.pop("IFLOW_API_KEY", None)
        import iflow_search_langchain  # must not raise
        assert hasattr(iflow_search_langchain, "create_iflow_search_tools")
        assert hasattr(iflow_search_langchain, "__version__")
        print("ok")
        """
    )
    env = {k: v for k, v in os.environ.items() if k != "IFLOW_API_KEY"}
    result = subprocess.run(
        [sys.executable, "-c", script], env=env, capture_output=True, text=True, check=False
    )
    assert result.returncode == 0, result.stderr
    assert "ok" in result.stdout


def test_factory_call_without_api_key_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Factory invocation, in contrast, does fail fast per §12.3."""
    from iflow_search import IFlowConfigError

    from iflow_search_langchain import create_iflow_web_search_tool

    monkeypatch.delenv("IFLOW_API_KEY", raising=False)
    with pytest.raises(IFlowConfigError):
        create_iflow_web_search_tool()
