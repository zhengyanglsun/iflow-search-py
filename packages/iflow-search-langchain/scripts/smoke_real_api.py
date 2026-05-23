#!/usr/bin/env python3
"""Opt-in real-API smoke for ``iflow-search-langchain``.

Refuses to run unless ``IFLOW_LANGCHAIN_SMOKE=1`` is set. Reads
``IFLOW_API_KEY`` from the environment only (never from disk). Redacts the
key in all log output. Does not write any file. Does not import LangGraph or
any LLM provider — the adapter contract is ``(content, artifact)`` shape
correctness, not "an LLM picks the right tool."
"""

from __future__ import annotations

import os
import sys

_SMOKE_FLAG = "IFLOW_LANGCHAIN_SMOKE"
_API_KEY_ENV = "IFLOW_API_KEY"


def _redact(key: str) -> str:
    if len(key) <= 8:
        return "****"
    return key[:4] + "***" + key[-2:]


def main() -> int:
    if os.environ.get(_SMOKE_FLAG) != "1":
        print(
            f"refusing to run: set {_SMOKE_FLAG}=1 to opt in to the real-API smoke",
            file=sys.stderr,
        )
        return 2

    api_key = os.environ.get(_API_KEY_ENV)
    if not api_key:
        print(f"refusing to run: {_API_KEY_ENV} is not set", file=sys.stderr)
        return 2

    redacted = _redact(api_key)
    print(f"[smoke] using {_API_KEY_ENV}={redacted}")

    from iflow_search_langchain import create_iflow_search_tools

    tools = create_iflow_search_tools(api_key=api_key)
    by_name = {t.name: t for t in tools}

    print("[smoke] iflow_web_search('hello world', count=2)")
    content, artifact = by_name["iflow_web_search"]._run(query="hello world", count=2)
    assert isinstance(content, str) and content
    assert isinstance(artifact, dict) and "raw" in artifact
    print(f"  content_chars={len(content)}  results={len(artifact.get('results', []))}")

    print("[smoke] iflow_image_search('cat', count=2)")
    content, artifact = by_name["iflow_image_search"]._run(query="cat", count=2)
    assert isinstance(content, str) and content
    assert isinstance(artifact, dict) and "raw" in artifact
    print(f"  content_chars={len(content)}  images={len(artifact.get('images', []))}")

    print("[smoke] iflow_web_fetch('https://example.com')")
    content, artifact = by_name["iflow_web_fetch"]._run(url="https://example.com")
    assert isinstance(content, str) and content
    assert isinstance(artifact, dict) and "raw" in artifact
    print(f"  content_chars={len(content)}  title={artifact.get('title')!r}")

    print("[smoke] ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
