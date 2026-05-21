"""Resolve the installed package version via ``importlib.metadata``.

Falls back to ``0+unknown`` when the package is not installed (e.g. when the
source tree is run uninstalled from a checkout, or when the metadata can't be
located for some other reason).
"""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

try:
    __version__: str = version("iflow-search")
except PackageNotFoundError:  # pragma: no cover — only hit in uninstalled runs
    __version__ = "0+unknown"


__all__ = ["__version__"]
