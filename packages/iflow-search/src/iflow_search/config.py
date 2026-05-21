"""Constants and default configuration values for the iFlow Search SDK."""

from __future__ import annotations

import re

DEFAULT_BASE_URL = "https://platform.iflow.cn"
DEFAULT_TIMEOUT_S = 30.0

ENV_API_KEY = "IFLOW_API_KEY"

DEFAULT_SOURCE = "python"
DEFAULT_INTEGRATION_NAME = "iflow-search"

MAX_ERROR_BODY_BYTES = 500

WEB_SEARCH_PATH = "/api/search/webSearch"
IMAGE_SEARCH_PATH = "/api/search/imageSearch"
WEB_FETCH_PATH = "/api/search/webFetch"

MCP_CLIENT_NAME_REGEX = re.compile(r"^[a-z0-9._-]{1,64}$")
MCP_CLIENT_VERSION_REGEX = re.compile(r"^[A-Za-z0-9._+-]{1,64}$")

__all__ = [
    "DEFAULT_BASE_URL",
    "DEFAULT_TIMEOUT_S",
    "ENV_API_KEY",
    "DEFAULT_SOURCE",
    "DEFAULT_INTEGRATION_NAME",
    "MAX_ERROR_BODY_BYTES",
    "WEB_SEARCH_PATH",
    "IMAGE_SEARCH_PATH",
    "WEB_FETCH_PATH",
    "MCP_CLIENT_NAME_REGEX",
    "MCP_CLIENT_VERSION_REGEX",
]
