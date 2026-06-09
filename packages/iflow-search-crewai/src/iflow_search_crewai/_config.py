"""Resolve tool configuration from constructor args and environment."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass

from iflow_search.config import DEFAULT_BASE_URL, ENV_API_KEY

_ENV_BASE_URL = "IFLOW_BASE_URL"
_ENV_TIMEOUT_MS = "IFLOW_TIMEOUT_MS"


@dataclass(frozen=True)
class ToolConfig:
    api_key: str | None
    base_url: str | None
    timeout_s: float | None


def resolve_tool_config(
    *,
    api_key: str | None,
    base_url: str | None,
    timeout: float | None,
) -> ToolConfig:
    resolved_key = api_key if api_key is not None else os.environ.get(ENV_API_KEY)
    resolved_base = base_url if base_url is not None else _optional_env(_ENV_BASE_URL)
    resolved_timeout = (
        timeout if timeout is not None else _parse_timeout_ms_env(os.environ)
    )
    return ToolConfig(
        api_key=resolved_key,
        base_url=resolved_base,
        timeout_s=resolved_timeout,
    )


def _optional_env(name: str) -> str | None:
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return None
    return raw.strip()


def _parse_timeout_ms_env(env: Mapping[str, str]) -> float | None:
    raw = env.get(_ENV_TIMEOUT_MS)
    if raw is None:
        return None
    stripped = raw.strip()
    if not stripped or not stripped.isdigit():
        return None
    value_ms = int(stripped)
    if value_ms <= 0:
        return None
    return value_ms / 1000.0


def default_base_url() -> str:
    return DEFAULT_BASE_URL


__all__ = ["ToolConfig", "resolve_tool_config", "default_base_url"]
