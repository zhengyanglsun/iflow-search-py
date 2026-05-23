"""Env-only configuration loading (design §6).

``load_config`` accepts an explicit ``env`` mapping so tests never have to
mutate ``os.environ``. Any validation failure must raise ``ConfigError`` with
a message that does not leak the API key.
"""

from __future__ import annotations

import pytest

from iflow_search_mcp._config import ConfigError, ResolvedConfig, load_config


def test_minimum_valid_env_returns_resolved_config() -> None:
    cfg = load_config({"IFLOW_API_KEY": "sk-test"})

    assert isinstance(cfg, ResolvedConfig)
    assert cfg.api_key == "sk-test"
    assert cfg.base_url is None
    assert cfg.timeout_s is None
    assert cfg.mcp_client_name is None
    assert cfg.mcp_client_version is None


def test_api_key_is_required() -> None:
    with pytest.raises(ConfigError) as exc_info:
        load_config({})
    assert "IFLOW_API_KEY" in str(exc_info.value)


def test_api_key_empty_after_strip_rejected() -> None:
    with pytest.raises(ConfigError) as exc_info:
        load_config({"IFLOW_API_KEY": "   "})
    assert "IFLOW_API_KEY" in str(exc_info.value)


def test_api_key_value_is_not_echoed_in_error() -> None:
    # Even if a future bug echoed env values, never the API key.
    try:
        load_config({})
    except ConfigError as exc:
        assert "sk-" not in str(exc)


def test_base_url_pass_through_stripped() -> None:
    cfg = load_config(
        {
            "IFLOW_API_KEY": "k",
            "IFLOW_BASE_URL": " https://staging.example.com/  ",
        }
    )
    assert cfg.base_url == "https://staging.example.com/"


def test_base_url_blank_rejected() -> None:
    with pytest.raises(ConfigError) as exc_info:
        load_config({"IFLOW_API_KEY": "k", "IFLOW_BASE_URL": "  "})
    assert "IFLOW_BASE_URL" in str(exc_info.value)


def test_timeout_ms_parsed_and_converted_to_seconds() -> None:
    cfg = load_config({"IFLOW_API_KEY": "k", "IFLOW_TIMEOUT_MS": "1500"})
    assert cfg.timeout_s == 1.5


def test_timeout_ms_zero_rejected() -> None:
    with pytest.raises(ConfigError) as exc_info:
        load_config({"IFLOW_API_KEY": "k", "IFLOW_TIMEOUT_MS": "0"})
    assert "IFLOW_TIMEOUT_MS" in str(exc_info.value)


def test_timeout_ms_negative_rejected() -> None:
    with pytest.raises(ConfigError) as exc_info:
        load_config({"IFLOW_API_KEY": "k", "IFLOW_TIMEOUT_MS": "-5"})
    assert "IFLOW_TIMEOUT_MS" in str(exc_info.value)


def test_timeout_ms_non_integer_rejected() -> None:
    with pytest.raises(ConfigError) as exc_info:
        load_config({"IFLOW_API_KEY": "k", "IFLOW_TIMEOUT_MS": "abc"})
    assert "IFLOW_TIMEOUT_MS" in str(exc_info.value)


def test_timeout_ms_float_string_rejected() -> None:
    with pytest.raises(ConfigError) as exc_info:
        load_config({"IFLOW_API_KEY": "k", "IFLOW_TIMEOUT_MS": "1.5"})
    assert "IFLOW_TIMEOUT_MS" in str(exc_info.value)


def test_mcp_client_name_valid_regex() -> None:
    cfg = load_config({"IFLOW_API_KEY": "k", "IFLOW_MCP_CLIENT": "claude-desktop"})
    assert cfg.mcp_client_name == "claude-desktop"


def test_mcp_client_name_uppercase_rejected() -> None:
    with pytest.raises(ConfigError) as exc_info:
        load_config({"IFLOW_API_KEY": "k", "IFLOW_MCP_CLIENT": "Claude-Desktop"})
    assert "IFLOW_MCP_CLIENT" in str(exc_info.value)


def test_mcp_client_name_too_long_rejected() -> None:
    with pytest.raises(ConfigError):
        load_config({"IFLOW_API_KEY": "k", "IFLOW_MCP_CLIENT": "a" * 65})


def test_mcp_client_name_special_char_rejected() -> None:
    with pytest.raises(ConfigError):
        load_config({"IFLOW_API_KEY": "k", "IFLOW_MCP_CLIENT": "claude desktop"})


def test_mcp_client_version_requires_client_name() -> None:
    # Orphan version is rejected at startup (design §6, §8).
    with pytest.raises(ConfigError) as exc_info:
        load_config(
            {
                "IFLOW_API_KEY": "k",
                "IFLOW_MCP_CLIENT_VERSION": "1.2.3",
            }
        )
    msg = str(exc_info.value)
    assert "IFLOW_MCP_CLIENT_VERSION" in msg
    assert "IFLOW_MCP_CLIENT" in msg


def test_mcp_client_version_valid() -> None:
    cfg = load_config(
        {
            "IFLOW_API_KEY": "k",
            "IFLOW_MCP_CLIENT": "claude-desktop",
            "IFLOW_MCP_CLIENT_VERSION": "1.2.3-beta+build.5",
        }
    )
    assert cfg.mcp_client_name == "claude-desktop"
    assert cfg.mcp_client_version == "1.2.3-beta+build.5"


def test_mcp_client_version_invalid_char_rejected() -> None:
    with pytest.raises(ConfigError):
        load_config(
            {
                "IFLOW_API_KEY": "k",
                "IFLOW_MCP_CLIENT": "claude-desktop",
                "IFLOW_MCP_CLIENT_VERSION": "1.2.3 build5",
            }
        )


def test_mcp_client_version_too_long_rejected() -> None:
    with pytest.raises(ConfigError):
        load_config(
            {
                "IFLOW_API_KEY": "k",
                "IFLOW_MCP_CLIENT": "claude-desktop",
                "IFLOW_MCP_CLIENT_VERSION": "1." * 33,  # 66 chars
            }
        )
