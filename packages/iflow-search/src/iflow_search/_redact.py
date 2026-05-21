"""API key redaction for log/error messages."""

from __future__ import annotations


def redact_api_key(value: str | None) -> str:
    """Return a redacted form of an API key safe for logs and error messages.

    Rules:
    - None or empty → ``<unset>``
    - length <= 6 → ``***``
    - else → first 4 chars + ``***`` + last 2 chars
    """
    if value is None or value == "":
        return "<unset>"
    if len(value) <= 6:
        return "***"
    return f"{value[:4]}***{value[-2:]}"


__all__ = ["redact_api_key"]
