"""__version__ matches pyproject.toml and is a PEP 440 stable release."""

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


def test_version_is_pep440_stable() -> None:
    assert re.fullmatch(r"\d+\.\d+\.\d+", __version__), (
        f"{__version__!r} is not a PEP 440 stable release"
    )
    assert not re.search(r"(a|b|rc|\.dev|\.post)\d+", __version__), (
        f"{__version__!r} carries a prerelease/dev/post suffix — package is no longer alpha"
    )
