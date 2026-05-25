"""Env-only configuration for the iflow-search-openapi adapter (design §12).

``os.environ`` is the only configuration surface. ``load_config`` takes the env
mapping as an argument so callers (and tests) never depend on the global
``os.environ``.

Every diagnostic message — including ``ConfigError`` — refers to env vars by
name. The values are never echoed. In particular, ``IFLOW_API_KEY`` and
``IFLOW_OPENAPI_AUTH_TOKEN`` appear nowhere in this module's output (design §7.1,
§7.5).
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass

_ENV_API_KEY = "IFLOW_API_KEY"
_ENV_BASE_URL = "IFLOW_BASE_URL"
_ENV_TIMEOUT_MS = "IFLOW_TIMEOUT_MS"
_ENV_HOST = "IFLOW_OPENAPI_HOST"
_ENV_PORT = "IFLOW_OPENAPI_PORT"
_ENV_AUTH_TOKEN = "IFLOW_OPENAPI_AUTH_TOKEN"
_ENV_CORS_ORIGIN = "IFLOW_OPENAPI_CORS_ORIGIN"
_ENV_CLIENT = "IFLOW_OPENAPI_CLIENT"

_DEFAULT_HOST = "127.0.0.1"
_DEFAULT_PORT = 8787

# Matches the JS sibling's CORS_ORIGIN_PATTERN verbatim (design §9.2).
# A wildcard, or scheme://host[:port] with no path/query/fragment.
_CORS_ORIGIN_RE = re.compile(r"^(\*|https?://[A-Za-z0-9.\-]{1,253}(?::[0-9]{1,5})?)$")
# Client name banner-only tag (design §10), same shape as MCP's IFLOW_MCP_CLIENT.
_CLIENT_RE = re.compile(r"^[a-z0-9._\-]{1,64}$")

# Hostname surface accepts IPv4 dotted-quad, IPv6 bracketed/unbracketed forms,
# and DNS hostnames. The validation is conservative — we don't try to resolve
# the value, just reject obvious junk that would crash uvicorn after bind.
_HOSTNAME_RE = re.compile(r"^[A-Za-z0-9.:\[\]\-]{1,253}$")


class ConfigError(Exception):
    """Raised at startup when the env block is missing or invalid.

    The diagnostic message never echoes ``IFLOW_API_KEY`` or
    ``IFLOW_OPENAPI_AUTH_TOKEN`` values — only their names.
    """


@dataclass(frozen=True)
class ResolvedConfig:
    api_key: str
    base_url: str | None
    timeout_s: float | None
    host: str
    port: int
    auth_token: str | None
    cors_origin: str | None
    client_name: str | None


def load_config(env: Mapping[str, str]) -> ResolvedConfig:
    api_key = _require_non_empty(env, _ENV_API_KEY)
    base_url = _optional_non_empty(env, _ENV_BASE_URL)
    timeout_s = _parse_timeout_ms(env)
    host = _parse_host(env)
    port = _parse_port(env)
    auth_token = _optional_non_empty(env, _ENV_AUTH_TOKEN)
    cors_origin = _parse_cors_origin(env)
    client_name = _parse_client_name(env)

    return ResolvedConfig(
        api_key=api_key,
        base_url=base_url,
        timeout_s=timeout_s,
        host=host,
        port=port,
        auth_token=auth_token,
        cors_origin=cors_origin,
        client_name=client_name,
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
    if not raw or not raw.isdigit():
        raise ConfigError(f"{_ENV_TIMEOUT_MS} must be a positive integer number of milliseconds")
    value_ms = int(raw)
    if value_ms <= 0:
        raise ConfigError(f"{_ENV_TIMEOUT_MS} must be a positive integer number of milliseconds")
    return value_ms / 1000.0


def _parse_host(env: Mapping[str, str]) -> str:
    if _ENV_HOST not in env:
        return _DEFAULT_HOST
    raw = env[_ENV_HOST].strip()
    if not raw:
        raise ConfigError(f"{_ENV_HOST} must be a non-empty string when set")
    if not _HOSTNAME_RE.match(raw):
        raise ConfigError(
            f"{_ENV_HOST} must be a valid hostname or IP address (got an unexpected character)"
        )
    return raw


def _parse_port(env: Mapping[str, str]) -> int:
    if _ENV_PORT not in env:
        return _DEFAULT_PORT
    raw = env[_ENV_PORT].strip()
    if not raw or not raw.isdigit():
        raise ConfigError(f"{_ENV_PORT} must be an integer in [0, 65535]")
    value = int(raw)
    if value < 0 or value > 65535:
        raise ConfigError(f"{_ENV_PORT} must be an integer in [0, 65535]")
    return value


def _parse_cors_origin(env: Mapping[str, str]) -> str | None:
    if _ENV_CORS_ORIGIN not in env:
        return None
    raw = env[_ENV_CORS_ORIGIN].strip()
    if not raw:
        raise ConfigError(f"{_ENV_CORS_ORIGIN} must be a non-empty string when set")
    if not _CORS_ORIGIN_RE.match(raw):
        raise ConfigError(
            f'{_ENV_CORS_ORIGIN} must be "*" or "http(s)://host[:port]" '
            "(no path, query, or fragment)"
        )
    return raw


def _parse_client_name(env: Mapping[str, str]) -> str | None:
    if _ENV_CLIENT not in env:
        return None
    raw = env[_ENV_CLIENT].strip()
    if not raw:
        raise ConfigError(f"{_ENV_CLIENT} must be a non-empty string when set")
    if not _CLIENT_RE.match(raw):
        raise ConfigError(f"{_ENV_CLIENT} must match ^[a-z0-9._-]{{1,64}}$")
    return raw


__all__ = ["ConfigError", "ResolvedConfig", "load_config"]
