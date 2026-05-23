"""CLI entry point for ``iflow-search-mcp``.

Reads configuration from ``os.environ`` (design §6), constructs the core
``AsyncIFlowSearchClient`` with attribution kwargs (design §8), builds the
MCP server (design §7), and serves it over stdio.

Stdout is reserved for the JSON-RPC stream; all human-readable output —
including the readiness banner and configuration errors — is written to
stderr, prefixed with ``[iflow-search-mcp]`` (design §5).
"""

from __future__ import annotations

import os
import sys
from typing import NoReturn

import anyio
from iflow_search import AsyncIFlowSearchClient
from mcp.server.stdio import stdio_server

from ._config import ConfigError, ResolvedConfig, load_config
from ._server import build_server
from ._version import INTEGRATION_NAME, SOURCE, __version__

_BANNER_PREFIX = f"[{INTEGRATION_NAME}]"


def main() -> int:
    try:
        config = load_config(os.environ)
    except ConfigError as exc:
        _stderr(f"configuration error: {exc}")
        return 1

    _stderr(f"v{__version__} ready on stdio.")

    try:
        anyio.run(_serve, config)
    except (KeyboardInterrupt, anyio.get_cancelled_exc_class()):
        return 0
    return 0


async def _serve(config: ResolvedConfig) -> None:
    client_kwargs: dict[str, object] = {
        "api_key": config.api_key,
        "source": SOURCE,
        "integration_name": INTEGRATION_NAME,
        "integration_version": __version__,
    }
    if config.base_url is not None:
        client_kwargs["base_url"] = config.base_url
    if config.timeout_s is not None:
        client_kwargs["timeout"] = config.timeout_s
    if config.mcp_client_name is not None:
        client_kwargs["mcp_client_name"] = config.mcp_client_name
    if config.mcp_client_version is not None:
        client_kwargs["mcp_client_version"] = config.mcp_client_version

    client = AsyncIFlowSearchClient(**client_kwargs)  # type: ignore[arg-type]
    try:
        server = build_server(client=client, version=__version__)
        async with stdio_server() as (read_stream, write_stream):
            await server.run(
                read_stream,
                write_stream,
                server.create_initialization_options(),
            )
    finally:
        await client.aclose()


def _stderr(message: str) -> None:
    sys.stderr.write(f"{_BANNER_PREFIX} {message}\n")
    sys.stderr.flush()


def _entry() -> NoReturn:  # pragma: no cover — wrapper for ``python -m``
    raise SystemExit(main())


if __name__ == "__main__":  # pragma: no cover
    _entry()
