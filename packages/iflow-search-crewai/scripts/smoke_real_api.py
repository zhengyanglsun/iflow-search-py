#!/usr/bin/env python3
"""Opt-in real iFlow API smoke for iflow-search-crewai.

Set IFLOW_CREWAI_SMOKE=1 and IFLOW_API_KEY in the environment.
Never prints secrets or Authorization headers.
"""

from __future__ import annotations

import json
import os
import sys


def main() -> int:
    if os.environ.get("IFLOW_CREWAI_SMOKE") != "1":
        print("Refusing to run: set IFLOW_CREWAI_SMOKE=1 to opt in.", file=sys.stderr)
        return 2
    if not os.environ.get("IFLOW_API_KEY"):
        print("IFLOW_API_KEY is not set.", file=sys.stderr)
        return 2

    from iflow_search_crewai import IFlowWebSearchTool

    tool = IFlowWebSearchTool()
    raw = tool._run(query="CrewAI iFlow Search integration", count=2)
    payload = json.loads(raw)

    if "error" in payload:
        print(f"tool={tool.name} status=error code={payload.get('code', 'unknown')}")
        return 1

    count = payload.get("result_count", 0)
    print(f"tool={tool.name} result_count={count}")
    if count:
        first = payload["results"][0]
        title = (first.get("title") or "")[:80]
        url = first.get("url") or ""
        print(f"first_title={title}")
        print(f"first_url={url}")
    print("smoke=ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
