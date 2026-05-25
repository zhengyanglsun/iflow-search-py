"""__version__ matches pyproject.toml and PEP 440 prerelease pattern."""

from __future__ import annotations

import re
import sys
from pathlib import Path

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib

from iflow_search_openapi._version import __version__


def test_version_matches_pyproject() -> None:
    pyproject = tomllib.loads(
        (Path(__file__).resolve().parents[1] / "pyproject.toml").read_text("utf-8")
    )
    assert __version__ == pyproject["project"]["version"]


def test_version_is_pep440_prerelease() -> None:
    assert re.fullmatch(r"\d+\.\d+\.\d+(a|b|rc)\d+", __version__), (
        f"{__version__!r} is not a PEP 440 prerelease — package is still alpha"
    )
