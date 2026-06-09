"""Single source of truth for the package version.

The value here must match ``[project].version`` in ``pyproject.toml``.
``tests/test_version.py`` enforces this.
"""

from __future__ import annotations

__version__ = "0.1.0"

__all__ = ["__version__"]
