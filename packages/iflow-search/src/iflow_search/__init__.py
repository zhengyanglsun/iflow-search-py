"""iFlow Search Python SDK — public surface.

Top-level imports expose the sync and async clients, every public exception,
and the normalized response models. Internal modules (``_http``,
``_normalize``, ``_attribution``, ``_redact``) are intentionally not exported.
"""

from __future__ import annotations

from ._version import __version__
from .async_client import AsyncIFlowSearchClient
from .client import IFlowSearchClient
from .errors import (
    IFlowAPIError,
    IFlowAuthError,
    IFlowBusinessError,
    IFlowConfigError,
    IFlowError,
    IFlowInsufficientCreditsError,
    IFlowNetworkError,
    IFlowRateLimitError,
    IFlowTimeoutError,
    IFlowValidationError,
)
from .models import (
    ImageResult,
    ImageSearchResponse,
    WebFetchResponse,
    WebSearchResponse,
    WebSearchResult,
)

__all__ = [
    "__version__",
    "IFlowSearchClient",
    "AsyncIFlowSearchClient",
    # Exceptions
    "IFlowError",
    "IFlowConfigError",
    "IFlowValidationError",
    "IFlowAuthError",
    "IFlowRateLimitError",
    "IFlowInsufficientCreditsError",
    "IFlowAPIError",
    "IFlowBusinessError",
    "IFlowTimeoutError",
    "IFlowNetworkError",
    # Models
    "WebSearchResult",
    "WebSearchResponse",
    "ImageResult",
    "ImageSearchResponse",
    "WebFetchResponse",
]
