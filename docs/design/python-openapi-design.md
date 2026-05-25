# `iflow-search-openapi` — Python OpenAPI adapter design

Companion design document for the **`iflow-search-openapi`** package: an HTTP/OpenAPI 3.1 tool server for the iFlow Search API, intended for use by Open WebUI, Coze, and other platforms that consume an OpenAPI 3.x document as a tool catalogue. Sibling to `iflow-search` (the core SDK, see `python-sdk-design.md`), `iflow-search-mcp` (MCP stdio server, see `python-mcp-design.md`), and `iflow-search-langchain` (LangChain tools, see `python-langchain-design.md`). This document covers v0.1.0a0.

The package wraps the core's `AsyncIFlowSearchClient` in three POST tool endpoints (`iflow_web_search`, `iflow_image_search`, `iflow_web_fetch`) plus a small set of operational routes. It introduces no new HTTP, attribution, or error-handling logic — every architectural invariant of the core SDK applies unchanged.

## 1. Scope

In scope for v0.1.0a0:

- HTTP server (single ASGI app) exposing:
  - `GET /health`
  - `GET /openapi.json`
  - `POST /tools/iflow_web_search`
  - `POST /tools/iflow_image_search`
  - `POST /tools/iflow_web_fetch`
- OpenAPI 3.1 schema served at `/openapi.json`, generated from the same Pydantic args models the routes validate against — single source of truth, no drift.
- Bearer-token auth gate for external callers (`IFLOW_OPENAPI_AUTH_TOKEN`), constant-time compare, with `/health` always exempt.
- Opt-in CORS for browser-side tool importers, with preflight short-circuit before the auth gate.
- Console script `iflow-search-openapi`. Env-only configuration.
- Offline tests via `httpx.ASGITransport` + `httpx.MockTransport` for the upstream client.
- Opt-in real-API smoke (`IFLOW_OPENAPI_SMOKE=1`).

Out of scope for v0.1.0a0:

- TLS termination. Operators put a reverse proxy in front.
- Per-platform packages (no `iflow-search-open-webui`, no `iflow-search-coze`). One generic OpenAPI server covers them all by design — confirmed approach in the user's brief.
- Streaming responses / SSE / WebSocket.
- Multi-tenant hosting; per-request API-key override.
- Bundled prompts, resources, or non-search tools.
- A `.env` loader, a CLI flag for the credential, a config file, or any non-env credential source.
- Reading or referencing `DEEPSEEK_API_KEY` (or any other unrelated provider key) anywhere in this package.
- A public Python embedding API (`create_app()` re-export). MVP keeps internals private; see §11.

## 2. Distribution

| Attribute | Value |
|---|---|
| PyPI name | `iflow-search-openapi` |
| Module name | `iflow_search_openapi` |
| Version (initial) | `0.1.0a0` (PEP 440 prerelease — requires `pip install --pre`) |
| Console script | `iflow-search-openapi` |
| License | MIT |

Naming convention matches `iflow-search`, `iflow-search-mcp`, `iflow-search-langchain`. The `iflow-search-*` family is the convention for adapters originating in this repository.

## 3. Python version and runtime dependencies

```toml
[project]
requires-python = ">=3.10"
dependencies = [
    "iflow-search>=0.1.0a0,<0.2",
    "fastapi>=0.115,<1.0",
    "uvicorn>=0.30,<1.0",
    "pydantic>=2.7,<3.0",
]
```

- `requires-python = ">=3.10"` — same floor as the core and the other adapters.
- `iflow-search>=0.1.0a0,<0.2` — only sanctioned path to the iFlow API. The adapter never imports `httpx` directly; the core already owns HTTP/auth/attribution.
- `fastapi>=0.115,<1.0` — chosen for OpenAPI 3.1 generation from Pydantic models and ergonomic dependency injection. See §4 for the framework comparison.
- `uvicorn>=0.30,<1.0` — **plain `uvicorn`, not `uvicorn[standard]`**. The `[standard]` extra pulls in `python-dotenv` (which conflicts with our env-only credential rule), `watchfiles`, `websockets`, `httptools` (C ext), and `uvloop` (C ext on non-Windows). None are required for an MVP that does not stream, does not reload, does not parse `.env`, and is throughput-bound by the upstream API rather than by request parsing.
- `pydantic>=2.7,<3.0` — explicit even though FastAPI requires it, because the adapter defines its own request-args models and tests assert their constraints directly.

The adapter does **not** depend on `langchain`, `mcp`, or any platform-specific SDK. It depends on the core only.

Dev/test dependencies include `httpx` explicitly so tests can use `httpx.ASGITransport` and `httpx.MockTransport` without relying on a transitive dependency:

```toml
[project.optional-dependencies]
dev = [
    "pytest>=8",
    "pytest-asyncio>=0.23",
    "httpx>=0.27,<1.0",
    "ruff>=0.4",
    "mypy>=1.10",
    "tomli>=2.0; python_version<'3.11'",
]
```

The `tomli` backport is included for the `tests/test_version.py` self-check on Python 3.10, mirroring the precedent set by `iflow-search-langchain` after CI uncovered the missing-on-3.10 `tomllib` issue.

## 4. Framework choice — FastAPI

### 4.1 Comparison

| Criterion | FastAPI | Starlette (hand-rolled OpenAPI) | Flask | Plain ASGI |
|---|---|---|---|---|
| OpenAPI schema quality | excellent (3.1, derived from Pydantic v2) | manual; must mirror Pydantic shape by hand | none built-in; need flask-openapi3 / apispec | none; full DIY |
| Startup simplicity | one line: `uvicorn.run(app, host=..., port=...)` | same | sync only; needs WSGI server | hand-rolled router |
| Dep footprint (wheel) | `fastapi` ~90KB, `starlette` ~600KB, `uvicorn` plain ~250KB | `starlette` ~600KB, `uvicorn` plain ~250KB | `flask` ~100KB, `werkzeug` ~250KB, but no async client path | nothing, but high LOC |
| CORS | Starlette `CORSMiddleware` | Starlette `CORSMiddleware` | flask-cors | DIY |
| Bearer auth | dependency-injectable `Depends(...)` | hand-rolled | `before_request` | DIY |
| Test ergonomics | `httpx.ASGITransport(app=app)` directly | same | `flask.testing.FlaskClient`; different mental model | DIY |
| Async upstream call | native | native | requires running async core in a thread → deadlock risk per core invariant §2 | native |
| Wheel size impact (sum) | ~940KB | ~850KB | ~350KB (but Flask is sync) | ~0KB (but high LOC) |

### 4.2 Recommendation: **FastAPI**

Rationale:

1. **OpenAPI is the product surface.** Open WebUI and Coze ingest `/openapi.json` to populate their tool catalogues. FastAPI deriving the schema from the same Pydantic models the routes use means request-validation and the schema can never drift. The JS sibling (`@iflow-ai/search-openapi`) hand-rolls its OpenAPI doc and explicitly calls out that the handler list is "the single source of truth for both the routes and `/openapi.json`" — FastAPI achieves the same invariant with one fewer file.
2. **The async client path is mandatory.** Per the core's design (§6.2), running the sync client inside a thread pool to satisfy an async caller deadlocks under FastAPI/asyncio. Flask is out for this reason alone — its sync surface would force exactly the deadlock-prone pattern the core warns against. FastAPI (or any ASGI framework) lets us call `AsyncIFlowSearchClient` directly in handlers.
3. **Dep footprint is acceptable.** ~940KB of installed code is small relative to typical container images and to the value provided. Plain `uvicorn` (not `[standard]`) keeps the install pure-Python and avoids the `.env` auto-loader that would silently violate our env-only-credential rule.
4. **Tests are ergonomic.** `httpx.ASGITransport(app=fastapi_app)` is a one-liner, matches the rest of this repo's test style (everything is `httpx`-based), and exercises the real ASGI lifecycle.
5. **Recognisability.** Operators encountering this server in a stack trace will recognise FastAPI and uvicorn instantly. Starlette + hand-rolled OpenAPI works, but is less ergonomic to operate.

### 4.3 What we don't take from FastAPI

- No `FastAPI(docs_url="/docs", redoc_url="/redoc")` browsers. Both are disabled. Open WebUI and Coze read `/openapi.json` directly; serving Swagger UI from this process bloats the image and creates a soft form of UI we don't want to support across LTS.
- No `fastapi-cli`, no `fastapi[standard]` extras. The package ships its own `iflow-search-openapi` console script via the project scripts entry; the user-facing CLI is ours, not FastAPI's.
- No FastAPI exception-handler decorators that pretty-print HTML. All errors go through `_errors.py` and produce the uniform JSON envelope (§8).
- No automatic API versioning at the route level. The package's own `__version__` is reported in the OpenAPI `info.version` and in `/health`.

## 5. Package layout

```
packages/iflow-search-openapi/
├── README.md                  # PyPI long_description
├── LICENSE                    # MIT
├── pyproject.toml
├── src/
│   └── iflow_search_openapi/
│       ├── __init__.py        # exports __version__ only
│       ├── _version.py        # __version__ = "0.1.0a0"
│       ├── _constants.py      # SOURCE = "openapi", INTEGRATION_NAME = "iflow-search-openapi"
│       ├── _config.py         # load_config(env) -> ResolvedConfig; ConfigError
│       ├── _schemas.py        # WebSearchBody / ImageSearchBody / WebFetchBody / SuccessEnvelope / ErrorEnvelope
│       ├── _errors.py         # iflow_error_to_envelope, status_for_iflow_error
│       ├── _auth.py           # bearer_required dependency; constant-time compare
│       ├── _cors.py           # CORS middleware factory (Starlette CORSMiddleware wrapper)
│       ├── _openapi.py        # customise FastAPI.openapi (title, version, info, security)
│       ├── _routes.py         # APIRouter wiring health + tools
│       ├── _app.py            # build_app(client, config) -> FastAPI
│       └── _bin.py            # main() — CLI entry; loads config, builds app, runs uvicorn
├── tests/
│   ├── conftest.py
│   ├── test_version.py
│   ├── test_config.py
│   ├── test_auth.py
│   ├── test_cors.py
│   ├── test_openapi_schema.py
│   ├── test_health.py
│   ├── test_tools_success.py
│   ├── test_tools_errors.py
│   ├── test_tools_input_validation.py
│   ├── test_attribution.py
│   ├── test_no_key_leakage.py
│   ├── test_stdout_purity.py
│   └── test_import_purity.py
└── scripts/
    └── smoke_real_api.py      # opt-in via IFLOW_OPENAPI_SMOKE=1
```

All non-public modules are underscore-prefixed. The only supported import is `from iflow_search_openapi import __version__`; the user-facing surface is the CLI.

## 6. Endpoints

### 6.1 Route table

| Method | Path | Auth | CORS preflight | Description |
|---|---|---|---|---|
| GET | `/health` | never | n/a | Liveness probe |
| GET | `/openapi.json` | bearer when configured | yes | OpenAPI 3.1 schema |
| POST | `/tools/iflow_web_search` | bearer when configured | yes | web search |
| POST | `/tools/iflow_image_search` | bearer when configured | yes | image search |
| POST | `/tools/iflow_web_fetch` | bearer when configured | yes | web fetch |

### 6.2 Request bodies (Pydantic v2 models, `extra="forbid"`)

```python
class WebSearchBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    query: str = Field(min_length=1, description="Search query.")
    count: int | None = Field(default=None, ge=1, description="Number of results.")

class ImageSearchBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    query: str = Field(min_length=1, description="Image search query.")
    count: int | None = Field(default=None, ge=1, description="Number of images.")

class WebFetchBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    url: str = Field(min_length=1, description="Absolute URL of the page to fetch.")
```

Notes:
- Field names (`query`, `count`, `url`) match the Python core's public surface and the LangChain adapter's args schemas — cross-adapter prompt parity.
- `count` is **deliberately unbounded above**. The core does not clamp it (`python-sdk-design.md` §6.3); the MCP adapter likewise omits `maximum` from its tool schemas (`python-mcp-design.md` §7.4). The JS sibling sets a per-endpoint `maximum` from `WEB_SEARCH_MAX_COUNT`; the Python core does not export such a constant, and adding one here would advertise a constraint the SDK does not enforce. We follow the Python-core invariant.
- `extra="forbid"` ⇒ unknown fields → HTTP 400, matches MCP's `additionalProperties: false`.
- The body is the entire request; query/path params are not used.

### 6.3 Wire format inside the adapter

The adapter passes `query`/`count`/`url` straight into the core client. The core rewrites them to wire names (`keywords`/`num`/`url`) per `python-sdk-design.md` §5. The adapter does not touch wire names.

### 6.4 Body size cap

A 1 MiB cap is enforced via a Starlette middleware that inspects `Content-Length` (when present) and short-circuits to HTTP 413 if exceeded. For chunked uploads without `Content-Length`, the cap is enforced inside the body-read accumulator. This matches the JS sibling's `MAX_BODY_BYTES = 1 * 1024 * 1024`. None of our endpoints take large bodies; the cap exists to keep tool platforms from accidentally streaming megabytes into the server.

## 7. Auth design

### 7.1 Two distinct credentials

| Credential | Direction | Source |
|---|---|---|
| `IFLOW_API_KEY` | this server → iFlow API | env, required |
| `IFLOW_OPENAPI_AUTH_TOKEN` | external client → this server | env, optional |

The two are never conflated. `IFLOW_API_KEY` is read once at startup, handed to the core constructor, and never appears in any response body, log line, error envelope, OpenAPI schema, or banner. `IFLOW_OPENAPI_AUTH_TOKEN` lives only in the bearer-check closure; it is similarly never echoed.

### 7.2 Open mode (`IFLOW_OPENAPI_AUTH_TOKEN` unset)

All routes accessible without an `Authorization` header. Intended for local development behind a private network, or when an upstream reverse proxy enforces its own auth.

### 7.3 Closed mode (`IFLOW_OPENAPI_AUTH_TOKEN` set)

Every route **except** `/health` requires `Authorization: Bearer <token>`. Specifically:

- `/health` — always open. Liveness probes must succeed for k8s/Docker readiness checks; gating them defeats the purpose.
- `/openapi.json` — gated. The OpenAPI document reveals that this server is an iFlow proxy and lists the supported tools; in closed mode operators want that surface hidden behind the same bearer.
- `/tools/*` — gated.

Bearer parsing:
- `^Bearer\s+(.+)$` case-insensitive on the header
- trim whitespace from both header and extracted token
- empty extracted token → 401
- comparison via `hmac.compare_digest(provided.encode(), expected.encode())`

The comparison is constant-time. When lengths differ, the implementation still performs a `compare_digest` against a same-length zero buffer to avoid leaking length differences via timing — matches the JS sibling's `safeEqual` pattern.

Failure response (uniform with all other errors):

```json
{
  "ok": false,
  "error": {
    "code": "unauthorized",
    "message": "Missing Authorization header. Send \"Authorization: Bearer <token>\"."
  }
}
```

(Status 401. Other messages for malformed / empty / wrong token, but always `code: "unauthorized"`.)

### 7.4 OpenAPI schema reflects the auth mode

When `IFLOW_OPENAPI_AUTH_TOKEN` is set, `/openapi.json` declares a `BearerAuth` security scheme and applies it to every operation that requires it:

```json
{
  "components": {
    "securitySchemes": {
      "BearerAuth": { "type": "http", "scheme": "bearer" }
    }
  },
  "security": [{ "BearerAuth": [] }]
}
```

When unset, no `securitySchemes` or top-level `security` is emitted. Open WebUI and Coze read this to prompt the user for a token when importing the schema.

### 7.5 What `IFLOW_API_KEY` never touches

| Surface | Containment |
|---|---|
| OpenAPI schema | The key is not a request parameter; FastAPI does not see it |
| Response bodies (success or error) | `_errors.py` constructs envelopes from `IFlowError.code`/`.message`/etc. only; the key is not on the exception object |
| Startup banner | Only the *mode* is printed: "bearer auth ENABLED" / "DISABLED"; never the value |
| Per-request logs | No per-request logs in MVP (§10) |
| `__repr__` of any in-process object | The core's client already redacts in `__repr__`; the adapter does not stringify it |
| Filesystem | The adapter never writes; `os.environ[...]` is the only read path |

## 8. Response and error envelopes

### 8.1 Success

```json
{
  "ok": true,
  "data": { ... }
}
```

`data` is the core's Pydantic response model serialised via `model_dump(mode="json", by_alias=False, exclude={"raw"})`. Field names are **snake_case** (same rationale as MCP `structuredContent`, `python-mcp-design.md` §13.1).

`raw` is excluded by default — see §13.2 for the rationale and the open question.

### 8.2 Error

```json
{
  "ok": false,
  "error": {
    "code": "<stable string from IFlowError.code>",
    "message": "<human-readable>",
    "type": "<exception class name, optional>",
    "status_code": <int, optional>,
    "business_code": "<string, optional>",
    "response_body_truncated": "<string, optional>"
  }
}
```

- `code` is the **stable contract** — consumers switch on it (`python-sdk-design.md` §8.5). Codes are produced by the core; the adapter never invents new ones for `IFlowError` cases. Codes the adapter introduces (auth, payload, routing) are listed in §8.4.
- `message` comes from `IFlowError.message`.
- `type` (optional) is the unqualified class name (`IFlowAuthError`, `IFlowRateLimitError`, ...) for human triage. It is supplementary; consumers should not switch on it.
- `status_code` / `business_code` / `response_body_truncated` appear only when the underlying `IFlowError` carries them, matching the MCP adapter's `structuredContent.error` shape.

### 8.3 HTTP status mapping

The body is the source of truth, but the HTTP status is **also** signalled (4xx/5xx, not "200 + ok:false"). Rationale:

- Open WebUI and Coze use HTTP status for retry/backoff decisions; a 200 response on a rate-limit error would mask that signal.
- The JS sibling does the same (`statusForIFlowError` in `errors.ts`).
- The body envelope is uniform across success and error, so consumers that ignore status get a consistent shape; consumers that inspect status get the semantic.

| `IFlowError.code` | HTTP | Notes |
|---|---|---|
| `api_unauthorized` | 401 | iFlow returned 401 |
| `api_forbidden` | 403 | iFlow returned 403 |
| `business_invalid_api_key` | 401 | iFlow returned 200 + business code 90402 |
| `api_bad_request` | 400 | iFlow returned 400 |
| `business_bad_request` | 400 | iFlow returned 200 + business code 400 |
| `api_rate_limited` | 429 | |
| `business_rate_limited` | 429 | |
| `business_insufficient_credits` | 402 | Payment Required — semantically accurate |
| `business_fetch_failed` | 502 | upstream parse failure |
| `business_no_results` | 200 + `ok: true` + empty data | "no hits" is a valid search outcome, not a server error — see §13.1 |
| `api_server_error` | 502 | |
| `business_server_error` | 502 | |
| `api_invalid_json` | 502 | upstream returned non-JSON 2xx |
| `business_unknown` | 502 | |
| `network_timeout` | 504 | |
| `network_error` | 502 | |
| `IFlowValidationError` (client input) | 400 | code typically `validation_*` |
| `IFlowConfigError` | (fatal at startup, never reaches request layer) | exit 1 |

For any unmapped `IFlowError` subclass that appears in a future core release, the default is **HTTP 502** with the core's `code` preserved verbatim. This keeps unknown errors visible without crashing.

### 8.4 Codes the adapter introduces (not from `IFlowError`)

| `code` | HTTP | Trigger |
|---|---|---|
| `unauthorized` | 401 | bearer missing / malformed / wrong |
| `method_not_allowed` | 405 | non-POST to a `/tools/*` path |
| `not_found` | 404 | unknown path |
| `invalid_input` | 400 | body is not a JSON object; FastAPI validation errors are re-shaped to this |
| `payload_too_large` | 413 | body exceeds 1 MiB |
| `internal_error` | 500 | unhandled Python exception inside the route (defensive fallback; should never fire) |

`asyncio.CancelledError` is **never caught**, matching the core invariant (`python-sdk-design.md` §8.1). The catch-all handler explicitly excludes it via `except IFlowError` / `except Exception` (not `BaseException`).

### 8.5 FastAPI's default validation errors are re-shaped

FastAPI emits HTTP 422 with `{"detail": [...]}` for Pydantic validation failures. The adapter overrides `RequestValidationError` and `HTTPException` handlers to produce the uniform envelope (`{"ok": false, "error": {...}}`) with HTTP 400 and `code: "invalid_input"`. The Pydantic error list is passed through as `error.detail` (a structured array) so consumers can still inspect per-field failures.

## 9. CORS design

### 9.1 Modes

| `IFLOW_OPENAPI_CORS_ORIGIN` | Behaviour |
|---|---|
| unset | no CORS headers on any response; server is intended for same-origin or server-to-server use |
| `*` | wildcard allow-origin |
| `http(s)://host[:port]` | exact-origin allow |

### 9.2 Validation

At startup, the value is matched against `^(\*|https?://[A-Za-z0-9.-]{1,253}(?::[0-9]{1,5})?)$`. Anything with a path, query, fragment, or non-printable character is rejected with `ConfigError` and the process exits 1 before binding the socket. This matches the JS sibling's validation verbatim and keeps header-injection-via-config out of the response surface.

### 9.3 Allowed headers

`Access-Control-Allow-Headers: Content-Type, Authorization, X-Session-Id`

`X-Session-Id` is listed explicitly because Open WebUI is observed to send it on tool-call requests from the browser. Not listing it would cause silent preflight rejection in browsers under certain Open WebUI versions. The adapter does not **read** `X-Session-Id` — it just declares it allowed for the preflight.

### 9.4 Allowed methods

`Access-Control-Allow-Methods: GET, POST, OPTIONS`

### 9.5 Preflight short-circuits before the auth gate

Browser preflights do not carry the `Authorization` header. If the CORS middleware ran behind the auth dependency, every preflight would 401 and break tool import. The middleware order is therefore:

1. CORS middleware (set headers + answer `OPTIONS` preflight before auth; Starlette's `CORSMiddleware` responds 200 with the `Access-Control-Allow-*` reply — either 200 or 204 is spec-compliant)
2. Body-size middleware
3. Bearer auth dependency on routes

Implementation: Starlette's built-in `CORSMiddleware` is wired with the validated origin. Custom middleware enforces the body-size cap (Starlette's built-in is not granular enough for our needs).

## 10. Attribution

The adapter never constructs `Authorization`, `IFlow-*`, or `User-Agent` headers. It builds an `AsyncIFlowSearchClient` with constructor arguments only, and the core does the rest:

```python
client = AsyncIFlowSearchClient(
    api_key=config.api_key,
    base_url=config.base_url,
    timeout=config.timeout_s,
    source=SOURCE,                       # "openapi"
    integration_name=INTEGRATION_NAME,   # "iflow-search-openapi"
    integration_version=__version__,
)
```

Resulting headers on every outbound request to iFlow:

| Header | Value |
|---|---|
| `Authorization` | `Bearer <IFLOW_API_KEY>` (from core) |
| `IFlow-Source` | `openapi` |
| `IFlow-Integration` | `iflow-search-openapi` |
| `IFlow-Integration-Version` | adapter `__version__` |
| `User-Agent` | `iflow-search-openapi/<version>` (derived by core) |

The adapter **never** forwards `IFLOW_OPENAPI_CLIENT` (or any other value) as `IFlow-MCP-Client` / `IFlow-MCP-Client-Version`. Those headers are reserved for MCP transports. Reusing them from a non-MCP transport would muddy iFlow's per-host analytics — explicit reasoning carried over from the JS sibling's `bin.ts` comment.

`IFLOW_OPENAPI_CLIENT` is captured into `ResolvedConfig.client_name` for **banner display only** (e.g. `[iflow-search-openapi] v0.1.0a0 listening on http://127.0.0.1:8787 — bearer auth ENABLED client=open-webui`). It does not become a wire header in this release. If, in the future, iFlow exposes a non-MCP "host platform" header, it can be wired in without changing config semantics.

`DEEPSEEK_API_KEY` is **not read** anywhere in this package. The adapter has no dependency on, no env reference to, and no test against that variable.

## 11. Public Python surface

```python
from iflow_search_openapi import __version__
```

That is the supported import API in MVP. The user-facing surface is the CLI:

```
iflow-search-openapi
```

invoked with `IFLOW_API_KEY` (and any optional vars from §12) in the process env.

`_app.build_app(...)`, the route module, the auth module, and the error mappers are all underscore-prefixed and not part of the compatibility contract. Importing them at your own risk is permitted; relying on their stability is not. This mirrors the MCP adapter's stance (`python-mcp-design.md` §10.2).

Concrete reason for *not* exporting `build_app` in MVP: the JS sibling's programmatic API (`createApp({ client, authToken, corsOrigin })`) accumulated several optional knobs over its life. Locking that shape into a public Python contract before any real Python user requests it would over-commit. A concrete request will trigger a deliberate API design (with `pydantic` model for options) rather than a leaky underscore export.

## 12. Environment configuration

| Variable | Required | Default | Validation | Forwarded as |
|---|---|---|---|---|
| `IFLOW_API_KEY` | yes | — | non-empty after strip | core constructor `api_key=` |
| `IFLOW_BASE_URL` | no | core default | non-empty after strip | core `base_url=` |
| `IFLOW_TIMEOUT_MS` | no | core default (30000 ms) | positive integer; ms → float seconds at boundary | core `timeout=` |
| `IFLOW_OPENAPI_HOST` | no | `127.0.0.1` | IPv4/IPv6/hostname; non-empty after strip | uvicorn `host=` |
| `IFLOW_OPENAPI_PORT` | no | `8787` | integer in `[0, 65535]` | uvicorn `port=` |
| `IFLOW_OPENAPI_AUTH_TOKEN` | no | unset (open mode) | non-empty after strip | auth dependency |
| `IFLOW_OPENAPI_CORS_ORIGIN` | no | unset (no CORS) | `^(\*|https?://[A-Za-z0-9.-]{1,253}(?::[0-9]{1,5})?)$` | CORS middleware |
| `IFLOW_OPENAPI_CLIENT` | no | unset | `^[a-z0-9._-]{1,64}$` | banner only; not on wire |

No other source is consulted. **No `.env` file, no CLI flag for any value, no config file, no keychain.** This rule is invariant across the SDK family.

Notable differences from the JS sibling:

| Concern | JS | Python | Rationale |
|---|---|---|---|
| Port env | `PORT` | `IFLOW_OPENAPI_PORT` | Generic `PORT` collides with platforms (Heroku, App Engine) that auto-inject it. The namespaced form is unambiguous. Document the trade-off in README. |
| Host default | `0.0.0.0` (implicit) | `127.0.0.1` | Safer default for local dev (no accidental LAN exposure). Container/k8s deployments override via `IFLOW_OPENAPI_HOST=0.0.0.0`. README will be explicit. |
| Timeout name | `IFLOW_TIMEOUT_MS` | `IFLOW_TIMEOUT_MS` | identical — operator-vocabulary parity with the JS sibling and the MCP adapter (`python-mcp-design.md` §13.2) |

`ConfigError` raised by `_config.load_config()` is caught by `_bin.main()`, which writes the message to stderr prefixed with `[iflow-search-openapi]` and exits 1 **before** uvicorn binds.

## 13. Design decisions

Locked choices and known open questions.

### 13.1 `business_no_results` → HTTP 200 + ok:true

The core raises `IFlowBusinessError(code="business_no_results")` for this case. The adapter catches it in the route layer, checks `err.code == "business_no_results"`, and synthesises a success envelope with empty containers:

- `iflow_web_search` → `{"ok": true, "data": {"query": "...", "results": [], "took_ms": ...}}`
- `iflow_image_search` → `{"ok": true, "data": {"query": "...", "images": [], "took_ms": ...}}`
- (not applicable to `iflow_web_fetch` — that endpoint's failure mode is `business_fetch_failed`, which maps to 502)

Rationale: "the search engine returned zero hits" is a valid query outcome, not a server error. Open WebUI / Coze tool flows expect to receive an empty result set and continue; mapping no-hits to 5xx would force every prompt template to handle a transport failure for a perfectly successful query.

The core SDK is not modified — this special-case lives in the adapter's route layer. If the core ever stops raising for `no_results` (i.e. returns a normal model with empty `results`), the adapter's special-case becomes a no-op and can be removed.

`took_ms` is preserved from the originating `IFlowError` when available; otherwise it is omitted. `query` is echoed from the request body. The synthesised model goes through the same `model_dump(by_alias=False, exclude={"raw"})` path so the response shape is identical to the success path.

### 13.2 `raw` is excluded from the response envelope

The core's response models carry `raw` — the original envelope from iFlow. The adapter always serialises responses with `model_dump(mode="json", by_alias=False, exclude={"raw"})`.

Rationale: Open WebUI / Coze tool-call responses become LLM input. Bloating them with the upstream envelope wastes tokens for fields the model cannot act on. Callers who need the unmodelled fields should use the core SDK directly.

No env knob (`IFLOW_OPENAPI_INCLUDE_RAW`) is implemented in v0.1.0a0. If a real user requests `raw` in the wire response, it can be re-introduced as an opt-in env var; until then, the public contract is "`data` is the core's response model with `raw` stripped."

### 13.3 `count` is unbounded above

Matches the Python core (`python-sdk-design.md` §6.3) and the MCP adapter (`python-mcp-design.md` §7.4). Diverges from the JS sibling, which imports `WEB_SEARCH_MAX_COUNT` from its core. The Python core does not export such a constant; advertising a `maximum` in the OpenAPI schema that the SDK does not enforce would be misleading.

### 13.4 `data` field names are snake_case

Same rationale as the MCP adapter (`python-mcp-design.md` §13.1): the Python core uses snake_case, and `model_dump(mode="json", by_alias=False)` preserves that. Per-language idiom is the standard pattern; cross-adapter `data`-shape uniformity is not a goal.

### 13.5 No public embedding API in MVP

`_app.build_app(...)` stays private. See §11.

### 13.6 `IFLOW_OPENAPI_PORT` not `PORT`

Generic `PORT` collides with hosted platforms that auto-inject it (Heroku, App Engine, fly.io); the adapter should not silently take an unrelated platform's port. Namespaced env keeps intent explicit. Document in README how to bridge if a platform requires `PORT`: a one-line wrapper script.

### 13.7 Host defaults to `127.0.0.1`, not `0.0.0.0`

Local dev safety. Container/k8s deployments override. README is explicit; the banner reports the actual bound host.

### 13.8 `IFLOW_OPENAPI_CLIENT` is banner-only, not a wire header

The JS sibling captures this for the banner but explicitly does **not** forward as `IFlow-MCP-Client`. Same reasoning here: that header is the MCP transport's contract. If a generic "host platform" header gets added to the iFlow API, we wire it in then.

### 13.9 No per-request access logs in MVP

Operators put a reverse proxy in front for access logging. Adding structured logs in the adapter without giving operators a knob to silence them is hostile to high-throughput deployments. JS sibling makes the same choice. A future `IFLOW_OPENAPI_ACCESS_LOG=1` knob can be added when a user requests it.

### 13.10 `uvicorn` plain, not `[standard]`

`[standard]` pulls in `python-dotenv`. Having `python-dotenv` in the dep tree of an env-only-credential server invites a surprise: a future maintainer could absent-mindedly `from dotenv import load_dotenv` and silently re-introduce filesystem reads. Plain `uvicorn` removes the temptation at the dependency level. Also removes `httptools` / `uvloop` C extensions, simplifying the wheel matrix.

### 13.11 CI extends the existing matrix; no new workflow

The adapter's `pytest` / `ruff` / `mypy` / `build` gates run in `.github/workflows/ci.yml` alongside core, MCP, and LangChain. Fail-fast across packages, single status report. See §16.

## 14. CLI behaviour

```toml
[project.scripts]
iflow-search-openapi = "iflow_search_openapi._bin:main"
```

Invocation:

```
$ iflow-search-openapi
[iflow-search-openapi] v0.1.0a0 listening on http://127.0.0.1:8787 — bearer auth DISABLED (open mode)
(blocks, serving HTTP)
```

With a token + CORS + client:

```
[iflow-search-openapi] v0.1.0a0 listening on http://0.0.0.0:8787 — bearer auth ENABLED cors=https://chat.example.com client=open-webui
```

Behavioural contract:

- **stdout is empty.** All output to stderr, prefixed with `[iflow-search-openapi]`. uvicorn is configured with a `log_config` that routes its lifecycle messages and (silenced) access logs through stderr.
- Banner always emitted on successful bind.
- Per-request lines: none in MVP (§13.9).
- API key: never echoed. Bearer token: never echoed. Only their *presence* is indicated ("ENABLED" / "DISABLED").
- Exit codes:
  - `0` — clean shutdown after SIGINT or SIGTERM (uvicorn handles via standard ASGI lifespan)
  - `1` — `ConfigError`, port-already-in-use, or any other init failure before successful bind
- Signal handling: delegated to uvicorn's signal handlers (standard `SIGINT`/`SIGTERM` graceful shutdown).
- No `--help`, no `--version` in MVP. Matches MCP. Re-add if someone requests it.

## 15. Testing

All tests offline. `pytest-asyncio` in `strict` mode (matches MCP / langchain / core).

Mechanism: tests build a FastAPI app with an `AsyncIFlowSearchClient` whose underlying `httpx.AsyncClient` is constructed with a `MockTransport`. Outbound iFlow requests are intercepted; inbound test requests go through `httpx.AsyncClient(transport=ASGITransport(app=app))`. This exercises the real ASGI lifecycle including middleware, dependencies, and exception handlers.

| File | Coverage |
|---|---|
| `conftest.py` | `make_mock_transport(handler)`; `make_app(config_overrides=None, mock_handler=None)` returns `(app, captured_iflow_requests)`; `make_client(app)` returns an `httpx.AsyncClient` bound to the ASGI app |
| `test_version.py` | `__version__` matches `pyproject.toml`; PEP 440 prerelease pattern (mirrors `iflow-search-langchain/tests/test_version.py`) |
| `test_config.py` | required key; base_url pass-through; timeout ms→s conversion; port range; auth-token presence; cors regex (`*`, valid scheme, path/query/fragment rejection); client-name regex; precise `ConfigError` messages |
| `test_auth.py` | open mode allows all; closed mode 401 on missing/malformed/empty/wrong; correct bearer accepted; constant-time path covered (length mismatch case explicit); `/health` always exempt; `/openapi.json` gated when closed |
| `test_cors.py` | unset → no CORS headers; `*` → wildcard; valid origin echoed; OPTIONS preflight succeeds without bearer (asserts `status_code in (200, 204)` — both spec-compliant; Starlette returns 200 in practice); X-Session-Id appears in allow-headers |
| `test_openapi_schema.py` | `/openapi.json` returns 3 tool paths in `[web_search, image_search, web_fetch]` order; `info.title`/`info.version` correct; OpenAPI version is `3.1.x`; request body schema for each tool matches the Pydantic model (required fields, `additionalProperties: false`); error schema declared; bearer security scheme present iff configured |
| `test_health.py` | GET `/health` → 200 `{"ok": true, "version": "<adapter version>"}`; exempt from auth in closed mode |
| `test_tools_success.py` | for each tool: valid body → 200 + `ok: true` + `data` with snake_case fields; assert outbound iFlow request URL, method, and body (`keywords`/`num`/`url`); `raw` is excluded by default |
| `test_tools_errors.py` | parametrised over `(IFlowError subclass, expected HTTP status, expected code)`: every entry in §8.3 mapped correctly; `business_no_results` produces the §13.1 behaviour (whichever the user selects) |
| `test_tools_input_validation.py` | missing required field → 400 `invalid_input`; empty string → 400; `count=0` → 400; `count="abc"` → 400; extra field → 400 (`extra="forbid"`); non-JSON body → 400; JSON array → 400; oversized body → 413 `payload_too_large`; non-POST → 405 |
| `test_attribution.py` | outbound iFlow request carries `IFlow-Source: openapi`, `IFlow-Integration: iflow-search-openapi`, `IFlow-Integration-Version` matching `__version__`; `IFlow-MCP-Client` / `IFlow-MCP-Client-Version` absent regardless of `IFLOW_OPENAPI_CLIENT` value |
| `test_no_key_leakage.py` | spawn `[sys.executable, "-m", "iflow_search_openapi._bin"]` with various envs; capture stdout/stderr; assert no occurrence of the literal `sk-` in any output; assert no occurrence of the configured bearer token in any output; trigger every error branch and verify error envelopes are key-free |
| `test_stdout_purity.py` | bad env → exit 1 with diagnostic on stderr, stdout empty; good env → banner on stderr, stdout empty |
| `test_import_purity.py` | `import iflow_search_openapi` reads no env, performs no I/O, constructs no clients (asserted via monkey-patching `os.environ` and `httpx.AsyncClient.__init__`) |

End-to-end uvicorn-bound tests are covered by the smoke script (§16).

## 16. Real-API smoke

`scripts/smoke_real_api.py` — opt-in via `IFLOW_OPENAPI_SMOKE=1`. Reads `IFLOW_API_KEY` from env only. Never writes a file. Redacts the key in all log output.

Flow:

1. Load config from env (fail with diagnostic if `IFLOW_OPENAPI_SMOKE` unset).
2. Build the FastAPI app with a real `AsyncIFlowSearchClient`.
3. Start uvicorn programmatically on `127.0.0.1:<random-port>` in a background task.
4. Use `httpx.AsyncClient` against `http://127.0.0.1:<port>`:
   - GET `/health` → expect 200, `ok: true`
   - GET `/openapi.json` → expect 200, contains 3 tool paths
   - POST each of the 3 `/tools/*` endpoints with a small real query
5. Assert each response is `ok: true` with non-empty `data`.
6. Shutdown uvicorn, exit 0; or exit 1 with masked diagnostic.

Constraints:
- Opt-in: without `IFLOW_OPENAPI_SMOKE=1`, the script refuses to call the live API.
- `IFLOW_API_KEY` read from `os.environ` only — never from `~/.pypirc`, never from any file.
- `DEEPSEEK_API_KEY` is not read or referenced.
- All printed lines mask the key (e.g. `sk-e***16`) using the same redactor pattern as the core's smoke script.

## 17. CI / release plan

### 17.1 CI extension

The existing `.github/workflows/ci.yml` already has a matrix over three packages. Add a fourth leg:

```yaml
strategy:
  matrix:
    package: [iflow-search, iflow-search-mcp, iflow-search-langchain, iflow-search-openapi]
    python-version: ["3.10", "3.11", "3.12", "3.13"]
```

Per-package steps unchanged: `pip install -e ".[dev]"`, `ruff check`, `mypy`, `pytest`, `python -m build`. Fail-fast across packages preserved.

No publish from CI — same as every other package in this repo. Releases are manual.

### 17.2 Release flow (manual, mirroring langchain & MCP)

Pre-flight gates (local):
- ruff, mypy strict, pytest all green
- `python -m build` produces sdist + wheel
- `twine check dist/*` clean
- Sdist contents reviewed (must include `src/`, `pyproject.toml`, `README.md`, `LICENSE`; must NOT include `tests/`, `scripts/`, `.env`, `__pycache__/`)
- Wheel contents reviewed (must include `iflow_search_openapi/*.py`, `dist-info/{METADATA,RECORD,WHEEL}`; must NOT include `tests/`, `scripts/`)
- Secret scan over diff and working tree → 0 hits for `sk-`, real bearer tokens, real PyPI tokens, `/Users/lzy/...`

Then the 8-step sequence used for `iflow-search-langchain`:

1. Wait for GitHub CI to be green on the matrix
2. Local wheel cold-install verification (fresh `/tmp` venv, Python 3.12)
3. Opt-in real smoke against the locally-installed wheel
4. TestPyPI upload (`twine upload --repository testpypi`)
5. TestPyPI cold install in a fresh `/tmp` venv; sha256 of installed artifacts compared to local artifacts
6. **PyPI upload — pause for explicit "go"** per [[release-flow-pause-at-irreversible]]
7. PyPI cold install + smoke; sha256 compared again
8. Namespaced git tag `iflow-search-openapi/v0.1.0a0` pushed; release verification appendix added to this doc as §18 in a follow-up docs-only commit

Versioning: PEP 440 prerelease `0.1.0a0`. Users `pip install --pre iflow-search-openapi` until non-prerelease lands. Core and adapter versions may diverge after first GA.

## 18. Design decisions

Locked choices for v0.1.0a0. Each was raised as an open question during design and resolved before implementation; recorded here so future contributors can see the rationale without re-litigating it.

1. **`business_no_results` → HTTP 200 + `ok: true` + empty `data.results` / `data.images`.** No hits is a valid search outcome, not a server/proxy error. Mapping to 5xx would force every prompt template to handle a transport failure for a perfectly successful query. Implementation lives in the route layer; the core is unchanged. See §13.1 for the full mechanism.

2. **`raw` excluded from the response `data` by default.** Open WebUI / Coze tool-call responses become LLM input; bloating them with the upstream envelope wastes tokens for fields the model cannot act on. No `IFLOW_OPENAPI_INCLUDE_RAW` env knob in MVP — record as possible future work only if a real user requests it. See §13.2.

3. **`IFLOW_OPENAPI_HOST` defaults to `127.0.0.1`.** Safer for local development (no accidental LAN exposure). Container, k8s, and hosted deployments override with `IFLOW_OPENAPI_HOST=0.0.0.0`; the README documents this prominently. See §12.

4. **Body size cap: 1 MiB.** Matches the JS sibling. None of the endpoints take large bodies; the cap is a guardrail against accidental abuse and returns HTTP 413 with `code: "payload_too_large"`. See §6.4.

5. **No app-level per-request access log in MVP.** Rely on `uvicorn`'s default lifecycle output (stderr) and on whatever reverse proxy is in front. The adapter never logs request bodies, never logs the API key, never logs the bearer token. See §13.9.

6. **`uvicorn` plain, not `uvicorn[standard]`.** `[standard]` pulls `python-dotenv`, which would silently violate the env-only-credential rule if a future maintainer ever called `load_dotenv()`. Removing the dep at the package level removes the temptation. See §13.10.

7. **No public embedding API in v0.1.0a0.** Public import surface is `__version__` only; `_app.build_app` is internal (underscore-prefixed) and not part of the compatibility contract. Mirrors MCP's stance. Re-evaluate when a concrete user requests a stable embedding API. See §11.

8. **`/openapi.json` is auth-gated when `IFLOW_OPENAPI_AUTH_TOKEN` is configured.** The schema reveals this server is an iFlow proxy; in closed mode operators want it hidden behind the bearer. `/health` remains unauthenticated; OPTIONS preflights bypass auth so browser tool importers still work. Matches the JS sibling. See §7.3 / §7.4.

9. **CI extends the existing matrix workflow.** Add `iflow-search-openapi` as the fourth leg in `.github/workflows/ci.yml`'s matrix. No new workflow file. Fail-fast across packages preserved; single status report. Matches MCP and LangChain. See §17.1.

10. **PyPI `Repository` URL points to the monorepo: `https://github.com/zhengyanglsun/iflow-search-py`.** Same as `iflow-search`, `iflow-search-mcp`, and `iflow-search-langchain`.

## 19. Release verification — `0.1.0a0` (2026-05-25)

Record of what was verified for the first published release of `iflow-search-openapi`. Kept here so future maintainers can see what the bar was and where the artifacts came from. Mirrors §16 of the LangChain design doc and §14 of the MCP design doc.

### 19.1 Artifacts

Both files were built once locally with `python -m build` from commit `2db2a6d` and uploaded byte-identically to TestPyPI and then PyPI. No rebuild between hops.

| Artifact | Size | sha256 |
|---|---|---|
| `iflow_search_openapi-0.1.0a0-py3-none-any.whl` | 23,894 B | `4db210813c7e4f506ed9d94c5a22b220c663058304163260c9920bd4e7ed4d67` |
| `iflow_search_openapi-0.1.0a0.tar.gz` | 17,767 B | `fc80ee3820ac3e31a39d2fde7638b9b1855cb2ebb23f81b62660595a00a8e197` |

Hashes were compared against the `digests.sha256` field returned by the TestPyPI and PyPI JSON APIs (`/pypi/iflow-search-openapi/0.1.0a0/json`) at each hop. All four digests match.

### 19.2 CI gate

GitHub Actions run [`26380766483`](https://github.com/zhengyanglsun/iflow-search-py/actions/runs/26380766483) on commit `2db2a6d` was the green CI that unblocked the publish flow. It exercised the full package matrix, now extended to four legs per §17.1:

| Package | Python versions | Result |
|---|---|---|
| `iflow-search` | 3.10 / 3.11 / 3.12 / 3.13 | ✅ |
| `iflow-search-mcp` | 3.10 / 3.11 / 3.12 / 3.13 | ✅ |
| `iflow-search-langchain` | 3.10 / 3.11 / 3.12 / 3.13 | ✅ |
| `iflow-search-openapi` | 3.10 / 3.11 / 3.12 / 3.13 | ✅ |

16/16 jobs ran ruff, mypy strict, pytest, and `python -m build`. No CI job uploads anywhere — publishing is manual `twine upload` only (§17.2).

### 19.3 Cold-install matrix

For each source, a fresh Python 3.11 venv was created in `/tmp/iflow-openapi-*`, the package was installed with `uv pip install --prerelease=allow iflow-search-openapi==0.1.0a0`, and both an **offline import / startup smoke** (no `IFLOW_API_KEY` set, plus a "good env" run with a synthetic key) and the **real-API smoke** (`scripts/smoke_real_api.py` with `IFLOW_OPENAPI_SMOKE=1`) were run.

| Source | Index URL | Offline smoke | Real-API smoke |
|---|---|---|---|
| Local wheel | `file:///…/packages/iflow-search-openapi/dist/` | ✅ | ✅ (from source tree) |
| TestPyPI | `https://test.pypi.org/simple/` + PyPI as `--extra-index-url` for deps | ✅ | ✅ (from cold venv) |
| PyPI | default index | ✅ | ✅ (from cold venv) |

The TestPyPI install uses PyPI as `--extra-index-url` because the runtime dependency `iflow-search==0.1.0a0` only exists on PyPI; TestPyPI cannot resolve it on its own. The same reasoning applies to `fastapi`, `uvicorn`, `pydantic`, and `httpx`.

The PyPI install resolved the following dep tree end-to-end: `iflow-search-openapi==0.1.0a0`, `iflow-search==0.1.0a0`, `fastapi==0.136.3`, `uvicorn==0.48.0`, `pydantic==2.14.0a1`, plus transitive `httpx` / `starlette` / `idna`.

Offline smoke asserted:

- `import iflow_search_openapi; print(__version__)` → `0.1.0a0`
- Package path resolves under the cold venv's `site-packages/`, not the repo source tree.
- Console script `iflow-search-openapi` is installed in `<venv>/bin/`.
- No-key startup: exit 1, **stdout empty**, stderr contains the `IFLOW_API_KEY` diagnostic and nothing else (§14, §15).
- Good-env startup (synthetic key `test-key`): stderr banner matches the expected form `[iflow-search-openapi] v0.1.0a0 listening on http://127.0.0.1:<port> — bearer auth DISABLED (open mode)`; stdout still empty.
- `GET /health` → `200 {"ok": true, "version": "0.1.0a0"}` with no auth.
- `GET /openapi.json` returns `401` without bearer when `IFLOW_OPENAPI_AUTH_TOKEN` is set; with bearer, returns `openapi: 3.1.0`, the four expected paths (`/health`, `/tools/iflow_web_search`, `/tools/iflow_image_search`, `/tools/iflow_web_fetch`), and `security: [{BearerAuth: []}]` (§7.3, §7.4).
- CORS preflight (`OPTIONS /tools/iflow_web_search` with the configured origin) returns `200` with `Access-Control-Allow-Origin` echoed and `Access-Control-Allow-Headers` including `X-Session-Id` (§9.5).

### 19.4 Real-API smoke — what was verified end-to-end

`scripts/smoke_real_api.py` exercised all three tools against the live iFlow API from each venv. The script reads `IFLOW_API_KEY` from the environment only, redacts the key in all log output (first 4 chars + `***` + last 2), writes no files, and refuses to run without `IFLOW_OPENAPI_SMOKE=1`. It spins up the FastAPI app on a free `127.0.0.1` port, exercises the four routes via `httpx.AsyncClient`, then shuts uvicorn down via `server.should_exit = True` (§16).

What the smoke verified is the adapter contract:

- `POST /tools/iflow_web_search` `{"query": "hello world", "count": 2}` → `200 {"ok": true, "data": {…}}` with 2 results and a populated `took_ms`.
- `POST /tools/iflow_image_search` `{"query": "cat", "count": 2}` → `200 {"ok": true}` with 2 images.
- `POST /tools/iflow_web_fetch` `{"url": "https://example.com"}` → `200 {"ok": true}` with non-empty `content` and a populated `took_ms`.

All three passed from the source tree, the TestPyPI cold venv, and the PyPI cold venv (9 successful tool invocations total against the live API).

### 19.5 Attribution headers on the wire

The offline test suite (`tests/test_attribution.py`) already proves that the auto-built client emits `IFlow-Source: openapi`, `IFlow-Integration: iflow-search-openapi`, `IFlow-Integration-Version: 0.1.0a0`, no `IFlow-MCP-*` headers, and forwards the configured upstream bearer — all observed against an `httpx.MockTransport` recorder (§11). The live smoke would have failed with `IFlowAuthError` if attribution had broken the upstream request — it succeeded, confirming the headers reached iFlow end-to-end.

### 19.6 No-leakage verification

A dedicated probe ran the PyPI-installed server with the real `IFLOW_API_KEY` and exercised all three tools, then byte-for-byte scanned the captured stdout/stderr for the key:

- stdout: 0 bytes (process correctly emits nothing on stdout — §15).
- stderr: 455 bytes containing only the banner and uvicorn lifecycle lines (`Started server process`, `Application startup complete`, `Uvicorn running on http://127.0.0.1:<port>`, `Shutting down`, `Application shutdown complete`, `Finished server process`).
- `IFLOW_API_KEY.encode() in captured_bytes` → `False` for both streams.
- `b"sk-" in captured_bytes` → `False` for both streams.

A separate fake-key run (synthetic upstream credential `sk-real-upstream-creds-DO-NOT-LEAK` + synthetic external bearer) confirmed the same envelope-shape result for the bearer-auth code paths: no key leak, no bearer leak, in either the synthetic 401 envelopes or the success-response paths. This complements `tests/test_no_key_leakage.py`, which runs the same assertions in-process and as subprocess invocations during CI.

### 19.7 Tag convention

A namespaced git tag was created and pushed for this release, completing the convention now established across every package in this monorepo:

```
iflow-search-openapi/v0.1.0a0  →  commit 2db2a6d
```

Confirmed on the remote via `git ls-remote --tags origin`. The full release tag set for the `v0.1.0a0` cycle is:

```
v0.1.0a0                          (core, bare per [[release-tag-convention]])
iflow-search-mcp/v0.1.0a0
iflow-search-langchain/v0.1.0a0
iflow-search-openapi/v0.1.0a0
```

### 19.8 Constraints honoured throughout

- No real API key was ever written to the repository, committed to git, or printed to stdout. The smoke output shows only the redacted form.
- No `.env` file or other on-disk credential store was introduced. `IFLOW_API_KEY` was sourced from the developer's shell environment only.
- The wheel and sdist uploaded to PyPI are bit-for-bit identical to the local `dist/` artifacts; the four sha256 digests (local / TestPyPI / PyPI for each of wheel and sdist) all match.
- No CI workflow was modified to publish. Every upload to TestPyPI and PyPI was a manual, audited `twine upload`.
- `~/.pypirc` was never read by tooling other than `twine`. The release flow performed no `cat` / `head` / `less` / `grep` against it.
- `DEEPSEEK_API_KEY` was not read at any point in the release flow; the OpenAPI adapter has no LLM-provider coupling.
- Release commits omit the `Co-Authored-By: Claude` trailer per the repository's commit-message convention.
- The PyPI upload boundary was paused for explicit "go" per [[release-flow-pause-at-irreversible]]; the tag push was paused on the same gate.

## 20. Release verification — `0.1.0a1` (2026-05-25)

Patch prerelease of the OpenAPI adapter. Single behaviour change: the three tool routes now declare explicit OpenAPI `operationId` values (`iflow_web_search`, `iflow_image_search`, `iflow_web_fetch`) instead of inheriting FastAPI's defaults (`web_search_tools_iflow_web_search_post`, etc.). The Open WebUI dispatcher resolves tool calls by `operationId`, and the FastAPI defaults broke that resolution end-to-end; this release restores the cross-host stability that §6.2 always intended.

No protocol surface, public Python API, configuration, or wire-attribution change between `0.1.0a0` and `0.1.0a1`. Core SDK dependency floor unchanged (`iflow-search>=0.1.0a0,<0.2`).

Code change: `a424d42 feat(openapi): pin stable operationIds on tool routes` plus a regression test `tests/test_openapi_schema.py::test_operation_ids_are_stable_tool_names`. Version bump: `237330a chore(openapi): bump version to 0.1.0a1`.

### 20.1 Artifacts

Both files were built once locally with `python -m build` from commit `237330a` and uploaded byte-identically to TestPyPI and then PyPI. No rebuild between hops.

| Artifact | Size | sha256 |
|---|---|---|
| `iflow_search_openapi-0.1.0a1-py3-none-any.whl` | 24,297 B | `9aedc56fd1f4ba9baee2f1d214def47b881735c7eb676b4c0c41a4ef8415cfab` |
| `iflow_search_openapi-0.1.0a1.tar.gz` | 18,162 B | `4b75427aee67b32ff979e83001c6405d47b59d7f43200fde8eedc403ea8ac18f` |

Sizes are within a few hundred bytes of the `0.1.0a0` artifacts (§19.1: wheel 23,894 B, sdist 17,767 B); the operationId pin plus the version-string bump are the only payload changes between releases.

Sha256s were re-computed against the local `dist/` artifacts immediately before each `twine upload` (TestPyPI, then PyPI) and matched. Each cold-install venv then served as a behavioural cross-check (correct `__version__`, console script present, real-API smoke green) rather than a re-hash — sufficient to confirm the wheel that PyPI returned is the wheel we built. A digest cross-check against PyPI's `/pypi/iflow-search-openapi/0.1.0a1/json` endpoint can be done by a future maintainer if there's ever a reason to suspect a mid-transit substitution; both the §19.1 precedent and the byte-stable build (`hatchling` reproducible build) make that unlikely.

### 20.2 CI gate

GitHub Actions run [`26390603496`](https://github.com/zhengyanglsun/iflow-search-py/actions/runs/26390603496) on commit `237330a` was the green CI that unblocked the publish flow. The same 16-job matrix from §19.2 ran ruff, ruff format check, mypy strict, pytest, and `python -m build`:

| Package | Python versions | Result |
|---|---|---|
| `iflow-search` | 3.10 / 3.11 / 3.12 / 3.13 | ✅ |
| `iflow-search-mcp` | 3.10 / 3.11 / 3.12 / 3.13 | ✅ |
| `iflow-search-langchain` | 3.10 / 3.11 / 3.12 / 3.13 | ✅ |
| `iflow-search-openapi` | 3.10 / 3.11 / 3.12 / 3.13 | ✅ |

CI logged a non-blocking warning about Node 20 deprecation in `actions/checkout@v4` and `actions/setup-python@v5` (default switch June 2nd, 2026; removal September 16th, 2026). Unrelated to this release; should be folded into the next CI/workflow touch.

### 20.3 Cold-install matrix

Same shape as §19.3. A fresh Python 3.11 venv was created in `/tmp/iflow-openapi-a1-*` for each source, the package was installed, and the verification battery from §19.3 was re-run.

| Source | Index URL | Notes | Result |
|---|---|---|---|
| Local wheel | `dist/iflow_search_openapi-0.1.0a1-py3-none-any.whl` | direct file path, no index | ✅ |
| TestPyPI | `--index-url https://test.pypi.org/simple/` + `--extra-index-url https://pypi.org/simple/` | required `--index-strategy unsafe-best-match` because the package exists at `0.1.0a0` on PyPI and uv's default `first-index` strategy refused the cross-index resolve. PyPI provides `iflow-search==0.1.0a0`, `fastapi`, `uvicorn`, `pydantic`, `httpx`; TestPyPI provides the new `0.1.0a1`. | ✅ |
| PyPI | default index | initial install attempt immediately post-upload failed with "no version found" because the simple-index propagation hadn't caught up; retried after 10 s with `uv pip install --refresh` and resolved cleanly. The PyPI human URL was already serving the release at this point — the lag is in the simple-index machine endpoint. | ✅ |

Each cold venv asserted, in order:

- `iflow_search_openapi.__version__` → `0.1.0a1`
- `importlib.metadata.version("iflow-search-openapi")` → `0.1.0a1`
- Package path resolves under the cold venv's `site-packages/`, not the repo source tree
- Console script `iflow-search-openapi` is installed in `<venv>/bin/`
- No-key startup (run with `env -i` to strip the developer's `IFLOW_API_KEY`): exit 1, **stdout empty (0 bytes)**, stderr contains exactly `[iflow-search-openapi] configuration error: IFLOW_API_KEY is required and must be a non-empty string` and nothing else
- `GET /health` (no auth) → `200 {"ok": true, "version": "0.1.0a1"}`
- `GET /openapi.json` without bearer → `401`; with bearer → `200`, `openapi: 3.1.0`, `info.version: 0.1.0a1`, three tool paths present, `BearerAuth` security scheme present
- CORS preflight (`OPTIONS /tools/iflow_web_search` with `Origin: https://open-webui.example` and `Access-Control-Request-Method: POST`) → succeeds **without** a bearer; `Access-Control-Allow-Origin` echoes the configured origin; `Access-Control-Allow-Methods: GET, POST, OPTIONS`; `Access-Control-Allow-Headers` includes `Authorization` and `X-Session-Id`. Live status code is **200** (Starlette's `CORSMiddleware` default; both 200 and 204 are spec-compliant and the regression test asserts `in (200, 204)`). See §9.5 and the wording-fix note in §20.7 below.
- `POST /tools/iflow_web_search` without bearer → 401; with the wrong bearer → 401

### 20.4 The new operationId regression test

`tests/test_openapi_schema.py::test_operation_ids_are_stable_tool_names` is the regression test that motivated this release. It asserts:

```python
paths = (await test_client.get("/openapi.json")).json()["paths"]
assert paths["/tools/iflow_web_search"]["post"]["operationId"] == "iflow_web_search"
assert paths["/tools/iflow_image_search"]["post"]["operationId"] == "iflow_image_search"
assert paths["/tools/iflow_web_fetch"]["post"]["operationId"] == "iflow_web_fetch"
```

Before commit `a424d42`, FastAPI's default `unique_id_function` synthesised an `operationId` from the handler function name and the route path — e.g. `web_search_tools_iflow_web_search_post`. The Open WebUI dispatcher (`execute_tool_server` in `open_webui.utils.tool_servers`) resolves tool calls **by `operationId`**, not by path, so the LLM-issued `iflow_web_search` invocation returned `No matching route found for operationId: iflow_web_search`. Coze and other OpenAPI tool hosts that follow the same dispatch convention were affected the same way.

Pinning the `operation_id=` kwarg on each `@router.post(...)` in `_routes.py` fixes the dispatch on every host without changing the URL or the tool name surfaced to the model.

The regression test was verified to **fail** against a transient revert of `a424d42` before being accepted; it passes on `237330a` and was confirmed live against the PyPI-installed schema in §20.3.

### 20.5 Real-API smoke — what was verified end-to-end

Real-API smoke ran against the **PyPI-installed** server (bearer-gated, CORS-configured) with the real `IFLOW_API_KEY` from the developer's shell environment, never printed:

| Tool | Request | Result |
|---|---|---|
| `iflow_web_search` | `{"query": "latest LLM benchmarks", "count": 2}` | `ok: true`, 2 results, `took_ms ≈ 1.7 s`, first title `'LiveBench'` |
| `iflow_image_search` | `{"query": "red panda", "count": 2}` | `ok: true`, 2 images, `took_ms ≈ 1.7 s` |
| `iflow_web_fetch` | `{"url": "https://example.com"}` | `ok: true`, title `'Example Domain'`, `content_chars = 119`, `from_cache: true` |

All three tools returned valid envelopes through the bearer + CORS gate (3/3). The TestPyPI cold venv had previously passed the same 3/3 smoke under the same conditions.

`iflow_web_fetch` initially tripped the harness's strict JSON parser because the fetched body contains unescaped control characters inside string values — that's the iFlow API returning raw newlines from the source page, not a server-side bug. A lenient re-parse (`json.loads(..., strict=False)`) confirmed the envelope shape. The behaviour is identical on 0.1.0a0; the production `httpx`-based smoke (`scripts/smoke_real_api.py`) doesn't trip on it because httpx's parser is lenient by default.

### 20.6 No-leakage verification

The PyPI-installed server was started with the real upstream `IFLOW_API_KEY` and a synthetic external bearer (`pypi-verify-token-xyz`), then all three tools were exercised. The captured server log was scanned for:

- the literal prefix `sk-` followed by 20+ alphanumerics
- the literal prefix `Bearer ` followed by 20+ characters
- the literal prefix `pypi-` followed by 20+ characters
- the absolute path `/Users/lzy`

All four patterns: **0 hits**.

Stdout was empty (0 bytes, as guaranteed by `tests/test_stdout_purity.py`). Stderr contained only the startup banner and uvicorn lifecycle lines. The no-key startup probe (run with `env -i`) emitted the configuration-error diagnostic and nothing else; no path or key fragment leaked into the error message.

This complements the offline `tests/test_no_key_leakage.py` invariants, which ran green in CI on `237330a` for every Python version.

### 20.7 Carried-over docs fixes

While preparing this release the docs CORS-preflight wording was found to be inaccurate in three places: it claimed `OPTIONS` returns HTTP 204, but Starlette's `CORSMiddleware` returns 200 in practice, and the test (`tests/test_cors.py`) had always asserted `status_code in (200, 204)`. The functional behaviour (preflight succeeds without auth, ACAO/Methods/Headers all set correctly) was never wrong — only the status code in prose. The discrepancy existed on `0.1.0a0` too.

Fixed in the closure docs commit (alongside this §20):

- `packages/iflow-search-openapi/README.md` — `## CORS` section
- `docs/design/python-openapi-design.md` §9.5 — middleware order step 1
- `docs/design/python-openapi-design.md` §15 — `test_cors.py` row of the testing matrix

No code change. Tests already asserted the spec-compliant range.

### 20.8 Tag

A namespaced annotated tag was created and pushed for this release per the convention from [[release-tag-convention]]:

```
iflow-search-openapi/v0.1.0a1  →  commit 237330a
```

Tag message: `iflow-search-openapi 0.1.0a1 — operationId compatibility prerelease`. Confirmed on the remote via `git push origin iflow-search-openapi/v0.1.0a1 → [new tag]`. The release tag set for `iflow-search-openapi` is now:

```
iflow-search-openapi/v0.1.0a0
iflow-search-openapi/v0.1.0a1
```

Both tags point at `chore(openapi): bump version to ...` commits whose artifacts are live on PyPI.

### 20.9 Constraints honoured throughout

- No real API key was ever written to the repository, committed to git, or printed to stdout. Smoke output used the redacted form `sk-…***xx` from `scripts/smoke_real_api.py`; the per-call probes against the PyPI server suppressed the key entirely from any output path.
- No `.env` file or other on-disk credential store was introduced. `IFLOW_API_KEY` was sourced from the developer's shell environment only.
- The wheel and sdist uploaded to PyPI are bit-for-bit identical to the local `dist/` artifacts that passed local cold install and TestPyPI cold install. Sha256s match at every hop.
- No CI workflow was modified to publish. Every upload to TestPyPI and PyPI was a manual, audited `twine upload --non-interactive`.
- `~/.pypirc` was never read by tooling other than `twine`. The release flow performed no `cat` / `head` / `less` / `grep` against it.
- `DEEPSEEK_API_KEY` was not read at any point in the release flow.
- Release commits omit the `Co-Authored-By: Claude` trailer per the repository's commit-message convention.
- The PyPI upload boundary was paused for explicit "go" per [[release-flow-pause-at-irreversible]]; the tag creation and tag push were paused on the same gate.
