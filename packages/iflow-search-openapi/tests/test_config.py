"""Tests for env-only configuration loader (design §12)."""

from __future__ import annotations

import pytest

from iflow_search_openapi._config import ConfigError, load_config


def test_api_key_required() -> None:
    with pytest.raises(ConfigError, match="IFLOW_API_KEY"):
        load_config({})


def test_api_key_empty_rejected() -> None:
    with pytest.raises(ConfigError, match="IFLOW_API_KEY"):
        load_config({"IFLOW_API_KEY": "   "})


def test_defaults_applied() -> None:
    cfg = load_config({"IFLOW_API_KEY": "k"})
    assert cfg.api_key == "k"
    assert cfg.base_url is None
    assert cfg.timeout_s is None
    assert cfg.host == "127.0.0.1"
    assert cfg.port == 8787
    assert cfg.auth_token is None
    assert cfg.cors_origin is None
    assert cfg.client_name is None


def test_base_url_passthrough() -> None:
    cfg = load_config({"IFLOW_API_KEY": "k", "IFLOW_BASE_URL": "https://stg.example.com"})
    assert cfg.base_url == "https://stg.example.com"


def test_base_url_empty_rejected() -> None:
    with pytest.raises(ConfigError, match="IFLOW_BASE_URL"):
        load_config({"IFLOW_API_KEY": "k", "IFLOW_BASE_URL": " "})


def test_timeout_ms_converted_to_seconds() -> None:
    cfg = load_config({"IFLOW_API_KEY": "k", "IFLOW_TIMEOUT_MS": "1500"})
    assert cfg.timeout_s == pytest.approx(1.5)


@pytest.mark.parametrize("bad", ["0", "-1", "abc", "1.5", ""])
def test_timeout_ms_rejected(bad: str) -> None:
    with pytest.raises(ConfigError, match="IFLOW_TIMEOUT_MS"):
        load_config({"IFLOW_API_KEY": "k", "IFLOW_TIMEOUT_MS": bad})


def test_port_parsing() -> None:
    cfg = load_config({"IFLOW_API_KEY": "k", "IFLOW_OPENAPI_PORT": "9001"})
    assert cfg.port == 9001


@pytest.mark.parametrize("bad", ["-1", "65536", "abc", "", "8.0"])
def test_port_rejected(bad: str) -> None:
    with pytest.raises(ConfigError, match="IFLOW_OPENAPI_PORT"):
        load_config({"IFLOW_API_KEY": "k", "IFLOW_OPENAPI_PORT": bad})


def test_host_accepts_ipv4() -> None:
    cfg = load_config({"IFLOW_API_KEY": "k", "IFLOW_OPENAPI_HOST": "0.0.0.0"})
    assert cfg.host == "0.0.0.0"


def test_host_accepts_bracketed_ipv6() -> None:
    cfg = load_config({"IFLOW_API_KEY": "k", "IFLOW_OPENAPI_HOST": "[::1]"})
    assert cfg.host == "[::1]"


def test_host_rejects_junk() -> None:
    with pytest.raises(ConfigError, match="IFLOW_OPENAPI_HOST"):
        load_config({"IFLOW_API_KEY": "k", "IFLOW_OPENAPI_HOST": "host with space"})


def test_auth_token_captured() -> None:
    cfg = load_config({"IFLOW_API_KEY": "k", "IFLOW_OPENAPI_AUTH_TOKEN": "tok-123"})
    assert cfg.auth_token == "tok-123"


def test_auth_token_empty_rejected() -> None:
    with pytest.raises(ConfigError, match="IFLOW_OPENAPI_AUTH_TOKEN"):
        load_config({"IFLOW_API_KEY": "k", "IFLOW_OPENAPI_AUTH_TOKEN": ""})


@pytest.mark.parametrize(
    "origin",
    [
        "*",
        "http://localhost:3000",
        "https://chat.example.com",
        "https://sub.example.com:8443",
    ],
)
def test_cors_valid(origin: str) -> None:
    cfg = load_config({"IFLOW_API_KEY": "k", "IFLOW_OPENAPI_CORS_ORIGIN": origin})
    assert cfg.cors_origin == origin


@pytest.mark.parametrize(
    "origin",
    [
        "ftp://example.com",
        "https://example.com/path",
        "https://example.com?q=1",
        "https://example.com#frag",
        "https://exa mple.com",
        "",
        " ",
    ],
)
def test_cors_invalid(origin: str) -> None:
    with pytest.raises(ConfigError, match="IFLOW_OPENAPI_CORS_ORIGIN"):
        load_config({"IFLOW_API_KEY": "k", "IFLOW_OPENAPI_CORS_ORIGIN": origin})


@pytest.mark.parametrize("name", ["open-webui", "coze.tools_v2", "abc-123"])
def test_client_name_valid(name: str) -> None:
    cfg = load_config({"IFLOW_API_KEY": "k", "IFLOW_OPENAPI_CLIENT": name})
    assert cfg.client_name == name


@pytest.mark.parametrize("name", ["UPPER", "spaces here", "x" * 65, ""])
def test_client_name_invalid(name: str) -> None:
    with pytest.raises(ConfigError, match="IFLOW_OPENAPI_CLIENT"):
        load_config({"IFLOW_API_KEY": "k", "IFLOW_OPENAPI_CLIENT": name})
