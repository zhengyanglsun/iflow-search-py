# iflow-search Python SDK Research Report

> **Status: research only.** No Python package created, no code written, no version moved, no real key touched. All claims below are sourced from (a) the JS repo at `/Users/lzy/Documents/iFlow-search-api/iflow-search-js/`, (b) `platform.iflow.cn/docs/`, or (c) the `iflow-ai/iflow-skills` repo. Anything I could not verify is marked **uncertain** in section 10.

Generated: 2026-05-21.

---

## 1. Executive Summary

- The JS monorepo's central rule — *all HTTP, auth, attribution headers, error mapping live in `@iflow-ai/search-core` and nowhere else* — is the most important invariant to mirror in Python. Adapters must stay thin.
- Three iFlow endpoints are stable and documented: `POST /api/search/webSearch`, `POST /api/search/imageSearch`, `POST /api/search/webFetch`. Request surfaces are intentionally minimal (`keywords` + `num`, or `url`). No filters, regions, time-ranges, languages, or freshness controls exist.
- The wire envelope `{ success, code, message, data, extra, exception }` is uniform. Business errors come back as `success: false` with numeric-string codes (`"40303"`, `"90402"`, `"90001"`, `"90002"`, `"60400"`, `"400"`, `"500"`). HTTP status alignment is **not documented** — Python port must observe at runtime, not assume.
- The JS `Result<T,E>` discriminated-union pattern (`{ ok, data | error }`) should NOT be ported. Python idiom is an exception hierarchy; serialization to dict happens explicitly when needed (e.g. for MCP tool results).
- Recommended PyPI shipping plan: ship **`iflow-search`** (core), **`iflow-search-langchain`** (covers LangChain + LangGraph + LangChain v1 `create_agent`), **`iflow-search-mcp`** (a `console_scripts` entry-point launched via `uvx`/`pipx`). Optionally **`iflow-search-openapi`** (FastAPI app) for Open WebUI, Coze, and other OpenAPI-aware platforms.
- **Do NOT ship dedicated packages for** LangGraph, Hermes, Claude Code, iFlow CLI, OpenClaw, Open WebUI, Coze — they all consume one of the three artifacts above. This rubric is locked on the JS side and we should mirror it.
- **CrewAI status is unsettled.** The JS docs reject a dedicated PyPI CrewAI adapter and recommend MCP. CrewAI's MCP support (`crewai-tools[mcp]`) makes this reasonable. Defer the decision until after MVP.
- Attribution headers (`IFlow-Source`, `IFlow-Integration`, `IFlow-Integration-Version`, `User-Agent`, plus optional `IFlow-MCP-Client[-Version]`) should be reproduced byte-for-byte in casing and value semantics. `IFlow-Source` for Python LangChain is the only naming call that should be deliberated — see §10.
- Use `httpx` + Pydantic v2 + `pytest` + `respx` + `ruff` + `mypy`/`pyright` + `hatchling`. Python `>=3.10`. Provide both sync and async clients from day 1.
- Initial release on PyPI as `0.1.0a0` (PEP 440 prerelease) — direct analog of JS `next` dist-tag, since `pip install` excludes prereleases unless `--pre` is passed. Promotion to `0.1.0` requires the same two-MCP-client smoke gate the JS side has locked in.
- **iFlow CLI scheduled sunset 2026-04-17** (per their docs); today is 2026-05-21. Confirm current status before investing integration time. The MCP server still serves Claude Code and Hermes regardless.

---

## 2. Current JS Architecture Findings

### Shape that should be mirrored

| JS pattern | Python equivalent | Reason |
|---|---|---|
| Three-package split `search-core` / `search-langchain` / `search-mcp` | `iflow-search` (core) + `iflow-search-langchain` + `iflow-search-mcp` | The split exists because LangChain and MCP have distinct peer/runtime dep matrices. Same constraints apply in Python (different optional deps). |
| Zero-runtime-dep core | Core: only `httpx` + `pydantic`; no LangChain/MCP imports | Lets the core be reused from FastAPI, scripts, custom agents without dragging in unused deps. |
| Three stable tool names `iflow_web_search`, `iflow_image_search`, `iflow_web_fetch` | Use the **identical strings** | Prompts and agent traces refer to these names. Cross-language renaming would break observability. |
| Identical tool descriptions byte-for-byte between LangChain and MCP packages | Define description strings once in core, reuse from both adapters | Avoids drift; matches JS. |
| Param wire-format rename: caller passes `query` / `count`, SDK sends `keywords` / `num` | Same rename in Python | The wire format is awkward; the SDK protects users from it. |
| Param rename in normalized output: `link → url`, `url → imageUrl`, `refUrl → sourceUrl` | Same in Python (snake_case: `link → url`, `url → image_url`, `ref_url → source_url`) | Output ergonomics. |
| `tookMs` measured client-side, included in normalized result | `took_ms` measured via `time.monotonic_ns()` | Useful for observability without any extra deps. |
| Abort/cancellation via `AbortSignal` parameter | Native `asyncio.CancelledError` + per-request `timeout` parameter | Don't replicate the JS API surface; use idiomatic Python. |
| Error-body truncation to 500 chars on `api_error.detail` | Same, as a named constant | Bounds memory under hostile or large 5xx bodies. |
| MCP server uses stdio only; CLI key from `env`, never CLI flag, never file | Identical policy in Python | Security model. JS doc explicitly forbids `~/.iflow-search-mcp.json`, `.env` discovery, and CLI flags for the key. Python must also avoid `python-dotenv` auto-loading in the MCP server. |
| Stdout-purity test for MCP server (asserts `stdout == ""` on bad config) | Same test in Python, asserting `sys.stdout` was never written | Critical because Python `print()` and `logging.basicConfig()` default to stdout. |
| Smoke test stands up a fake iFlow HTTP server on `127.0.0.1:<random>` and spawns the real binary | Same pattern in Python using `http.server` or `aiohttp` + `subprocess` + the Python MCP client SDK | High-value; ports cleanly. |
| Pre-publish secret scan over diff & working tree | Identical | Use the same regex against `IFLOW_API_KEY=sk-...` patterns plus PyPI tokens. |
| Pre-publish artifact-content inspection (only `dist/`, `README.md`, `LICENSE`, `package.json`) | Same: inspect built sdist/wheel — no `src/` (in sdist OK), no `tests/`, no `.env`, no `__pycache__/` | Direct port of the JS check. |
| LangGraph reuses LangChain tools, no separate package | Same: no `iflow-search-langgraph` package, document the reuse pattern with `create_agent(tools=[...])` | The JS rejection rationale ("would be a re-export") applies verbatim. |

### Shape that should NOT be ported

| JS choice | Reason to drop |
|---|---|
| `Result<T,E>` discriminated union `{ ok, data \| error }` | JS idiom (avoid `try/catch`). Python idiom is real exceptions with attributes. Raises on failure. |
| Plain-object errors (not `Error` subclasses) | Exists in JS only because `JSON.stringify(error)` loses fields. Python exception attributes serialize fine via `.__dict__` or explicit `to_dict()`. Use a real exception hierarchy. |
| Injectable `fetch?: typeof fetch` for testing | Python tests `httpx` via `respx` (mock transport) — no need to pass a function. |
| `createIFlowSearchClient(opts)` factory wrapping a constructor | Pointless in Python; just expose `IFlowSearchClient(...)`. |
| `ENV_API_KEY` exported as constant but never read by core | Python single-package SDK should read `IFLOW_API_KEY` from env as a friendly default, with explicit `api_key=` still preferred. |
| AbortError → `network_timeout` even when caller-cancelled | This is a JS bug. Python should distinguish: caller cancel → re-raise `asyncio.CancelledError`; SDK timeout → `IFlowTimeoutError`. |
| `createRequire(import.meta.url)("../package.json").version` for runtime version | Python uses `importlib.metadata.version("iflow-search")`. No file read at runtime. |
| Camel-case fields (`tookMs`, `fromCache`, `imageUrl`) on normalized output | Python uses `snake_case` (`took_ms`, `from_cache`, `image_url`). Pydantic's `alias` + `model_config(populate_by_name=True)` can map between wire and Python names if needed. |
| Low-level MCP `Server` chosen over `McpServer` to avoid Zod runtime dep | In Python the analogous "minimize deps" pressure doesn't exist — Pydantic is already core. Use `FastMCP` (decorator-based, ergonomic). |
| `next` npm dist-tag mechanics | Use PEP 440 prereleases (`0.1.0a0`, `0.1.0rc0`). `pip install` skips them unless `--pre`. Same end-user behavior. |
| `workspace:*` protocol + pack-time rewrite | Python monorepo tooling differs (uv workspaces / Poetry path deps). Just pin a concrete `>=0.1.0a0` across sibling packages in pyproject.toml at publish time. |
| Peer dependencies pattern | Python has no peer deps. Declare `langchain-core>=0.3,<2` directly; users install one package. |

### Hard rules to inherit verbatim

1. **No `httpx`/`requests` calls in adapter packages.** Only in the core. Same as the JS "no `fetch` in adapter source" rule.
2. **No throwing across the MCP boundary.** Catch everything, return `is_error=True` tool results.
3. **Stdout is reserved for MCP frames.** All diagnostics to stderr.
4. **API key off the filesystem.** Env vars only. No `.env` auto-load in the MCP server. No CLI flag for the key.
5. **One MCP process = one iFlow account.** Multi-key support is users adding a second `mcpServers` entry.
6. **Publish is manual.** No CI workflow uploads to PyPI.

---

## 3. API Surface Findings

Base URL: `https://platform.iflow.cn`. Auth: `Authorization: Bearer <key>`. Per-key rate cap: **1000 RPM** total across all three endpoints. Credit cost per successful call: web 1, image 3, fetch 2 (failed calls free).

### 3.1 `POST /api/search/webSearch`

**Request body**

```json
{ "keywords": "<string, required>", "num": <int, optional> }
```

**Response body** (in `data`)

```json
{
  "query": "<string>",
  "organic": [
    { "title": "<string>", "link": "<string>", "snippet": "<string>",
      "position": <int>, "date": "<string|null>" }
  ]
}
```

### 3.2 `POST /api/search/imageSearch`

**Request body**

```json
{ "keywords": "<string, required>", "num": <int, optional> }
```

**Response body** — `data` is a bare **Array** (not an object; contradicts the generic `data: Object` description in `api-reference`):

```json
[ { "url": "<image-url>", "refUrl": "<source-page>", "title": "<string|empty>" } ]
```

The skill repo's shell scripts also show `width`, `height`, `position` fields, which the JS `search-core` normalizer already handles defensively — they may be present in practice even though the official table omits them. **Uncertain.**

### 3.3 `POST /api/search/webFetch`

**Request body**

```json
{ "url": "<absolute-url, required>" }
```

**Response body** (in `data`)

```json
{ "title": "<string>", "content": "<string>", "url": "<string>", "fromCache": <bool> }
```

### 3.4 Common envelope

```json
{
  "success": true|false,
  "code": "<numeric-string>",
  "message": "<string>",
  "data": <Object|Array|null>,
  "extra": null,
  "exception": null
}
```

### 3.5 Documented business error codes

| `code` | Meaning |
|---|---|
| `200` | success |
| `400` | param validation |
| `500` | upstream/internal |
| `40303` | rate limit (1000 RPM) |
| `60400` | insufficient credits |
| `90001` | webFetch parse failure |
| `90002` | search returned no results |
| `90402` | invalid API key |

### 3.6 What is NOT documented (and the Python port must not invent)

- HTTP status alignment per business code (does `40303` come with HTTP `429`? Probably, but unconfirmed).
- Max value of `num`. JS SDK clamps to **20** but this is the SDK's choice, not the API's spec.
- Default `num` (docs say 10; skill CLI uses 15; server-side absent-`num` behavior unconfirmed).
- Rate-limit response headers (no documented `X-RateLimit-*`).
- Pagination, cursors, streaming — none documented; assume none.
- `Accept: text/markdown` behavior — docs say it's the default and returns "structured Markdown", but the Markdown schema is not specified. JS SDK and skills always send `Accept: application/json`. **Python SDK should do the same.**
- Whether `webFetch` response `url` reflects redirects or canonicalization.
- Cache TTL / key for `fromCache`.
- API key format and per-key quota beyond the shared 1000 RPM cap.

---

## 4. Recommended Python Package Design

### 4.1 Distribution / import names

| Role | PyPI name | Import name | Notes |
|---|---|---|---|
| Core | `iflow-search` | `iflow_search` | Single short umbrella name, no scope mimicry. |
| LangChain adapter | `iflow-search-langchain` | `iflow_search_langchain` | Also covers LangGraph & LangChain v1 `create_agent`. |
| MCP server | `iflow-search-mcp` | `iflow_search_mcp` | Provides `[project.scripts]` entry: `iflow-search-mcp`. Run via `uvx iflow-search-mcp` or `pipx run iflow-search-mcp`. |
| OpenAPI server (P3) | `iflow-search-openapi` | `iflow_search_openapi` | Optional FastAPI app for Open WebUI / Coze. Defer until after MVP. |

**Alternative naming considered and rejected:**

- `iflow-ai-search-core` — mirrors the npm `@iflow-ai/` scope but is more verbose than necessary; PyPI has no scope concept and `iflow-search-*` already unambiguously identifies the publisher.
- `iflow.search` namespace packages — adds tooling complexity, gives no real benefit until there are >5 sibling packages.

### 4.2 Python version

`requires-python = ">=3.10"` — gives `match` statement, modern type syntax (`X | None`), structural pattern matching for error-mapping code, and is supported by every framework target (LangChain, LangGraph, CrewAI, MCP, FastAPI).

### 4.3 Runtime dependencies

**`iflow-search` (core):**

- `httpx>=0.27,<1.0` — sync + async HTTP from one lib, native `MockTransport` for testing
- `pydantic>=2.7,<3.0` — for input/output models, json-schema generation, validation

**`iflow-search-langchain`:**

- `iflow-search` (sibling, pinned to concrete version at publish)
- `langchain-core>=0.3,<2.0` — covers both 0.3.x and 1.x lines; tools API is stable across both

**`iflow-search-mcp`:**

- `iflow-search` (sibling, pinned)
- `mcp[cli]>=1.8.0,<2.0`

### 4.4 Dev dependencies (under `[dependency-groups]` / `[project.optional-dependencies].dev`)

- `pytest>=8`, `pytest-asyncio>=0.23`
- `respx>=0.21` — `httpx` mock transport, lets us assert request shape without monkeypatching
- `ruff>=0.4` — single linter + formatter
- `mypy>=1.10` or `pyright` — pick one; mypy has broader ecosystem support
- `hatchling` as the build backend (`tool.hatch.*` in `pyproject.toml`)
- `build` + `twine` for the publish pipeline
- For the MCP package only: `pytest-timeout` (the smoke test spawns a child process and we need a hard deadline)

### 4.5 Sync vs async

**Ship both from day one.** A subset of consumers needs each:

| Consumer | Needs |
|---|---|
| FastAPI route handlers | async |
| CrewAI tools | sync (BaseTool._run is sync; _arun is optional) |
| LangChain tools | sync `_run` and async `_arun` both common |
| MCP server (FastMCP) | async (FastMCP handlers are async) |
| Jupyter / scripts / Streamlit | sync |

Implementation pattern:

- `IFlowSearchClient` (sync, wraps `httpx.Client`)
- `AsyncIFlowSearchClient` (wraps `httpx.AsyncClient`)
- Shared `_serialize_request` / `_normalize_response` helpers in core (pure functions over Pydantic models)
- Identical method signatures except for `async`/`await`

Do not implement the async client by running the sync client in a thread pool — that creates deadlocks under FastAPI/asyncio. Two real clients sharing pure helpers is the clean shape.

### 4.6 Response types

**Use Pydantic v2 models.** Reasons:

- LangChain `StructuredTool(args_schema=...)` accepts Pydantic models directly.
- MCP `FastMCP` derives tool schemas from function signatures (Pydantic-typed args generate JSON Schema automatically).
- FastAPI uses Pydantic natively for OpenAPI generation.
- Pydantic v2's strict-mode + `model_validate` handles iFlow's inconsistent shapes (e.g. image `data` as bare Array) cleanly.

Models (snake_case Python fields, with `alias` to match wire when needed):

```
WebSearchResult { title, url, snippet, position, date }      # alias url <- link
WebSearchResponse { query, count, took_ms, results: list[WebSearchResult] }
ImageResult { image_url, source_url, title, width, height, position }  # alias from url/refUrl
ImageSearchResponse { query, count, took_ms, images: list[ImageResult] }
WebFetchResponse { url, title, content, from_cache, took_ms }
```

Keep the raw response body accessible too (`.raw: dict[str, Any]`) for users who need fields the SDK didn't model.

### 4.7 Recommended core directory layout

```
src/iflow_search/
  __init__.py            # public exports: IFlowSearchClient, AsyncIFlowSearchClient, exceptions, models
  _version.py            # exposes __version__ via importlib.metadata
  client.py              # IFlowSearchClient (sync)
  async_client.py        # AsyncIFlowSearchClient
  _http.py               # shared request building, header construction, response parsing
  _attribution.py        # IFlow-Source / Integration / Version header builder (mirrors JS headers.ts)
  config.py              # constants: DEFAULT_BASE_URL, DEFAULT_TIMEOUT_S, MAX_*_COUNT, ENV_API_KEY
  errors.py              # exception hierarchy
  models.py              # Pydantic input/output models
  _normalize.py          # raw envelope -> Pydantic model conversion
  _redact.py             # redact_api_key()
tests/
  test_client_sync.py
  test_client_async.py
  test_headers.py
  test_errors.py
  test_normalize.py
  conftest.py            # respx fixtures, fake-iflow factory
pyproject.toml
README.md
LICENSE
```

### 4.8 Public API sketch (not implementation)

```python
from iflow_search import IFlowSearchClient

client = IFlowSearchClient(
    api_key="...",                       # required; also reads IFLOW_API_KEY from env if omitted
    source="my-app",                     # required if you're a downstream adapter; defaults to "core"
    integration_name="iflow-search",     # defaults to this package name
    integration_version=...,             # defaults to importlib.metadata.version()
    base_url=None,                       # defaults to DEFAULT_BASE_URL
    timeout=30.0,                        # seconds
    http_client=None,                    # inject httpx.Client for testing or shared session
    mcp_client_name=None,                # only set by MCP adapter
    mcp_client_version=None,             # only meaningful with mcp_client_name
)

response = client.web_search(query="flash attention", count=5)
# raises IFlowAuthError / IFlowRateLimitError / IFlowAPIError / IFlowTimeoutError on failure
# returns WebSearchResponse on success

for r in response.results:
    print(r.title, r.url)
```

---

## 5. Integration Matrix

| Platform | Recommended Python path | Dedicated package? | MVP | Full |
|---|---|---|---|---|
| **LangChain Python** | `langchain-core` tools shipped as standalone `iflow-search-langchain` | **Yes** | `@tool`-decorated functions wrapping `IFlowSearchClient` | `BaseTool` subclass per tool with Pydantic `args_schema`, async `_arun`, structured tool result via `content_and_artifact` (matches JS LangChain behavior) |
| **LangGraph Python** | Reuse `iflow-search-langchain` tools in `langgraph.prebuilt.create_react_agent` or LangChain v1's `langchain.agents.create_agent` | **No** | Document the import pattern in `iflow-search-langchain` README | Add `examples/langgraph_agent.py` mirroring the JS example |
| **CrewAI** | Defer — JS docs explicitly reject a dedicated package until MCP is proven insufficient. Path 1: route via `iflow-search-mcp` + `crewai-tools[mcp]`. Path 2: ship a thin `iflow-search-crewai` only if user demand justifies it. | **No (initially)** | Provide a CrewAI recipe doc + example showing the MCP bridge | Re-evaluate after 6 months; if demand exists, ship `BaseTool` subclass package depending on `iflow-search` |
| **MCP** (Hermes, Claude Code, iFlow CLI, OpenClaw, Claude Desktop) | One Python MCP server (`iflow-search-mcp`) over stdio | **Yes** | `FastMCP` server with the three tools, env-only config, secrets via `env:` block in client config | Add Streamable HTTP transport behind a transport factory (kept off MVP per JS non-goals); add resources for "saved searches"; cross-client smoke against at least Claude Code + Claude Desktop (the JS-side 0.1.0 gate, mirrored) |
| **Open WebUI** | OpenAPI tool server (Open WebUI docs explicitly recommend this over native Python Tools) | **No** (reuse `iflow-search-openapi`) | FastAPI app exposing the three endpoints with `operation_id`s; doc the base URL + how to add it to Open WebUI's tool servers panel | Honor `X-OpenWebUI-Chat-Id` for observability, CORS config, optional API-key reverse-proxy auth |
| **Coze** | Same FastAPI / OpenAPI server; users import the YAML into the Coze console | **No** | Provide `openapi.yaml` snippet + Coze import walkthrough | Document `service_http` auth config and (later) OAuth 2.0 plugin authoring |
| **FastAPI / OpenAPI** | First-class artifact — same code that serves Open WebUI and Coze | **Yes (optional)** | FastAPI app: `title`, `version`, `servers`, `operation_id` per endpoint, Pydantic `Field(description=...)` everywhere | Add `fastapi_mcp` bridge so the same app also exposes itself as an MCP server (dual-mode) |
| **OpenClaw** | MCP server (if platform turns out to be real and worth investing in — see §10) | **No** | Reuse `iflow-search-mcp` | Verify ecosystem authority first |
| **Hermes Agent** | MCP server | **No** | Reuse `iflow-search-mcp`; document `~/.hermes/config.yaml` `mcp_servers:` snippet (YAML, not JSON) | Document `allowed_tools` filtering |
| **Claude Code / iFlow CLI** | MCP server | **No** | Reuse `iflow-search-mcp`; document `.mcp.json` + `~/.iflow/settings.json` snippets | One-click install snippet using `claude mcp add-json` |

---

## 6. Attribution Header Design

### 6.1 Headers the Python core must always emit

| Header | Source | Value | Override allowed? |
|---|---|---|---|
| `Authorization` | core | `Bearer ${api_key}` | no |
| `Content-Type` | core | `application/json` | no |
| `Accept` | core | `application/json` | no (markdown response shape is undocumented) |
| `IFlow-Source` | caller-supplied via `source=` | non-empty string, ASCII slug | YES, by adapters; users typically don't set it |
| `IFlow-Integration` | caller-supplied via `integration_name=` | typically the package name | YES, by adapters |
| `IFlow-Integration-Version` | caller-supplied via `integration_version=` | semver string | YES, by adapters |
| `User-Agent` | core | `${integration_name}/${integration_version}` | no (derived) |

### 6.2 Headers conditionally emitted

| Header | When emitted | Value |
|---|---|---|
| `IFlow-MCP-Client` | only when `mcp_client_name` is non-empty | from `mcp_client_name`; matches regex `^[a-z0-9._-]{1,64}$` |
| `IFlow-MCP-Client-Version` | only when BOTH `mcp_client_name` AND `mcp_client_version` are non-empty | matches regex `^[A-Za-z0-9._+-]{1,64}$`; orphan version (without name) raises `ConfigError` |

These are surfaced only by `iflow-search-mcp`. Other adapters must not set them.

### 6.3 Recommended `IFlow-Source` values per adapter

| Adapter | `IFlow-Source` | `IFlow-Integration` |
|---|---|---|
| `iflow-search` used directly | `core` | `iflow-search` |
| `iflow-search-langchain` | `langchain` | `iflow-search-langchain` |
| `iflow-search-mcp` | `mcp` | `iflow-search-mcp` |
| `iflow-search-openapi` (planned) | `openapi` | `iflow-search-openapi` |

**Open question:** Should the Python LangChain adapter send `IFlow-Source: langchain` (matching JS) or `langchain-py` (to differentiate language at the backend)? See §10.

### 6.4 Override policy

| Field | User can override? | Why |
|---|---|---|
| `api_key` | yes (explicit arg or env) | the whole point |
| `source` | yes if calling the core directly; locked by adapters | downstream applications might want their own slug |
| `integration_name` | yes (advanced) | for apps wrapping our SDK |
| `integration_version` | yes (advanced) | matches the above |
| `base_url` | yes | dev/staging/proxy environments |
| `timeout` | yes | network-conditions-dependent |
| `Authorization` | no | derived from `api_key` only |
| `Content-Type` / `Accept` | no | wire format is fixed |
| `User-Agent` | no | derived from integration name + version |
| `IFlow-MCP-Client[-Version]` | no (set by MCP adapter from env only) | controlled allowlist per JS design |

### 6.5 What must NOT be openable

- `Authorization` cannot be overridden by an arbitrary string — only the `api_key` arg flows into it.
- `User-Agent` cannot accept a freeform string — it's a derived value.
- `IFlow-Source` cannot be empty, and adapter packages should lock it to their published name.
- No mechanism should let a user disable the attribution headers wholesale.

---

## 7. Error Model

### 7.1 Exception hierarchy

```
IFlowError(Exception)                        # base — every SDK exception inherits from this
├── IFlowConfigError                         # missing api_key, invalid attribution, invalid env regex
├── IFlowValidationError                     # client-side param check failed before request
├── IFlowAuthError                           # HTTP 401/403 OR business code 90402
├── IFlowRateLimitError                      # HTTP 429 OR business code 40303
├── IFlowInsufficientCreditsError            # business code 60400
├── IFlowAPIError                            # HTTP 5xx, non-JSON 2xx, or other non-2xx
│   └── attrs: status_code: int, response_body: str|None, response_id: str|None
├── IFlowBusinessError                       # success=false with any other code
│   └── attrs: business_code: str, business_message: str|None
├── IFlowTimeoutError                        # SDK-initiated timeout (httpx.TimeoutException)
└── IFlowNetworkError                        # DNS, connection refused, TLS, etc. (httpx.NetworkError)
```

Cancellation (caller-initiated `asyncio.CancelledError`) is **not** caught — it propagates as itself.

### 7.2 Common attributes on every `IFlowError`

| Attribute | Type | Notes |
|---|---|---|
| `message` | str | One-line human description |
| `code` | str | Stable string code (see §7.4) |
| `request` | dict\|None | `{ method, url, endpoint }`; no headers, no body |
| `response_body_truncated` | str\|None | first 500 chars of the raw response body |
| `cause` | BaseException\|None | the underlying httpx exception, if any (set via `raise ... from ...` natively) |

### 7.3 HTTP status → exception mapping

| HTTP | When | Exception |
|---|---|---|
| 2xx + valid JSON + `success: true` | normal | (none; returns model) |
| 2xx + valid JSON + `success: false` | business error | dispatched via business code (§7.4) |
| 2xx + non-JSON body | server bug | `IFlowAPIError(status_code=200, code="api_invalid_json")` |
| 400 | bad params (rare; SDK usually catches client-side) | `IFlowValidationError(code="api_bad_request")` |
| 401 | invalid/missing key | `IFlowAuthError(code="api_unauthorized")` |
| 403 | key not allowed | `IFlowAuthError(code="api_forbidden")` |
| 429 | rate limited | `IFlowRateLimitError(code="api_rate_limited")` |
| 5xx | upstream | `IFlowAPIError(status_code=5xx, code="api_server_error")` |
| other 4xx | unexpected | `IFlowAPIError(status_code=4xx, code="api_http_error")` |
| `httpx.TimeoutException` | SDK-side timeout | `IFlowTimeoutError(code="network_timeout")` |
| `httpx.NetworkError`, ConnectError, etc. | network | `IFlowNetworkError(code="network_error")` |

### 7.4 Business code → exception mapping

| iFlow `code` | Exception |
|---|---|
| `"200"` | (success) |
| `"400"` | `IFlowValidationError(code="business_bad_request")` |
| `"40303"` | `IFlowRateLimitError(code="business_rate_limited")` |
| `"60400"` | `IFlowInsufficientCreditsError(code="business_insufficient_credits")` |
| `"90001"` | `IFlowBusinessError(code="business_fetch_failed", business_code="90001")` (web_fetch only) |
| `"90002"` | `IFlowBusinessError(code="business_no_results", business_code="90002")` (search only) |
| `"90402"` | `IFlowAuthError(code="business_invalid_api_key")` |
| `"500"` | `IFlowAPIError(code="business_server_error")` |
| any other | `IFlowBusinessError(code="business_unknown", business_code=<code>)` |

**Important:** when an HTTP status and business code disagree (e.g. HTTP 200 with `code: "40303"` body), trust the body. The JS SDK does this; the iFlow API's documented HTTP-status behavior is inconsistent.

### 7.5 Error-code strings are stable contract

The `code` attribute is the stable identifier consumers should switch on (especially MCP `structured_content.error.code`). Keep these strings backward-compatible across Python SDK versions.

### 7.6 Differences from JS error codes

| JS code (search-core) | Python equivalent | Why different |
|---|---|---|
| `missing_api_key` | `IFlowConfigError(code="missing_api_key")` | same wire-string |
| `missing_param` | `IFlowValidationError(code="missing_param")` | same |
| `invalid_param` | `IFlowValidationError(code="invalid_param")` | same |
| `network_timeout` | `IFlowTimeoutError(code="network_timeout")` | same |
| `network_error` | `IFlowNetworkError(code="network_error")` | same |
| `api_error` | `IFlowAPIError(code="api_*")` | refined into sub-types (`api_unauthorized`, `api_rate_limited`, etc.) |
| `api_business_error` | `IFlowBusinessError(code="business_*")` | refined per business code |

The JS `code` strings are kept as a stable subset; Python adds finer subcodes without breaking the prefix-based parse used by JS adapters.

---

## 8. Test Plan

All tests run **offline** by default. No real iFlow requests. No real key in any committed file.

### 8.1 Test matrix

| Layer | Test | Tool | What it asserts |
|---|---|---|---|
| Unit | `test_headers.py::test_required_headers_emitted` | direct call to `_attribution.build()` | five required header names + values |
| Unit | `test_headers.py::test_mcp_headers_conditional` | direct call | `IFlow-MCP-Client[-Version]` rules (both, name-only, orphan-version raises) |
| Unit | `test_headers.py::test_no_key_leakage` | inspect built headers and body for raw key substring | key never appears outside `Authorization` |
| Unit | `test_client_sync.py::test_web_search_payload_rename` | `respx` mock | request body is `{"keywords": "...", "num": ...}` (asserts `query→keywords`, `count→num`) |
| Unit | `test_client_sync.py::test_web_search_normalized_shape` | `respx` mock with canned response | output is `WebSearchResponse` with `url` (not `link`), correct types, `took_ms > 0` |
| Unit | `test_client_async.py::*` | async variants of all client tests | same assertions through `AsyncIFlowSearchClient` |
| Unit | `test_normalize.py::test_image_search_bare_array_data` | given a raw `data: []` payload | normalizer handles the documented inconsistency |
| Unit | `test_normalize.py::test_coercion_helpers` | bad/missing fields | normalizer never raises; produces None / "" defaults |
| Unit | `test_errors.py::test_http_status_to_exception` | parametrized: 401/403/429/500/502/200-non-json | correct exception class + `code` + `status_code` |
| Unit | `test_errors.py::test_business_code_to_exception` | parametrized over `40303`, `90402`, `60400`, `90001`, `90002`, `400`, unknown | correct exception class + `business_code` preserved |
| Unit | `test_errors.py::test_truncate_500_chars` | given a 50KB error body | `response_body_truncated` is exactly 500 chars |
| Unit | `test_errors.py::test_timeout_not_confused_with_cancel` | `respx.MockTransport` raises `TimeoutException` vs `CancelledError` | each maps to the right exception (this fixes the JS bug) |
| Unit | `test_config.py::test_env_var_reads` | `monkeypatch.setenv("IFLOW_API_KEY", "...")`, no explicit arg | client constructs successfully |
| Unit | `test_config.py::test_mcp_client_name_regex` | parametrized accept/reject list (mirror JS test list) | valid: `hermes`, `claude-code`, `host_2.0`, `x`; invalid: `Hermes`, `Claude Code`, `a b`, `>64 chars` |
| Unit | `test_config.py::test_mcp_client_version_regex` | parametrized | valid: `1.2.3-beta.4+build.5`; invalid: `1.0 beta`, `1.0/2`, `v 1` |
| Unit | `test_config.py::test_mcp_orphan_version_rejected` | version set without name | raises `IFlowConfigError` |
| Unit | `test_redact.py::test_redact_format` | various lengths | `<unset>`, `***`, `abcd***ab` |
| LangChain | `test_tools.py::test_three_tool_names_and_descriptions` | constructed tools | names: `iflow_web_search`, `iflow_image_search`, `iflow_web_fetch`; descriptions byte-identical to core constants |
| LangChain | `test_tools.py::test_tool_invoke_returns_content_and_artifact` | mocked client | content is human-readable summary, artifact is full Pydantic model |
| LangChain | `test_tools.py::test_attribution_headers` | `respx` mock | request sent with `IFlow-Source: langchain` (or `langchain-py`, see §10) and `IFlow-Integration: iflow-search-langchain` |
| LangChain | `test_tools.py::test_tool_error_raises` | mocked rate-limit response | tool raises (LangChain conventions) — not silent string |
| MCP | `test_mcp_config.py::*` | mirror search-mcp config tests | full env-var validation |
| MCP | `test_mcp_errors.py::test_no_throw_across_boundary` | tool handler raises Python exception | server returns `is_error=True` `CallToolResult` with `structured_content.error.code = "internal_error"` (matches JS) |
| MCP | `test_mcp_schema.py::test_tool_list_shape` | `list_tools()` | exact three tools, exact names, exact JSON Schema shapes |
| MCP | `test_mcp_stdout.py::test_no_stdout_pollution` | spawn `iflow-search-mcp` as subprocess with missing env | `stdout` is empty, `stderr` has `[iflow-search-mcp] ...`, exit code 1 |
| Smoke | `scripts/smoke_stdio.py` | spawn server with `IFLOW_BASE_URL` pointed at local `http.server` mock + Python MCP client SDK | full stdio handshake, `tools/list` returns three tools in order, `tools/call` returns structured content, fake-iFlow received POST with attribution headers including `IFlow-MCP-Client: smoke-host` and `IFlow-MCP-Client-Version: 9.9.9-smoke` |
| Smoke (opt-in) | `scripts/smoke_real_api.py` | requires `IFLOW_API_KEY` in env; **default skipped** | reads key from `os.environ` only, never writes to disk; one call per endpoint; pretty-prints |

### 8.2 Tooling choices

- `pytest` + `pytest-asyncio` (strict mode: `asyncio_mode = "strict"`)
- `respx` for `httpx` mocking (much cleaner than monkeypatching)
- `pytest.raises(IFlowAuthError, match=r"...")` for exception assertions
- Test fixtures live in `tests/fixtures/` as small Python literals — fabricated (mirroring JS approach), small enough to inspect, designed to exercise normalizer edge cases
- `conftest.py` exposes a `respx_mock_iflow` fixture that pre-registers stub routes for the three endpoints

### 8.3 Coverage targets

The JS side does not enforce a numeric coverage target. The Python port shouldn't either — coverage is a proxy. The real gates are: every error path tested, every header tested for emission and absence, every business code mapped, the no-stdout-pollution test green, the smoke script green.

---

## 9. Release Plan

### 9.1 Versioning

- Initial release: **`0.1.0a0`** (PEP 440 prerelease).
- `pip install iflow-search` returns "no matching distribution" until a non-prerelease lands. Users must `pip install --pre iflow-search`. This is the deliberate analog of the JS `next` dist-tag — same end-user surface.
- All sibling packages publish in lock-step at the same prerelease version initially.
- Once two real MCP clients are smoked end-to-end (Claude Code + Claude Desktop is the JS-doc-recommended pair), bump to `0.1.0` proper.
- **Never** convert a prerelease to a stable release by republishing under a new version name — PyPI does not allow re-uploading the same version, so each promotion is a fresh `0.1.0` after the `0.1.0a*` series.

### 9.2 PyPI publish pre-flight (mirror of JS pre-publish gate)

```
# Mandatory checklist before any uv publish / twine upload
[ ] git status clean on main
[ ] HEAD pushed; latest GitHub Actions run green
[ ] uv lock --check  (or pip-compile --check)
[ ] uv build  →  dist/iflow_search-*.whl and dist/iflow_search-*.tar.gz produced
[ ] ruff check .   →  no findings
[ ] mypy src/      →  no findings
[ ] pytest         →  green
[ ] python scripts/smoke_stdio.py  →  green (for the MCP package)
[ ] secret scan over git diff and working tree (regex: sk-[A-Za-z0-9]{20,}, IFLOW_API_KEY=, etc.)  →  no matches
[ ] inspect sdist:  tar tf dist/iflow_search-*.tar.gz
    must contain: pyproject.toml, src/, README.md, LICENSE
    must NOT contain: .env, __pycache__/, .pytest_cache/, scripts/, tests/ (sdist may include, depending on policy — be explicit)
[ ] inspect wheel:  unzip -l dist/iflow_search-*.whl
    must contain: iflow_search/*.py, iflow_search-*.dist-info/{METADATA,RECORD,WHEEL}
    must NOT contain: tests/, scripts/, .env
[ ] inspect wheel METADATA: dependency on sibling packages is concrete (e.g. iflow-search>=0.1.0a0,<0.2), not path or git URL
[ ] twine check dist/*  →  PASSED for each artifact
[ ] uv publish --dry-run  OR  twine upload --repository testpypi dist/*  →  cleanly uploaded to TestPyPI
[ ] cold-install smoke from /tmp:
    cd /tmp && python -m venv v && source v/bin/activate
    pip install --pre --index-url https://test.pypi.org/simple/ iflow-search
    python -c "from iflow_search import IFlowSearchClient; print(IFlowSearchClient.__doc__)"
```

### 9.3 Publishing order

`iflow-search` (core) must publish before `iflow-search-langchain` or `iflow-search-mcp`, because the latter two pin a concrete version of core that must already resolve on PyPI.

```
1. bump version in all three pyproject.toml (single chore commit)
2. uv build / twine upload core
3. pip index versions iflow-search   # confirm new version surfaced
4. uv build / twine upload langchain
5. uv build / twine upload mcp
6. cold-install smoke from /tmp for each package
```

### 9.4 Secret-leak protocol

Same as JS: rotate the key at iFlow's portal first, *then* yank the PyPI release (`pypi project yank ...`), *then* publish a fix. **Never delete-and-republish** — PyPI doesn't permit it.

### 9.5 GitHub Actions

Build + lint + typecheck + test only. **Never `twine upload` from CI.** Mirror the JS `.github/workflows/ci.yml` shape. A separate `release.yml` can exist but should only build artifacts (no upload step); the human runs the upload locally with a token in their shell.

### 9.6 README required content (per package)

- Install command (`pip install --pre iflow-search`).
- One worked example per public method.
- Attribution-header behavior summary.
- Env-var summary (`IFLOW_API_KEY`).
- Link to API docs.
- License (MIT).
- Explicit "do not commit your API key" note.

### 9.7 Examples directory

- `examples/quickstart.py` — sync core
- `examples/quickstart_async.py` — async core
- `examples/langchain_simple.py` — `@tool` decorator
- `examples/langgraph_agent.py` — mirrors JS `langgraph-agent` example, `create_react_agent` wiring
- `examples/mcp_client_configs/` — `.mcp.json`, `~/.iflow/settings.json`, `~/.hermes/config.yaml` snippets
- `examples/fastapi_openapi/` — FastAPI server (deferred to P3)

---

## 10. Open Questions (need human decisions, do NOT guess)

1. **PyPI distribution name.** Confirm `iflow-search` is acceptable and not already taken. Check `pip index versions iflow-search` and `pip index versions iflow-search-core` before committing.
2. **`IFlow-Source` for Python LangChain.** Use `langchain` (matches JS, unified backend slice) or `langchain-py` (differentiates Python for ops dashboards)? Recommendation: **`langchain`**, with the language identifiable from `IFlow-Integration` (= `iflow-search-langchain`) and `User-Agent`. Confirm with whoever owns iFlow's request-attribution dashboards.
3. **Max `num` value.** JS clamps to 20 client-side. Is 20 the actual server-side maximum? If the server accepts higher values, the SDK should not artificially cap them.
4. **Default `num`.** Docs say 10, skill CLI uses 15, server-default-when-omitted unconfirmed. The SDK should probably *not* set a default and let the server decide — but verify the server doesn't 400 on omission.
5. **Markdown response format.** Docs say `Accept: text/markdown` is the default. If true, the server may be returning Markdown by default to clients that don't set `Accept`. Confirm via a one-shot test that JSON is what's returned when we send `Accept: application/json` (it is, per the skill scripts).
6. **HTTP status alignment.** Need a single empirical test sweep: hit each error condition (bad key, no credits, rate limit hit, 90002 search-no-results, 90001 fetch-fail) and capture the actual HTTP status for each. Until we do, the Python SDK should trust the body code and treat HTTP status as a fallback.
7. **Whether `request_id` is returned by iFlow.** Neither the docs nor JS SDK capture a request-id. If iFlow does set a header like `X-Request-Id` on responses, the Python SDK should capture it and put it on every exception for support debugging. One test request will answer this.
8. **CrewAI strategy.** Defer or ship now? JS docs reject preemptive packages — recommend defer until at least one user asks. Confirm.
9. **iFlow CLI sunset.** Today is 2026-05-21, the announced sunset was 2026-04-17. Has it actually shut down? If so, drop iFlow CLI from the integration matrix; if it was extended, document new dates.
10. **OpenClaw authority.** The general-purpose agent could not find authoritative primary sources for OpenClaw and the web is flooded with apparently-fabricated SEO content. Before any OpenClaw integration commits, someone with first-party knowledge needs to confirm what OpenClaw actually is, who runs it, and whether it's worth investing in.
11. **Repository layout.** One monorepo (`iflow-search-py/` with three subpackages, mirroring JS) or three separate repos? The JS side is one monorepo and that has worked. Recommendation: one monorepo, `uv` workspaces. Confirm.
12. **Build backend.** `hatchling` is recommended above. `uv_build` is also viable as of 2025. Pick one for consistency before scaffolding.
13. **mypy vs pyright.** Pick one. Mypy has broader plugin ecosystem; pyright is faster and more accurate. Recommendation: **mypy** for compatibility with the LangChain ecosystem's own typing.
14. **Author / publisher identity on PyPI.** Should the PyPI `author` be the legal entity "杭州星辰千寻科技有限公司 / Hangzhou Xingchen Qianxun Technology Co., Ltd." matching the JS upstream-issue identity, or an individual? Confirm.

---

## 11. Proposed Next Implementation Prompt

> *Below is a drop-in prompt for the next Claude Code session that should implement the MVP. **Do not execute it now.** Treat it as the deliverable artifact for a future session.*

```
You are implementing the MVP of the `iflow-search` Python core SDK. Read the research report
at iflow-search-py/RESEARCH.md before writing any code. Do not deviate from its decisions
without flagging them as additional Open Questions.

Scope of this session (MVP — `iflow-search` core package ONLY; not the LangChain adapter,
not the MCP server):

In scope:
- pyproject.toml using hatchling, requires-python >=3.10
- src/iflow_search/ with: __init__.py, _version.py, client.py, async_client.py,
  _http.py, _attribution.py, config.py, errors.py, models.py, _normalize.py, _redact.py
- Pydantic v2 models for WebSearchResponse / ImageSearchResponse / WebFetchResponse
  and their nested types (snake_case Python fields; alias to wire names where they differ:
  link→url, refUrl→source_url, fromCache→from_cache, tookMs→took_ms)
- Sync IFlowSearchClient and async AsyncIFlowSearchClient with three methods each:
  web_search(query, count=None), image_search(query, count=None), web_fetch(url)
- Exception hierarchy per research report §7, including refined sub-types
- Attribution header builder mirroring JS `headers.ts` rules exactly:
  always: IFlow-Source, IFlow-Integration, IFlow-Integration-Version, User-Agent
  conditional: IFlow-MCP-Client[-Version] (both, or name-only; orphan version raises)
- IFLOW_API_KEY env-var fallback in core (depart from JS here intentionally; document)
- DEFAULT_BASE_URL = "https://platform.iflow.cn"
- DEFAULT_TIMEOUT_S = 30.0
- WEB_SEARCH_MAX_COUNT = 20, IMAGE_SEARCH_MAX_COUNT = 20 (per JS; flag as Open Question 3)
- Body truncation constant MAX_ERROR_BODY_BYTES = 500
- tests/ matching the matrix in research report §8 for the core layer only:
  test_headers, test_client_sync, test_client_async, test_errors, test_normalize,
  test_config (the parts that apply to core: env reads, validation), test_redact
- conftest.py with a respx_mock_iflow fixture
- README.md (research report §9.6 content)
- LICENSE (MIT, identical to JS repo)
- .github/workflows/ci.yml that runs ruff + mypy + pytest on push to PRs to main
  (no publish steps)

Out of scope this session (defer to follow-up sessions):
- iflow-search-langchain package
- iflow-search-mcp package
- iflow-search-openapi package
- Smoke scripts that spawn real iFlow API
- PyPI upload
- Version bumps beyond initial 0.1.0a0

Hard rules (non-negotiable):
- All HTTP and header construction lives in core. No other code touches httpx.
- Use httpx for both sync and async — do not run sync via threadpool from async paths.
- Pydantic v2 models. Do not introduce dataclasses for shapes that cross the network.
- Pydantic v2 strict-mode validation on inputs.
- Cancellation (asyncio.CancelledError) propagates; only SDK-initiated timeouts become
  IFlowTimeoutError.
- Never write a real API key to any tracked file. Test fixtures use 'test-key-redacted'.
- Do not bump the version beyond 0.1.0a0 this session.
- Do not run `twine upload`, `uv publish`, or any registry-mutating command.
- Do not modify any file under iflow-search-js/.
- Before committing, run: ruff check . && mypy src/ && pytest. All must pass.

When done:
1. Show the final pyproject.toml.
2. Show the test summary (count, all green).
3. Mark the implementation as complete; do not publish.
4. List anything you encountered that contradicts the research report so we can update it.

Reference (read first):
- The research report committed to this repo.
- /Users/lzy/Documents/iFlow-search-api/iflow-search-js/packages/search-core/src/*.ts
  for source-of-truth behavior. The Python port mirrors behavior, not API surface.
```

---

**End of report.** This is research output only — no Python files created, no version moved, no key touched, no commits made. Ready for human review and the open questions in §10 before any implementation session begins.
