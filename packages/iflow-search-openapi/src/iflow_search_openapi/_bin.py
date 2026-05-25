"""CLI entry point for ``iflow-search-openapi`` (design §14).

Reads configuration from ``os.environ``, constructs the core
``AsyncIFlowSearchClient`` with attribution kwargs (design §10), builds the
FastAPI app (design §11), and serves it via uvicorn on the configured
host/port.

Output contract (design §14):

- **stdout is empty.** All human-readable output goes to stderr, prefixed
  with ``[iflow-search-openapi]``. uvicorn's log config routes its lifecycle
  messages to stderr too; per-request access logs are disabled.
- Banner indicates only the *presence* of bearer / CORS / client tags — never
  their values.
- Exit codes:

  * ``0`` — clean shutdown after SIGINT / SIGTERM.
  * ``1`` — :class:`ConfigError`, port bind failure, or any init error.
"""

from __future__ import annotations

import asyncio
import os
import sys
from typing import Any, NoReturn

import uvicorn
from iflow_search import AsyncIFlowSearchClient

from ._app import build_app
from ._config import ConfigError, ResolvedConfig, load_config
from ._constants import INTEGRATION_NAME, SOURCE
from ._version import __version__

_BANNER_PREFIX = f"[{INTEGRATION_NAME}]"


def main() -> int:
    try:
        config = load_config(os.environ)
    except ConfigError as exc:
        _stderr(f"configuration error: {exc}")
        return 1

    try:
        return asyncio.run(_serve(config))
    except KeyboardInterrupt:
        return 0


async def _serve(config: ResolvedConfig) -> int:
    client_kwargs: dict[str, Any] = {
        "api_key": config.api_key,
        "source": SOURCE,
        "integration_name": INTEGRATION_NAME,
        "integration_version": __version__,
    }
    if config.base_url is not None:
        client_kwargs["base_url"] = config.base_url
    if config.timeout_s is not None:
        client_kwargs["timeout"] = config.timeout_s

    client = AsyncIFlowSearchClient(**client_kwargs)
    try:
        app = build_app(client=client, config=config)
        _stderr(_banner(config))
        server_config = uvicorn.Config(
            app,
            host=config.host,
            port=config.port,
            log_config=_log_config(),
            access_log=False,
            # uvicorn binds to the socket on startup; if the port is busy it
            # raises and we surface a config-style failure.
        )
        server = uvicorn.Server(server_config)
        try:
            await server.serve()
        except OSError as exc:
            _stderr(f"failed to bind {config.host}:{config.port}: {exc}")
            return 1
    finally:
        await client.aclose()
    return 0


def _banner(config: ResolvedConfig) -> str:
    auth_state = "ENABLED" if config.auth_token is not None else "DISABLED (open mode)"
    parts = [
        f"v{__version__} listening on http://{config.host}:{config.port}",
        f"— bearer auth {auth_state}",
    ]
    if config.cors_origin is not None:
        parts.append(f"cors={config.cors_origin}")
    if config.client_name is not None:
        parts.append(f"client={config.client_name}")
    return " ".join(parts)


def _log_config() -> dict[str, Any]:
    """uvicorn log config — everything to stderr, no access log."""
    return {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "default": {
                "()": "uvicorn.logging.DefaultFormatter",
                "fmt": "%(levelprefix)s %(message)s",
                "use_colors": None,
            },
        },
        "handlers": {
            "stderr": {
                "formatter": "default",
                "class": "logging.StreamHandler",
                "stream": "ext://sys.stderr",
            },
        },
        "loggers": {
            "uvicorn": {"handlers": ["stderr"], "level": "INFO", "propagate": False},
            "uvicorn.error": {"level": "INFO"},
            "uvicorn.access": {"handlers": ["stderr"], "level": "WARNING", "propagate": False},
        },
    }


def _stderr(message: str) -> None:
    sys.stderr.write(f"{_BANNER_PREFIX} {message}\n")
    sys.stderr.flush()


def _entry() -> NoReturn:  # pragma: no cover — wrapper for ``python -m``
    raise SystemExit(main())


if __name__ == "__main__":  # pragma: no cover
    _entry()
