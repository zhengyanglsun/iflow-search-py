#!/usr/bin/env python
"""Opt-in real-API smoke for ``iflow-search``.

Run ONE call against each of the three endpoints using a live ``IFLOW_API_KEY``.
By default this script does nothing — it must be explicitly enabled via
``IFLOW_SMOKE=1`` so it never fires during unit-test runs or CI.

Strict rules (do not relax):

* The API key is read from ``os.environ["IFLOW_API_KEY"]`` only.
* The key is never written to disk, never echoed, never embedded in errors.
* The key is redacted before any log line (via :func:`iflow_search._redact.redact_api_key`).
* No ``.env`` files are loaded. No CLI flag accepts a key.

Usage::

    IFLOW_SMOKE=1 python -m iflow_search.scripts.smoke_real_api
    # or, if the package is installed:
    IFLOW_SMOKE=1 python scripts/smoke_real_api.py

Optional environment variables:

* ``IFLOW_SMOKE_BASE_URL`` — point at a staging/proxy endpoint.
* ``IFLOW_SMOKE_QUERY`` — override the web/image query string.
* ``IFLOW_SMOKE_URL``   — override the web_fetch URL.

Exits non-zero if any of the three calls fails.
"""

from __future__ import annotations

import os
import sys

from iflow_search import IFlowError, IFlowSearchClient
from iflow_search._redact import redact_api_key


def _hr() -> None:
    print("-" * 60)


def main() -> int:
    if os.environ.get("IFLOW_SMOKE") != "1":
        print(
            "real-API smoke is opt-in. Set IFLOW_SMOKE=1 in the environment "
            "to run this script. Refusing to make live API calls.",
            file=sys.stderr,
        )
        return 0  # opt-in absence is not an error

    key = os.environ.get("IFLOW_API_KEY")
    if not key:
        print(
            "IFLOW_API_KEY is not set. Export it in your shell before running "
            "the smoke (this script will not read it from any file).",
            file=sys.stderr,
        )
        return 2

    base_url = os.environ.get("IFLOW_SMOKE_BASE_URL")
    query = os.environ.get("IFLOW_SMOKE_QUERY", "flash attention")
    img_query = os.environ.get("IFLOW_SMOKE_IMG_QUERY", "great wall of china")
    fetch_url = os.environ.get("IFLOW_SMOKE_URL", "https://zh.wikipedia.org/wiki/Wiki")

    print(f"[smoke] api key: {redact_api_key(key)}")
    print(f"[smoke] base_url: {base_url or 'default (https://platform.iflow.cn)'}")
    print(f"[smoke] web query: {query!r}")
    print(f"[smoke] image query: {img_query!r}")
    print(f"[smoke] fetch url: {fetch_url!r}")
    print()

    client = IFlowSearchClient(base_url=base_url) if base_url else IFlowSearchClient()

    failures = 0

    _hr()
    print(f"[1/3] web_search(query={query!r}, count=3)")
    try:
        r = client.web_search(query=query, count=3)
        print(f"  ok | took_ms={r.took_ms} results={len(r.results)}")
        for i, item in enumerate(r.results, 1):
            print(f"   {i}. {item.title[:80]}")
            print(f"      {item.url}")
    except IFlowError as e:
        failures += 1
        print(f"  ERR | code={e.code} message={e.message}", file=sys.stderr)

    _hr()
    print(f"[2/3] image_search(query={img_query!r}, count=3)")
    try:
        r = client.image_search(query=img_query, count=3)
        print(f"  ok | took_ms={r.took_ms} images={len(r.images)}")
        for i, item in enumerate(r.images, 1):
            print(f"   {i}. {item.title[:60]!r}")
            print(f"      image: {item.image_url[:100]}")
            print(f"      src:   {item.source_url[:100]}")
    except IFlowError as e:
        failures += 1
        print(f"  ERR | code={e.code} message={e.message}", file=sys.stderr)

    _hr()
    print(f"[3/3] web_fetch(url={fetch_url!r})")
    try:
        r = client.web_fetch(url=fetch_url)
        print(f"  ok | took_ms={r.took_ms} from_cache={r.from_cache}")
        print(f"     title: {r.title[:80]}")
        print(f"     content length: {len(r.content)} chars")
    except IFlowError as e:
        failures += 1
        print(f"  ERR | code={e.code} message={e.message}", file=sys.stderr)

    _hr()
    client.close()
    if failures:
        print(f"[smoke] {failures} endpoint(s) failed. ❌", file=sys.stderr)
        return 1
    print("[smoke] all three endpoints returned 2xx + success=true. ✅")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
