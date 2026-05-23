"""End-to-end stdio smoke for iflow-search-mcp (design §12).

Hermetic: spawns a fake iFlow HTTP server on a random localhost port and
points the spawned ``iflow-search-mcp`` subprocess at it via env vars. No
real API key is needed. Records every inbound request so we can assert the
attribution headers actually flowed env → core → wire.

Opt-in via ``IFLOW_MCP_SMOKE=1``.

Exit codes:
    0 — every assertion passed
    1 — at least one assertion failed
    2 — smoke not enabled
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import threading
import time
from collections.abc import Iterable
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

# ----- recorded fake iFlow server ----------------------------------------

_LOCK = threading.Lock()
_RECORDED: list[dict[str, Any]] = []


def _envelope(data: Any) -> bytes:
    return json.dumps(
        {
            "success": True,
            "code": "200",
            "message": "OK",
            "data": data,
            "extra": None,
            "exception": None,
        }
    ).encode("utf-8")


_RESPONSES: dict[str, bytes] = {
    "/api/search/webSearch": _envelope(
        {
            "query": "smoke",
            "organic": [
                {
                    "title": "Smoke result",
                    "link": "https://example.com/smoke",
                    "snippet": "A canned smoke response.",
                    "position": 1,
                    "date": None,
                }
            ],
        }
    ),
    "/api/search/imageSearch": _envelope(
        [
            {
                "url": "https://example.com/smoke.png",
                "refUrl": "https://example.com/smoke-page",
                "title": "Smoke image",
            }
        ]
    ),
    "/api/search/webFetch": _envelope(
        {
            "title": "Smoke page",
            "content": "fetched content",
            "url": "https://example.com/smoke",
            "fromCache": False,
        }
    ),
}


class _Handler(BaseHTTPRequestHandler):
    def do_POST(self) -> None:  # noqa: N802 — http.server API
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length) if length else b""
        path = self.path
        with _LOCK:
            _RECORDED.append(
                {
                    "path": path,
                    "headers": {k.lower(): v for k, v in self.headers.items()},
                    "body": body.decode("utf-8", errors="replace"),
                }
            )
        resp = _RESPONSES.get(path)
        if resp is None:
            self.send_response(404)
            self.end_headers()
            return
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(resp)))
        self.end_headers()
        self.wfile.write(resp)

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
        # Silence default access logging — would pollute stderr.
        return


def _start_fake_server() -> tuple[ThreadingHTTPServer, str]:
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, f"http://127.0.0.1:{port}"


# ----- assertions --------------------------------------------------------


_FAILURES: list[str] = []


def _check(cond: bool, label: str) -> None:
    status = "OK" if cond else "FAIL"
    print(f"[{status}] {label}")
    if not cond:
        _FAILURES.append(label)


def _check_in(needle: str, haystack: Iterable[str], label: str) -> None:
    _check(any(needle in h for h in haystack), label)


# ----- mcp client harness -----------------------------------------------


async def _drive(base_url: str) -> None:
    # Import here so missing optional deps surface cleanly under the smoke flag.
    from mcp import ClientSession
    from mcp.client.stdio import StdioServerParameters, stdio_client

    bin_env = {
        "IFLOW_API_KEY": "smoke-test-key",
        "IFLOW_BASE_URL": base_url,
        "IFLOW_MCP_CLIENT": "smoke-host",
        "IFLOW_MCP_CLIENT_VERSION": "9.9.9-smoke",
        # Preserve PATH so the spawned interpreter resolves correctly.
        "PATH": os.environ.get("PATH", ""),
    }

    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "iflow_search_mcp._bin"],
        env=bin_env,
    )

    async with (
        stdio_client(params) as (read_stream, write_stream),
        ClientSession(read_stream, write_stream) as session,
    ):
        await session.initialize()

        tools = await session.list_tools()
        names = [t.name for t in tools.tools]
        _check(
            names == ["iflow_web_search", "iflow_image_search", "iflow_web_fetch"],
            f"tools/list order: {names}",
        )

        result = await session.call_tool(
            "iflow_web_search", {"query": "smoke", "count": 1}
        )
        _check(not result.isError, "call_tool isError is falsy")
        text_blocks = [c.text for c in result.content if hasattr(c, "text")]
        _check_in("Smoke result", text_blocks, "text content contains canned title")
        _check(
            result.structuredContent is not None
            and result.structuredContent.get("results", [{}])[0].get("title")
            == "Smoke result",
            "structuredContent.results[0].title == 'Smoke result'",
        )


def _assert_recorded_headers() -> None:
    # Wait briefly for any in-flight POST to land.
    deadline = time.time() + 1.0
    while time.time() < deadline and not _RECORDED:
        time.sleep(0.01)

    _check(len(_RECORDED) >= 1, f"fake iFlow received {len(_RECORDED)} request(s)")
    if not _RECORDED:
        return
    req = _RECORDED[-1]
    h = req["headers"]
    _check(h.get("iflow-source") == "mcp", f"iflow-source: {h.get('iflow-source')!r}")
    _check(
        h.get("iflow-integration") == "iflow-search-mcp",
        f"iflow-integration: {h.get('iflow-integration')!r}",
    )
    _check(
        bool(h.get("iflow-integration-version")),
        f"iflow-integration-version: {h.get('iflow-integration-version')!r}",
    )
    _check(
        h.get("authorization") == "Bearer smoke-test-key",
        "authorization header matches IFLOW_API_KEY",
    )
    _check(
        h.get("iflow-mcp-client") == "smoke-host",
        f"iflow-mcp-client: {h.get('iflow-mcp-client')!r}",
    )
    _check(
        h.get("iflow-mcp-client-version") == "9.9.9-smoke",
        f"iflow-mcp-client-version: {h.get('iflow-mcp-client-version')!r}",
    )


def main() -> int:
    if os.environ.get("IFLOW_MCP_SMOKE") != "1":
        print("IFLOW_MCP_SMOKE not set — refusing to run smoke (set IFLOW_MCP_SMOKE=1)")
        return 2

    server, base_url = _start_fake_server()
    try:
        print(f"Fake iFlow listening on {base_url}")
        asyncio.run(_drive(base_url))
        _assert_recorded_headers()
    finally:
        server.shutdown()

    if _FAILURES:
        print(f"\nFAILED: {len(_FAILURES)} assertion(s)")
        for f in _FAILURES:
            print(f"  - {f}")
        return 1

    print("\nALL OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
