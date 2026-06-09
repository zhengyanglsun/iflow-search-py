"""Keep package version in sync across metadata files."""

from __future__ import annotations

from pathlib import Path

import iflow_search_crewai

try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib  # type: ignore[no-redef]


def test_version_matches_pyproject() -> None:
    pyproject = Path(__file__).resolve().parents[1] / "pyproject.toml"
    data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    assert iflow_search_crewai.__version__ == data["project"]["version"]
