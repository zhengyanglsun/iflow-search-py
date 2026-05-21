"""Tests for the attribution-header builder."""

from __future__ import annotations

import pytest

from iflow_search._attribution import build_attribution_headers
from iflow_search.errors import IFlowConfigError


def test_required_headers_emitted() -> None:
    headers = build_attribution_headers(
        api_key="sk-test",
        source="python",
        integration_name="iflow-search",
        integration_version="0.1.0a0",
    )
    assert headers["Authorization"] == "Bearer sk-test"
    assert headers["Content-Type"] == "application/json"
    assert headers["Accept"] == "application/json"
    assert headers["IFlow-Source"] == "python"
    assert headers["IFlow-Integration"] == "iflow-search"
    assert headers["IFlow-Integration-Version"] == "0.1.0a0"
    assert headers["User-Agent"] == "iflow-search/0.1.0a0"


def test_mcp_client_name_emitted_alone() -> None:
    headers = build_attribution_headers(
        api_key="sk-test",
        source="mcp",
        integration_name="iflow-search-mcp",
        integration_version="0.1.0a0",
        mcp_client_name="hermes",
    )
    assert headers["IFlow-MCP-Client"] == "hermes"
    assert "IFlow-MCP-Client-Version" not in headers


def test_mcp_client_name_and_version_emitted_together() -> None:
    headers = build_attribution_headers(
        api_key="sk-test",
        source="mcp",
        integration_name="iflow-search-mcp",
        integration_version="0.1.0a0",
        mcp_client_name="hermes",
        mcp_client_version="1.2.3",
    )
    assert headers["IFlow-MCP-Client"] == "hermes"
    assert headers["IFlow-MCP-Client-Version"] == "1.2.3"


def test_mcp_orphan_version_raises() -> None:
    with pytest.raises(IFlowConfigError) as exc:
        build_attribution_headers(
            api_key="sk-test",
            source="mcp",
            integration_name="iflow-search-mcp",
            integration_version="0.1.0a0",
            mcp_client_version="1.2.3",
        )
    assert exc.value.code == "invalid_mcp_client_version"


@pytest.mark.parametrize(
    "name",
    [
        "hermes",
        "claude-code",
        "claude-desktop",
        "host_2.0",
        "x",
        "a" * 64,
    ],
)
def test_mcp_client_name_valid(name: str) -> None:
    headers = build_attribution_headers(
        api_key="sk-test",
        source="mcp",
        integration_name="iflow-search-mcp",
        integration_version="0.1.0a0",
        mcp_client_name=name,
    )
    assert headers["IFlow-MCP-Client"] == name


@pytest.mark.parametrize(
    "name",
    [
        "Hermes",  # uppercase rejected
        "Claude Code",  # space rejected
        "a b",
        "a" * 65,  # too long
        "",  # empty
        "name!",
    ],
)
def test_mcp_client_name_invalid(name: str) -> None:
    with pytest.raises(IFlowConfigError) as exc:
        build_attribution_headers(
            api_key="sk-test",
            source="mcp",
            integration_name="iflow-search-mcp",
            integration_version="0.1.0a0",
            mcp_client_name=name,
        )
    assert exc.value.code == "invalid_mcp_client_name"


@pytest.mark.parametrize(
    "version",
    [
        "1.2.3",
        "1.2.3-beta.4+build.5",
        "0.0.1",
        "a" * 64,
    ],
)
def test_mcp_client_version_valid(version: str) -> None:
    headers = build_attribution_headers(
        api_key="sk-test",
        source="mcp",
        integration_name="iflow-search-mcp",
        integration_version="0.1.0a0",
        mcp_client_name="hermes",
        mcp_client_version=version,
    )
    assert headers["IFlow-MCP-Client-Version"] == version


@pytest.mark.parametrize(
    "version",
    [
        "1.0 beta",  # space
        "1.0/2",  # slash
        "v 1",
        "a" * 65,
        "",
    ],
)
def test_mcp_client_version_invalid(version: str) -> None:
    with pytest.raises(IFlowConfigError) as exc:
        build_attribution_headers(
            api_key="sk-test",
            source="mcp",
            integration_name="iflow-search-mcp",
            integration_version="0.1.0a0",
            mcp_client_name="hermes",
            mcp_client_version=version,
        )
    assert exc.value.code == "invalid_mcp_client_version"


def test_missing_api_key_raises() -> None:
    with pytest.raises(IFlowConfigError) as exc:
        build_attribution_headers(
            api_key="",
            source="python",
            integration_name="iflow-search",
            integration_version="0.1.0a0",
        )
    assert exc.value.code == "missing_api_key"


def test_no_key_in_non_authorization_headers() -> None:
    secret = "sk-not-leaking-anywhere"
    headers = build_attribution_headers(
        api_key=secret,
        source="python",
        integration_name="iflow-search",
        integration_version="0.1.0a0",
        mcp_client_name="hermes",
        mcp_client_version="1.2.3",
    )
    for name, value in headers.items():
        if name == "Authorization":
            continue
        assert secret not in value, f"{name!r} leaked the API key"
