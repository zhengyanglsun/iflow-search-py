"""Tests for env-var resolution and basic client construction."""

from __future__ import annotations

import pytest

from iflow_search import IFlowSearchClient
from iflow_search.errors import IFlowConfigError


def test_env_var_provides_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("IFLOW_API_KEY", "env-key-value")
    client = IFlowSearchClient()
    try:
        assert client._headers["Authorization"] == "Bearer env-key-value"
    finally:
        client.close()


def test_explicit_arg_overrides_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("IFLOW_API_KEY", "env-key")
    client = IFlowSearchClient(api_key="explicit-key")
    try:
        assert client._headers["Authorization"] == "Bearer explicit-key"
    finally:
        client.close()


def test_missing_key_raises_config_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("IFLOW_API_KEY", raising=False)
    with pytest.raises(IFlowConfigError) as exc:
        IFlowSearchClient()
    assert exc.value.code == "missing_api_key"


def test_default_source_is_python(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("IFLOW_API_KEY", "k")
    client = IFlowSearchClient()
    try:
        assert client._headers["IFlow-Source"] == "python"
        assert client._headers["IFlow-Integration"] == "iflow-search"
    finally:
        client.close()


def test_custom_source_passed_through(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("IFLOW_API_KEY", "k")
    client = IFlowSearchClient(
        source="my-adapter",
        integration_name="my-adapter",
        integration_version="9.9.9",
    )
    try:
        assert client._headers["IFlow-Source"] == "my-adapter"
        assert client._headers["IFlow-Integration"] == "my-adapter"
        assert client._headers["IFlow-Integration-Version"] == "9.9.9"
        assert client._headers["User-Agent"] == "my-adapter/9.9.9"
    finally:
        client.close()
