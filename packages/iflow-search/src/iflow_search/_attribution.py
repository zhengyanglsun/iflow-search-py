"""Build attribution headers for outbound requests to iFlow.

This module is the single source of truth for the ``IFlow-*`` and ``User-Agent``
headers. The architecture invariant is: *no other module constructs these
headers*. If a future adapter package needs to set or override one of them, it
must do so by passing arguments into this builder, not by mutating the dict
afterwards.
"""

from __future__ import annotations

from .config import MCP_CLIENT_NAME_REGEX, MCP_CLIENT_VERSION_REGEX
from .errors import IFlowConfigError


def build_attribution_headers(
    *,
    api_key: str,
    source: str,
    integration_name: str,
    integration_version: str,
    mcp_client_name: str | None = None,
    mcp_client_version: str | None = None,
) -> dict[str, str]:
    """Return the complete header dict for an outbound iFlow request.

    ``IFlow-MCP-Client`` is emitted only when ``mcp_client_name`` is set, and
    ``IFlow-MCP-Client-Version`` only when *both* name and version are set. An
    orphan ``mcp_client_version`` (without a name) is a configuration error
    and raises :class:`IFlowConfigError` — absence of the headers is meaningful
    on the wire ("opted out") and we must not silently drop a partial pair.
    """
    if not api_key:
        raise IFlowConfigError(
            "api_key is required to build attribution headers",
            code="missing_api_key",
        )
    if not source:
        raise IFlowConfigError(
            "source is required to build attribution headers",
            code="missing_source",
        )
    if not integration_name:
        raise IFlowConfigError(
            "integration_name is required to build attribution headers",
            code="missing_integration_name",
        )
    if not integration_version:
        raise IFlowConfigError(
            "integration_version is required to build attribution headers",
            code="missing_integration_version",
        )

    if mcp_client_version is not None and mcp_client_name is None:
        raise IFlowConfigError(
            "mcp_client_version may only be set when mcp_client_name is also set",
            code="invalid_mcp_client_version",
        )

    if mcp_client_name is not None and not MCP_CLIENT_NAME_REGEX.match(mcp_client_name):
        raise IFlowConfigError(
            f"mcp_client_name {mcp_client_name!r} does not match "
            f"{MCP_CLIENT_NAME_REGEX.pattern}",
            code="invalid_mcp_client_name",
        )

    if mcp_client_version is not None and not MCP_CLIENT_VERSION_REGEX.match(mcp_client_version):
        raise IFlowConfigError(
            f"mcp_client_version {mcp_client_version!r} does not match "
            f"{MCP_CLIENT_VERSION_REGEX.pattern}",
            code="invalid_mcp_client_version",
        )

    headers: dict[str, str] = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
        "IFlow-Source": source,
        "IFlow-Integration": integration_name,
        "IFlow-Integration-Version": integration_version,
        "User-Agent": f"{integration_name}/{integration_version}",
    }

    if mcp_client_name is not None:
        headers["IFlow-MCP-Client"] = mcp_client_name
        if mcp_client_version is not None:
            headers["IFlow-MCP-Client-Version"] = mcp_client_version

    return headers


__all__ = ["build_attribution_headers"]
