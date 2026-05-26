"""Public ``__version__`` is the only module attribute that constitutes the
MVP public Python API (design §10.1). The integration constants used by the
core SDK's attribution headers must also be stable strings.
"""

from __future__ import annotations


def test_package_exports_version() -> None:
    import iflow_search_mcp

    assert iflow_search_mcp.__version__ == "0.1.0"


def test_version_module_constants() -> None:
    from iflow_search_mcp._version import (
        INTEGRATION_NAME,
        SOURCE,
        __version__,
    )

    assert __version__ == "0.1.0"
    assert INTEGRATION_NAME == "iflow-search-mcp"
    assert SOURCE == "mcp"


def test_public_surface_is_only_version() -> None:
    import iflow_search_mcp

    assert iflow_search_mcp.__all__ == ("__version__",)
