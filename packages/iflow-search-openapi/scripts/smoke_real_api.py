#!/usr/bin/env python3
"""Opt-in real-API smoke for ``iflow-search-openapi`` (design §16).

Refuses to run unless ``IFLOW_OPENAPI_SMOKE=1`` is set. Reads
``IFLOW_API_KEY`` from the environment only (never from disk). Redacts the
key in all log output. Does not write any file.

Flow (design §16):

1. Load config from env.
2. Build the FastAPI app with a real ``AsyncIFlowSearchClient``.
3. Start uvicorn programmatically on ``127.0.0.1:<free port>`` in a
   background task.
4. Exercise GET /health, GET /openapi.json, and each of the three
   ``/tools/*`` endpoints with a small real query.
5. Shut uvicorn down cleanly. Exit 0 on success, 1 on failure (with a
   redacted diagnostic), 2 on missing opt-in / env.
"""

from __future__ import annotations

import asyncio
import os
import socket
import sys

_SMOKE_FLAG = "IFLOW_OPENAPI_SMOKE"
_API_KEY_ENV = "IFLOW_API_KEY"


def _redact(key: str) -> str:
    if len(key) <= 8:
        return "****"
    return key[:4] + "***" + key[-2:]


def _pick_free_port() -> int:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


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

    try:
        return asyncio.run(_run(api_key))
    except KeyboardInterrupt:
        return 1


async def _run(api_key: str) -> int:
    import httpx
    import uvicorn
    from iflow_search import AsyncIFlowSearchClient

    from iflow_search_openapi._app import build_app
    from iflow_search_openapi._config import ResolvedConfig
    from iflow_search_openapi._constants import INTEGRATION_NAME, SOURCE
    from iflow_search_openapi._version import __version__

    port = _pick_free_port()
    config = ResolvedConfig(
        api_key=api_key,
        base_url=os.environ.get("IFLOW_BASE_URL") or None,
        timeout_s=30.0,
        host="127.0.0.1",
        port=port,
        auth_token=None,
        cors_origin=None,
        client_name=None,
    )

    client = AsyncIFlowSearchClient(
        api_key=config.api_key,
        base_url=config.base_url,
        timeout=config.timeout_s,
        source=SOURCE,
        integration_name=INTEGRATION_NAME,
        integration_version=__version__,
    )
    app = build_app(client=client, config=config)

    server = uvicorn.Server(
        uvicorn.Config(
            app,
            host=config.host,
            port=config.port,
            log_config=None,
            access_log=False,
            log_level="warning",
        )
    )
    serve_task = asyncio.create_task(server.serve())

    try:
        # Wait until uvicorn flips started=True.
        for _ in range(100):
            if server.started:
                break
            await asyncio.sleep(0.05)
        else:
            print("[smoke] uvicorn never started", file=sys.stderr)
            return 1

        base = f"http://127.0.0.1:{port}"
        async with httpx.AsyncClient(base_url=base, timeout=30.0) as http:
            print("[smoke] GET /health")
            r = await http.get("/health")
            assert r.status_code == 200, r.text
            assert r.json()["ok"] is True, r.text
            assert r.json()["version"] == __version__

            print("[smoke] GET /openapi.json")
            r = await http.get("/openapi.json")
            assert r.status_code == 200, r.text
            schema = r.json()
            for tool in (
                "/tools/iflow_web_search",
                "/tools/iflow_image_search",
                "/tools/iflow_web_fetch",
            ):
                assert tool in schema["paths"], f"missing {tool}"

            print("[smoke] POST /tools/iflow_web_search")
            r = await http.post(
                "/tools/iflow_web_search",
                json={"query": "hello world", "count": 2},
            )
            assert r.status_code == 200, _scrub(r.text, api_key)
            body = r.json()
            assert body["ok"] is True, _scrub(r.text, api_key)
            data = body["data"]
            print(f"  results={len(data.get('results', []))} took_ms={data.get('took_ms')}")

            print("[smoke] POST /tools/iflow_image_search")
            r = await http.post("/tools/iflow_image_search", json={"query": "cat", "count": 2})
            assert r.status_code == 200, _scrub(r.text, api_key)
            body = r.json()
            assert body["ok"] is True, _scrub(r.text, api_key)
            data = body["data"]
            print(f"  images={len(data.get('images', []))} took_ms={data.get('took_ms')}")

            print("[smoke] POST /tools/iflow_web_fetch")
            r = await http.post("/tools/iflow_web_fetch", json={"url": "https://example.com"})
            assert r.status_code == 200, _scrub(r.text, api_key)
            body = r.json()
            assert body["ok"] is True, _scrub(r.text, api_key)
            data = body["data"]
            print(f"  title={data.get('title')!r} content_chars={len(data.get('content', ''))}")

        print("[smoke] ok")
        return 0
    finally:
        server.should_exit = True
        try:
            await asyncio.wait_for(serve_task, timeout=5.0)
        except asyncio.TimeoutError:
            serve_task.cancel()
        await client.aclose()


def _scrub(text: str, api_key: str) -> str:
    return text.replace(api_key, _redact(api_key))


if __name__ == "__main__":
    raise SystemExit(main())
