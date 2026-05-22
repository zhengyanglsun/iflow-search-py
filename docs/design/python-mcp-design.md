# iflow-search-mcp — Design

This document describes the design of the `iflow-search-mcp` Python package: how it is structured, what the public surface looks like, how it bridges between MCP clients and the `iflow-search` core SDK, and how errors are mapped.

The package is a thin adapter. All HTTP, authentication, attribution-header construction, response normalization, and error mapping live in the core SDK (`iflow-search`). This package owns only the MCP server wiring — tool definitions, tool dispatch, and the stdio entry point.

---

## 1. Scope

`iflow-search-mcp` exposes the three `iflow-search` endpoints — web search, image search, and web fetch — as MCP tools, served over stdio. It targets any MCP-capable host (Claude Code, Claude Desktop, Hermes Agent, …) that spawns the server as a subprocess and speaks JSON-RPC over its stdio.

MVP transport is **stdio only**. HTTP / SSE / Streamable transport, client-specific packages, and embedding APIs are explicit non-goals (§10).

---

## 2. Distribution and import names

| Role | PyPI name | Import name | CLI |
|---|---|---|---|
| MCP server | `iflow-search-mcp` | `iflow_search_mcp` | `iflow-search-mcp` |

Depends on `iflow-search>=0.1.0a0,<0.2`. The core is the only sanctioned path to the iFlow API from this package.

---

## 3. Python version and runtime dependencies

- `requires-python = ">=3.10"` — same floor as the core SDK and as the official MCP SDK.
- Runtime dependencies:
  - `iflow-search>=0.1.0a0,<0.2`
  - `mcp>=1.27,<2.0`

The adapter does not pin `httpx`, `pydantic`, or `anyio` directly. The core and `mcp` already constrain them; adding a third pin here only creates resolver conflicts on upstream bumps.

Installing `mcp` transitively pulls in `starlette`, `uvicorn`, `sse-starlette`, `python-multipart`, `pyjwt[crypto]`, and `jsonschema` even for stdio-only servers. There is no `[stdio]` extra on the upstream package; this is the upstream's choice and outside our control. Disclose it in the README so operators understand the footprint.

---

## 4. Package layout

```
packages/iflow-search-mcp/
├── README.md
├── LICENSE
├── pyproject.toml
├── src/
│   └── iflow_search_mcp/
│       ├── __init__.py         # exports __version__ only
│       ├── _version.py         # VERSION, INTEGRATION_NAME, SOURCE
│       ├── _config.py          # load_config(env) -> ResolvedConfig; ConfigError
│       ├── _server.py          # build_server(client, version) -> mcp.server.lowlevel.Server
│       ├── _bin.py             # main() — CLI entry
│       ├── _errors.py          # iflow_error_to_tool_result, unexpected_error_to_tool_result
│       └── _tools/
│           ├── __init__.py     # ALL_TOOLS = (web_search, image_search, web_fetch)
│           ├── _base.py        # ToolDefinition dataclass
│           ├── _web_search.py
│           ├── _image_search.py
│           └── _web_fetch.py
├── tests/                      # offline; no real network
└── scripts/
    └── smoke_stdio.py          # opt-in, hermetic stdio smoke (§12)
```

All non-public modules are underscore-prefixed. See §10 for the rationale and the precise MVP public surface.

---

## 5. CLI behavior

The package ships one console script:

```toml
[project.scripts]
iflow-search-mcp = "iflow_search_mcp._bin:main"
```

Invocation:

```
$ iflow-search-mcp
[iflow-search-mcp] v0.1.0a0 ready on stdio.    ← stderr
(blocks, reading JSON-RPC from stdin)
```

- Transport: stdio only. No flags in MVP. All configuration flows through env (§6).
- **Stdout is reserved for the JSON-RPC stream.** The package never calls `print()`. All human-facing output — banner, init errors, fatal errors, shutdown trace — is written to **stderr**, prefixed with `[iflow-search-mcp]`.
- Exit codes:
  - `0` — clean shutdown after SIGINT or SIGTERM
  - `1` — configuration or init error before the stdio handshake
- Signal handling: SIGINT and SIGTERM trigger a graceful close of the `Server` instance and cancel the stdio task group (the `mcp` SDK is anyio-based, not raw asyncio).

---

## 6. Environment configuration

| Variable | Required | Validation | Forwarded as |
|---|---|---|---|
| `IFLOW_API_KEY` | yes | non-empty after strip | core constructor `api_key=` |
| `IFLOW_BASE_URL` | no | non-empty after strip | core `base_url=` |
| `IFLOW_TIMEOUT_MS` | no | positive integer string, parsed as ms, converted to seconds at the boundary | core `timeout=` (float seconds) |
| `IFLOW_MCP_CLIENT` | no | regex `^[a-z0-9._-]{1,64}$` | core `mcp_client_name=` |
| `IFLOW_MCP_CLIENT_VERSION` | no | regex `^[A-Za-z0-9._+-]{1,64}$`; **rejected if `IFLOW_MCP_CLIENT` is unset** | core `mcp_client_version=` |

No other source is consulted: no `.env` file, no CLI flag for the credential or any other setting, no keychain integration, no config file on disk. The MCP host's `env` block is the only configuration surface.

Any validation failure raises `ConfigError` at startup, before the stdio transport binds. The failure mode is "exit 1, diagnostic on stderr, stdout completely empty."

`IFLOW_TIMEOUT_MS` is named in milliseconds for cross-adapter operator consistency with the JS sibling `@iflow-ai/search-mcp`. The adapter converts to float seconds at the core boundary because the core takes seconds. See §13.2.

---

## 7. Tool schemas

Three tools are exposed in this fixed order. Input schemas are hand-written JSON Schema (the low-level `Server` requires them), with `additionalProperties: false` on every tool so unknown arguments are rejected at the MCP boundary.

### 7.1 `iflow_web_search`

```json
{
  "name": "iflow_web_search",
  "title": "iFlow Web Search",
  "description": "Search the web with iFlow. Use to find current information, news, papers, and reference pages. Returns titles, URLs, and snippets.",
  "inputSchema": {
    "type": "object",
    "properties": {
      "query": {"type": "string", "minLength": 1, "description": "Search query."},
      "count": {"type": "integer", "minimum": 1, "description": "Number of results."}
    },
    "required": ["query"],
    "additionalProperties": false
  }
}
```

### 7.2 `iflow_image_search`

```json
{
  "name": "iflow_image_search",
  "title": "iFlow Image Search",
  "description": "Search images with iFlow. Returns image URLs, titles, and the source pages they appear on.",
  "inputSchema": {
    "type": "object",
    "properties": {
      "query": {"type": "string", "minLength": 1, "description": "Image search query."},
      "count": {"type": "integer", "minimum": 1, "description": "Number of images."}
    },
    "required": ["query"],
    "additionalProperties": false
  }
}
```

### 7.3 `iflow_web_fetch`

```json
{
  "name": "iflow_web_fetch",
  "title": "iFlow Web Fetch",
  "description": "Fetch the readable contents of a single URL via iFlow. Use after iflow_web_search picks a promising result and you want the full text.",
  "inputSchema": {
    "type": "object",
    "properties": {
      "url": {"type": "string", "minLength": 1, "description": "Absolute URL of the page to fetch."}
    },
    "required": ["url"],
    "additionalProperties": false
  }
}
```

### 7.4 `count` is intentionally unbounded above

The core SDK does not clamp `count` to any maximum (see the `iflow-search` design doc §6.3). The tool schema must not specify `maximum` either — doing so would advertise a constraint the SDK does not enforce. The server decides the upper bound at request time.

### 7.5 Tool result shape

Success:

```json
{
  "content": [{"type": "text", "text": "<human-readable summary>"}],
  "structuredContent": {
    "query": "...",
    "took_ms": 1234,
    "results": [{"title": "...", "url": "...", "snippet": "..."}]
  }
}
```

- `content[0].text` is a model-friendly rendering — numbered titles + URLs + snippets for web search, `<title>\n   image: <url>` for image search, the readable body for fetch.
- `structuredContent` is the Pydantic response model from the core, dumped via `model_dump(mode="json", by_alias=False)`. Field names are **snake_case**, matching the core's Python response models. See §13.1 for the rationale.

Error: see §9.

---

## 8. Attribution

The adapter never constructs `Authorization`, `IFlow-*`, or `User-Agent` headers. It builds an `AsyncIFlowSearchClient` with these constructor arguments and the core does the rest (the core's design doc §7 enforces this invariant for every adapter):

```python
client = AsyncIFlowSearchClient(
    api_key=config.api_key,
    base_url=config.base_url,
    timeout=config.timeout_s,
    source="mcp",
    integration_name="iflow-search-mcp",
    integration_version=__version__,
    mcp_client_name=config.client_name,        # may be None
    mcp_client_version=config.client_version,  # may be None
)
```

Resulting headers on every outbound request:

| Header | Value | Notes |
|---|---|---|
| `Authorization` | `Bearer <IFLOW_API_KEY>` | core, from `api_key=` |
| `IFlow-Source` | `mcp` | adapter constant |
| `IFlow-Integration` | `iflow-search-mcp` | adapter constant |
| `IFlow-Integration-Version` | adapter `__version__` | adapter constant |
| `IFlow-MCP-Client` | `IFLOW_MCP_CLIENT` env value | conditional |
| `IFlow-MCP-Client-Version` | `IFLOW_MCP_CLIENT_VERSION` env value | conditional; requires `IFLOW_MCP_CLIENT` |
| `User-Agent` | `iflow-search-mcp/<version>` | core, derived |

Setting `IFLOW_MCP_CLIENT_VERSION` without `IFLOW_MCP_CLIENT` raises `ConfigError` at startup. Orphan version is rejected to keep "opt-out" (no MCP headers at all) distinguishable on the wire from "partial pair."

---

## 9. Error model

Two failure modes, mirroring the MCP spec's "Error Handling" section.

### 9.1 Unknown tool

`tools/call` with a name not in the registry returns a tool result with `isError: true`:

```json
{
  "content": [{"type": "text", "text": "Unknown tool: <name>. Available: iflow_web_search, iflow_image_search, iflow_web_fetch."}],
  "structuredContent": {
    "tool": "<name>",
    "error": {"code": "unknown_tool", "message": "Unknown tool: <name>"}
  },
  "isError": true
}
```

This matches the sibling JS adapter's behavior and avoids leaking a JSON-RPC `-32602` envelope to the model, which most MCP clients render less gracefully than `isError` results.

Implementation note: if a future version of the `mcp` SDK forces the low-level `Server` to short-circuit unknown tools into a JSON-RPC error before reaching the handler, the implementation should bypass that by registering a catch-all dispatcher and producing the `isError` result from within it.

### 9.2 Tool execution errors

Every `IFlowError` raised by the core is rendered by `iflow_error_to_tool_result(err, tool_name)`:

```json
{
  "content": [{"type": "text", "text": "<tool_name> failed: [<code>] <message>"}],
  "structuredContent": {
    "tool": "<tool_name>",
    "error": {
      "code": "<core stable code, e.g. business_insufficient_credits>",
      "message": "<error message>",
      "status_code": 429,
      "business_code": "40303",
      "response_body_truncated": "..."
    }
  },
  "isError": true
}
```

Conditional fields (`status_code`, `business_code`, `response_body_truncated`) appear in `structuredContent.error` only when the underlying `IFlowError` carries them.

Unexpected Python exceptions inside a handler are caught and rendered with `code="internal_error"`. The server never throws across the MCP boundary — bugs become structured errors the client can render, never dropped JSON-RPC frames.

### 9.3 Cancellation propagates

`asyncio.CancelledError` is never caught or wrapped at any layer. Handler `try` blocks explicitly catch `IFlowError` and `Exception`, never `BaseException`. This matches the core's invariant and is critical for MCP clients that disconnect mid-call.

### 9.4 `code` is the stable contract

The adapter dispatches on `err.code` strings only, never on exception class identity. This matches the core's design doc §8.5: `code` is the public contract, class refinements may be added in future releases without renaming codes.

---

## 10. Public API and non-goals

### 10.1 MVP public Python surface

Only one symbol is part of the supported import API:

```python
from iflow_search_mcp import __version__
```

The supported user entry point is the CLI:

```
iflow-search-mcp
```

invoked by an MCP host that supplies `IFLOW_API_KEY` (and any optional vars from §6) in the spawned process's `env` block.

### 10.2 Internal (not part of the public API)

`_config.py`, `_server.py`, `_tools/*`, `_errors.py`, `_bin.py`, `_version.py` are underscore-prefixed module names. They may change, be renamed, or be removed without a deprecation cycle. Importing them at your own risk is permitted; relying on their stability is not.

### 10.3 Explicit non-goals for MVP

- HTTP / SSE / Streamable transport (stdio only).
- Per-client packages (`iflow-search-mcp-claude-desktop` etc.).
- A public `build_server()` / tool registry export ("embed this server in my own process").
- A `.env` loader, a CLI flag for the credential, a config file, or keychain integration.
- A real-API smoke at the MCP layer (the core's `scripts/smoke_real_api.py` already covers the HTTP path).
- A `--help` / `--version` CLI flag.

These may be reconsidered after a real user requests them. The MVP optimizes for "MCP host spawns the binary, server runs, tools work."

---

## 11. Testing

All tests offline. `pytest-asyncio` in `strict` mode (matches the core).

| File | Coverage |
|---|---|
| `conftest.py` | `make_mock_transport(handler)` wrapping `httpx.MockTransport`; `fake_async_client()` builds `AsyncIFlowSearchClient(api_key="test-key", http_client=…)` |
| `test_config.py` | required key; base URL pass-through; timeout parsing (ms → s); regex validation for client name and version; orphan-version rejection; exact `ConfigError` messages |
| `test_tool_schemas.py` | each tool's `name`, `title`, `description`, and `inputSchema` are literal-equal to §7; `additionalProperties: false` is present; `tools/list` returns the three in declared order |
| `test_tool_handlers.py` | for each tool: dispatch with mock client → assert text summary shape + structured payload field-by-field; assert each `IFlowError` subclass produces `isError: true` with the correct stable `code`; assert unexpected exception → `code="internal_error"`; assert missing required argument and additional property both produce `isError` results |
| `test_errors.py` | `iflow_error_to_tool_result` for every error subclass listed in the core's §8.1; conditional fields appear only when applicable; cancellation re-raises |
| `test_stdout_purity.py` | spawn `[sys.executable, "-m", "iflow_search_mcp._bin"]` with `{}` env, then with `{IFLOW_API_KEY: test, IFLOW_TIMEOUT_MS: abc}`; assert `returncode == 1`, `stdout == b""`, stderr names the variable and does not contain `sk-` |

End-to-end stdio is covered by the smoke script (§12). Driving the actual stdio transport from inside the unit-test process is not done — handler functions are called directly with a mock client.

---

## 12. Smoke

`scripts/smoke_stdio.py` — opt-in via `IFLOW_MCP_SMOKE=1`, fully hermetic (no real API key needed):

1. Stand up a fake-iFlow HTTP server on `127.0.0.1:<random-port>` returning canned envelopes for the three endpoints. Record every inbound request (path + headers + body).
2. Use `mcp.client.stdio.stdio_client(...)` to spawn the binary as a subprocess with:
   - `IFLOW_API_KEY=smoke-test-key`
   - `IFLOW_BASE_URL=http://127.0.0.1:<port>`
   - `IFLOW_MCP_CLIENT=smoke-host`
   - `IFLOW_MCP_CLIENT_VERSION=9.9.9-smoke`
3. Wrap with `mcp.client.session.ClientSession`, `initialize()`, `list_tools()`, `call_tool("iflow_web_search", {"query": "smoke", "count": 1})`.
4. Assert:
   - `tools/list` returns `[iflow_web_search, iflow_image_search, iflow_web_fetch]` in order.
   - `call_tool` result `isError` is falsy.
   - `content[0].text` contains the canned title; `structuredContent.results[0].title == "Smoke result"`.
   - On the recorded fake-iFlow request: `iflow-source: mcp`, `iflow-integration: iflow-search-mcp`, `iflow-integration-version` non-empty, `authorization: Bearer smoke-test-key`, `iflow-mcp-client: smoke-host`, `iflow-mcp-client-version: 9.9.9-smoke`.
5. Exit 0 on all assertions passed, 1 otherwise.

Strictly stronger evidence than in-process mocking because it proves the spawned binary actually wires env → core constructor → outbound headers.

A real-API smoke at MCP layer is intentionally **not** added. The core already covers the HTTP path; a duplicate at this layer would burn quota without testing anything MCP-specific.

---

## 13. Design decisions

Locked choices made during design. Recorded here so future contributors don't re-litigate them without evidence.

### 13.1 `structuredContent` uses snake_case

Python core's response models are snake_case (`image_url`, `from_cache`, `took_ms`). The adapter dumps them as-is via `model_dump(mode="json", by_alias=False)`. The MCP spec does not constrain casing in `structuredContent`; per-language idiom is the standard pattern (cf. AWS / Stripe SDKs across languages). MCP clients that consume both the JS and Python adapters' `structuredContent` are rare; clients that consume only one benefit more from native casing than from cross-adapter uniformity.

### 13.2 `IFLOW_TIMEOUT_MS` is kept in milliseconds

The env name matches the JS sibling (`@iflow-ai/search-mcp`) for cross-adapter operator consistency. Operators who run both adapters in production benefit from a single configuration vocabulary. The adapter converts ms → float seconds at the core constructor boundary because the core takes seconds.

### 13.3 CI extends the existing matrix; no new workflow

Once implemented, the package's `pytest` / `ruff` / `mypy` / `build` gates run in the existing `.github/workflows/ci.yml` matrix, with a second `working-directory:` per gate. Fail-fast across packages. Adding a separate workflow file would just duplicate the Python-version matrix and slow status reporting.

### 13.4 Version line starts at `0.1.0a0`, prerelease semantics inherited

Same PEP 440 prerelease pattern as the core (`iflow-search==0.1.0a0`). Users `pip install --pre iflow-search-mcp` until a non-prerelease lands. Versions of the adapter and the core may diverge independently after first GA.

### 13.5 README in two places, with honest status labels

- `packages/iflow-search-mcp/README.md` — PyPI `long_description`, with install command and configuration example.
- Root `README.md` "Adapters" section — one-line entry for `iflow-search-mcp`, **marked `planned` or `pre-release` until actually published**. The install command in the root README must not pretend the package is on PyPI before it is.

### 13.6 Low-level `mcp.server.lowlevel.Server`, not FastMCP

Hand-rolled `tools/list` + `tools/call` dispatch over the low-level `Server` gives exact control over the wire schema (`minLength`, `additionalProperties: false`, no implicit `maximum`). FastMCP's decorator-driven path generates schemas from type hints and obscures the wire shape — usable, but harder to align with the core's "no client-side clamping" rule (§7.4). Matches the sibling JS adapter's structure as a side effect.

### 13.7 No public embedding API in MVP

The package exports `__version__` only. `build_server`, the tool registry, and the error mappers are internal. This minimizes the public surface that becomes a compatibility contract. Internals can be promoted to public exports when a concrete user asks for them.
