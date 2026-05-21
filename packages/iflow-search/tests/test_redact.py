"""Tests for the API-key redaction helper."""

from __future__ import annotations

import pytest

from iflow_search._redact import redact_api_key


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (None, "<unset>"),
        ("", "<unset>"),
        ("a", "***"),
        ("ab", "***"),
        ("abcdef", "***"),
        ("abcdefg", "abcd***fg"),
        ("sk-1234567890abcdef", "sk-1***ef"),
    ],
)
def test_redact_api_key(value: str | None, expected: str) -> None:
    assert redact_api_key(value) == expected


def test_redact_does_not_leak_middle() -> None:
    key = "sk-supersecretmiddle-XY"
    redacted = redact_api_key(key)
    assert "supersecretmiddle" not in redacted
    assert redacted.startswith("sk-s")
    assert redacted.endswith("XY")
