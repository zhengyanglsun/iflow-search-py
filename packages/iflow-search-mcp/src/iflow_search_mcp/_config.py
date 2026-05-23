"""Env-only configuration for the iflow-search-mcp adapter (design §6).

The MCP host's ``env`` block is the only configuration surface. ``load_config``
takes the env mapping as an argument so callers (and tests) never depend on
the global ``os.environ``.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass

_ENV_API_KEY = "IFLOW_API_KEY"
_ENV_BASE_URL = "IFLOW_BASE_URL"
_ENV_TIMEOUT_MS = "IFLOW_TIMEOUT_MS"
_ENV_MCP_CLIENT = "IFLOW_MCP_CLIENT"
_ENV_MCP_CLIENT_VERSION = "IFLOW_MCP_CLIENT_VERSION"

_MCP_CLIENT_RE = re.compile(r"^[a-z0-9._-]{1,64}$")
_MCP_CLIENT_VERSION_RE = re.compile(r"^[A-Za-z0-9._+-]{1,64}$")


class ConfigError(Exception):
    """Raised at startup when the env block is missing or invalid.

    The diagnostic message never echoes the API key.
    """


@dataclass(frozen=True)
class ResolvedConfig:
    api_key: str
    base_url: str | None
    timeout_s: float | None
    mcp_client_name: str | None
    mcp_client_version: str | None


def load_config(env: Mapping[str, str]) -> ResolvedConfig:
    api_key = _require_non_empty(env, _ENV_API_KEY)
    base_url = _optional_non_empty(env, _ENV_BASE_URL)
    timeout_s = _parse_timeout_ms(env)
    mcp_client_name, mcp_client_version = _parse_mcp_client(env)

    return ResolvedConfig(
        api_key=api_key,
        base_url=base_url,
        timeout_s=timeout_s,
        mcp_client_name=mcp_client_name,
        mcp_client_version=mcp_client_version,
    )


def _require_non_empty(env: Mapping[str, str], name: str) -> str:
    raw = env.get(name)
    if raw is None or not raw.strip():
        raise ConfigError(f"{name} is required and must be a non-empty string")
    return raw.strip()


def _optional_non_empty(env: Mapping[str, str], name: str) -> str | None:
    if name not in env:
        return None
    raw = env[name]
    if not raw.strip():
        raise ConfigError(f"{name} must be a non-empty string when set")
    return raw.strip()


def _parse_timeout_ms(env: Mapping[str, str]) -> float | None:
    if _ENV_TIMEOUT_MS not in env:
        return None
    raw = env[_ENV_TIMEOUT_MS].strip()
    # Strict: only digit characters, no signs, no decimals, no whitespace inside.
    if not raw or not raw.isdigit():
        raise ConfigError(
            f"{_ENV_TIMEOUT_MS} must be a positive integer number of milliseconds"
        )
    value_ms = int(raw)
    if value_ms <= 0:
        raise ConfigError(
            f"{_ENV_TIMEOUT_MS} must be a positive integer number of milliseconds"
        )
    return value_ms / 1000.0


def _parse_mcp_client(env: Mapping[str, str]) -> tuple[str | None, str | None]:
    name_raw = env.get(_ENV_MCP_CLIENT)
    version_raw = env.get(_ENV_MCP_CLIENT_VERSION)

    name = name_raw.strip() if name_raw is not None else None
    version = version_raw.strip() if version_raw is not None else None

    if version and not name:
        raise ConfigError(
            f"{_ENV_MCP_CLIENT_VERSION} is set but {_ENV_MCP_CLIENT} is not; "
            "set both or neither"
        )

    if name is not None and (not name or not _MCP_CLIENT_RE.match(name)):
        raise ConfigError(
            f"{_ENV_MCP_CLIENT} must match ^[a-z0-9._-]{{1,64}}$"
        )

    if version is not None and (not version or not _MCP_CLIENT_VERSION_RE.match(version)):
        raise ConfigError(
            f"{_ENV_MCP_CLIENT_VERSION} must match ^[A-Za-z0-9._+-]{{1,64}}$"
        )

    return (name or None, version or None)


__all__ = ["ConfigError", "ResolvedConfig", "load_config"]
