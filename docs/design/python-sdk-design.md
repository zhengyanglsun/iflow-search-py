# iflow-search Python SDK — Design

This document describes the design of the `iflow-search` Python SDK: how the package is structured, what the public API looks like, how requests and responses are shaped, and how errors are mapped.

---

## 1. Scope

`iflow-search` is the framework-agnostic core SDK for the iFlow Search API. It exposes three endpoints — web search, image search, and web-page fetching — and returns structured, typed Python objects suitable for use by LLM agents and conventional applications alike.

The core has no LangChain / MCP / FastAPI dependencies. Adapter packages may be published separately under the same `iflow-search-*` prefix and depend on this one.

---

## 2. Distribution and import names

| Role | PyPI name | Import name |
|---|---|---|
| Core SDK | `iflow-search` | `iflow_search` |

Adapter packages published from this monorepo:

- `iflow-search-langchain` — LangChain (and LangGraph) tools.
- `iflow-search-mcp` — MCP stdio server.
- `iflow-search-openapi` — FastAPI / OpenAPI 3.1 tool server.

Reuse rules:

- LangGraph reuses LangChain tools — no separate package.
- Other MCP-capable agent hosts consume the MCP server directly.
- Open WebUI / Coze / similar low-code platforms consume the OpenAPI server.

---

## 3. Python version and runtime dependencies

- `requires-python = ">=3.10"` — gives modern type syntax (`X | None`), structural pattern matching, and is supported by every framework target.
- Runtime deps: `httpx>=0.27,<1.0`, `pydantic>=2.7,<3.0`. Nothing else.

Sync and async clients are both shipped from day one. FastAPI route handlers and the MCP server need async; CrewAI tools, scripts, and Jupyter sessions need sync.

---

## 4. API surface

Base URL: `https://platform.iflow.cn`. Auth: `Authorization: Bearer <api-key>`.

### 4.1 `POST /api/search/webSearch`

Request body:

```json
{ "keywords": "<string, required>", "num": <int, optional> }
```

Response `data`:

```json
{
  "query": "<string>",
  "organic": [
    { "title": "<string>", "link": "<string>", "snippet": "<string>",
      "position": <int>, "date": "<string|null>" }
  ]
}
```

### 4.2 `POST /api/search/imageSearch`

Request body:

```json
{ "keywords": "<string, required>", "num": <int, optional> }
```

Response `data` is observed as a bare array (this differs from the generic object-shaped description elsewhere):

```json
[ { "url": "<image-url>", "refUrl": "<source-page>", "title": "<string|empty>" } ]
```

The image normalizer also accepts `data` as an object containing a list under `images` / `results` / `items` / `organic`, so a future shape change does not break clients.

### 4.3 `POST /api/search/webFetch`

Request body:

```json
{ "url": "<absolute-url, required>" }
```

Response `data`:

```json
{ "title": "<string>", "content": "<string>", "url": "<string>", "fromCache": <bool> }
```

### 4.4 Common envelope

Every endpoint responds with the same envelope:

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

### 4.5 Documented business error codes

| `code` | Meaning |
|---|---|
| `200` | success |
| `400` | parameter validation |
| `500` | upstream / internal |
| `40303` | rate limit (per-key 1000 RPM across all three endpoints) |
| `60400` | insufficient credits |
| `90001` | webFetch parse failure |
| `90002` | search returned no results |
| `90402` | invalid API key |

---

## 5. Wire-format renames

The public Python API uses ergonomic names; the SDK rewrites them on the wire.

| Direction | Wire | Python |
|---|---|---|
| Request (web / image) | `keywords` | `query` |
| Request (web / image) | `num` | `count` |
| Response (web)        | `link`      | `url` (on `WebSearchResult`) |
| Response (image)      | `url`       | `image_url` |
| Response (image)      | `refUrl`    | `source_url` |
| Response (web_fetch)  | `fromCache` | `from_cache` |
| Added client-side     | —           | `took_ms` |

The raw envelope is always preserved on `response.raw`. Callers that need fields the SDK did not model can read them without an SDK release.

---

## 6. Client design

### 6.1 Public API

```python
from iflow_search import IFlowSearchClient

client = IFlowSearchClient(
    api_key=None,                # optional; falls back to IFLOW_API_KEY env var
    source=None,                 # IFlow-Source header; defaults to "python"
    integration_name=None,       # defaults to "iflow-search"
    integration_version=None,    # defaults to installed package version
    base_url=None,               # defaults to https://platform.iflow.cn
    timeout=None,                # seconds; defaults to 30.0
    http_client=None,            # inject an httpx.Client for pooling or tests
    mcp_client_name=None,        # used only by the MCP adapter
    mcp_client_version=None,
)

response = client.web_search(query="flash attention", count=5)
for r in response.results:
    print(r.title, r.url)
```

`AsyncIFlowSearchClient` has the same constructor signature and the same three methods (`web_search`, `image_search`, `web_fetch`), but they are `async`.

### 6.2 Sync and async are independent

Both clients call `httpx` directly. They share pure helpers (`_http.py`, `_normalize.py`, `_attribution.py`) but do not delegate to each other. Running a sync client inside a thread pool to satisfy an async caller deadlocks under FastAPI / asyncio, so that pattern is explicitly avoided.

### 6.3 Input validation

Validation happens only at the boundary:

- `query` must be a non-empty string.
- `url` must be a non-empty string.
- `count` must be a positive integer when provided; `None` means "omit `num` from the wire payload and let the server apply its default."
- `count` is **not** clamped to any maximum.

Anything beyond these checks is the server's responsibility.

### 6.4 Response models

Pydantic v2 models, snake_case fields:

```
WebSearchResult       { title, url, snippet, position, date }
WebSearchResponse     { query, results: list[WebSearchResult], took_ms, raw }
ImageResult           { image_url, source_url, title, width, height, position }
ImageSearchResponse   { query, images: list[ImageResult], took_ms, raw }
WebFetchResponse      { url, title, content, from_cache, took_ms, raw }
```

`model_config = ConfigDict(extra="ignore", populate_by_name=True)` so that:

- Extra fields from a newer iFlow API version do not break decoding.
- Field aliases (between wire names and Python names) work both ways.

`took_ms` is measured client-side via `time.monotonic_ns()`. It is always present and reflects wall time observed by the SDK.

---

## 7. Attribution headers

The core SDK is the only place that constructs `Authorization`, `IFlow-*`, and `User-Agent` headers. Adapter packages customize them via constructor arguments — they never mutate the header dict.

### 7.1 Always emitted

| Header | Source | Value |
|---|---|---|
| `Authorization` | core | `Bearer <api_key>` |
| `Content-Type` | core | `application/json` |
| `Accept` | core | `application/json` |
| `IFlow-Source` | constructor arg `source=` | non-empty string; default `"python"` |
| `IFlow-Integration` | constructor arg `integration_name=` | default `"iflow-search"` |
| `IFlow-Integration-Version` | constructor arg `integration_version=` | default installed package version |
| `User-Agent` | derived | `<integration_name>/<integration_version>` |

### 7.2 Conditionally emitted (MCP only)

| Header | When |
|---|---|
| `IFlow-MCP-Client` | emitted iff `mcp_client_name` is set; must match `^[a-z0-9._-]{1,64}$` |
| `IFlow-MCP-Client-Version` | emitted iff *both* `mcp_client_name` and `mcp_client_version` are set; must match `^[A-Za-z0-9._+-]{1,64}$` |

Setting `mcp_client_version` without `mcp_client_name` is a configuration error and raises `IFlowConfigError`. Absence of these headers is meaningful on the wire ("opted out"), so partial pairs must not be silently dropped.

### 7.3 What users may override

| Field | Override allowed? | Why |
|---|---|---|
| `api_key` | yes (constructor or `IFLOW_API_KEY` env) | required credential |
| `source` | yes | distinguish caller |
| `integration_name` | yes | for applications wrapping the SDK |
| `integration_version` | yes | matches above |
| `base_url` | yes | dev / staging / proxy |
| `timeout` | yes | network-condition dependent |
| `Authorization` | **no** | derived from `api_key` only |
| `Content-Type` / `Accept` | **no** | wire format is fixed |
| `User-Agent` | **no** | derived |

There is no API for users to set raw HTTP headers. This is a deliberate restriction — it keeps the wire format under SDK control and prevents accidental exposure of credentials in unintended headers.

### 7.4 Recommended `IFlow-Source` per adapter

| Adapter | `IFlow-Source` | `IFlow-Integration` |
|---|---|---|
| `iflow-search` (used directly) | `python` | `iflow-search` |
| `iflow-search-langchain` | `langchain` | `iflow-search-langchain` |
| `iflow-search-mcp` | `mcp` | `iflow-search-mcp` |
| `iflow-search-openapi` | `openapi` | `iflow-search-openapi` |

---

## 8. Error model

### 8.1 Exception hierarchy

```
IFlowError                          # base — every SDK exception inherits from this
├── IFlowConfigError                # missing api_key, invalid attribution
├── IFlowValidationError            # bad client-side input
├── IFlowAuthError                  # HTTP 401/403, business code 90402
├── IFlowRateLimitError             # HTTP 429, business code 40303
├── IFlowInsufficientCreditsError   # business code 60400
├── IFlowAPIError                   # HTTP 5xx, non-JSON 2xx, other non-2xx
├── IFlowBusinessError              # success=false with any other code
├── IFlowTimeoutError               # SDK-initiated timeout
└── IFlowNetworkError               # DNS / connection / TLS errors
```

Caller-initiated `asyncio.CancelledError` is **not** caught or wrapped — it propagates as itself so cooperative cancellation keeps working.

### 8.2 Common attributes on every `IFlowError`

| Attribute | Type | Notes |
|---|---|---|
| `message` | `str` | one-line human description |
| `code` | `str` | stable string identifier (see §8.5) |
| `request` | `dict \| None` | `{method, url, endpoint}`; no headers, no body |
| `response_body_truncated` | `str \| None` | first 500 chars of the raw response body, if any |

The underlying exception (e.g. `httpx.TimeoutException`) is preserved as `__cause__` via `raise ... from ...`.

### 8.3 HTTP status → exception

| HTTP | Exception |
|---|---|
| 2xx + valid JSON + `success: true` | (returns model) |
| 2xx + valid JSON + `success: false` | dispatched via business code (§8.4) |
| 2xx + non-JSON body | `IFlowAPIError(code="api_invalid_json")` |
| 400 | `IFlowValidationError(code="api_bad_request")` |
| 401 | `IFlowAuthError(code="api_unauthorized")` |
| 403 | `IFlowAuthError(code="api_forbidden")` |
| 429 | `IFlowRateLimitError(code="api_rate_limited")` |
| 5xx | `IFlowAPIError(code="api_server_error", status_code=…)` |
| other non-2xx | `IFlowAPIError(code="api_http_error", status_code=…)` |
| `httpx.TimeoutException` | `IFlowTimeoutError(code="network_timeout")` |
| `httpx.NetworkError` | `IFlowNetworkError(code="network_error")` |

### 8.4 Business code → exception

| iFlow `code` | Exception |
|---|---|
| `"200"` | (success) |
| `"400"` | `IFlowValidationError(code="business_bad_request")` |
| `"40303"` | `IFlowRateLimitError(code="business_rate_limited")` |
| `"60400"` | `IFlowInsufficientCreditsError(code="business_insufficient_credits")` |
| `"90001"` | `IFlowBusinessError(code="business_fetch_failed", business_code="90001")` |
| `"90002"` | `IFlowBusinessError(code="business_no_results", business_code="90002")` |
| `"90402"` | `IFlowAuthError(code="business_invalid_api_key")` |
| `"500"` | `IFlowAPIError(code="business_server_error")` |
| any other | `IFlowBusinessError(code="business_unknown", business_code=<code>)` |

When the HTTP status and the business code disagree (e.g. HTTP 200 with `code: "40303"`), **the body wins**. This matches observed API behavior and ensures consistent client-side handling regardless of upstream HTTP-status conventions.

### 8.5 `code` is a stable contract

The `code` attribute is a stable string identifier — consumers (especially adapters that serialize errors to JSON, such as an MCP tool result) should switch on `code` rather than rely on exception class identity. Class refinements may be added in future releases; the existing `code` strings remain backward-compatible.

---

## 9. Configuration

| Constant | Default | Notes |
|---|---|---|
| `DEFAULT_BASE_URL` | `https://platform.iflow.cn` | |
| `DEFAULT_TIMEOUT_S` | `30.0` | applied per request |
| `ENV_API_KEY` | `IFLOW_API_KEY` | only source for the credential outside an explicit constructor arg |
| `DEFAULT_SOURCE` | `python` | |
| `DEFAULT_INTEGRATION_NAME` | `iflow-search` | |
| `MAX_ERROR_BODY_BYTES` | `500` | bounds memory under hostile or large 5xx bodies |

The API key is read from `os.environ["IFLOW_API_KEY"]` only — never from a `.env` file, never from a CLI flag, never from any filesystem path. This rule applies to the SDK itself, to the smoke script, and to any future adapter.

---

## 10. Testing

All tests run **offline** — no real API call, ever.

Mechanism: `tests/conftest.py` exposes `make_mock_transport`, which wraps `httpx.MockTransport` and records every outbound request as a `CapturedRequest`. Tests assert on the captured request shape (URL, headers, body) and feed back canned responses.

Fixture conventions:

- Every client in tests is constructed with an obvious placeholder string such as `"test-key"` or `"env-key-value"`. These are fake fixtures, not credentials.
- Canned responses are small inline Python literals, designed to exercise normalizer edge cases.

Test matrix (sync and async parallel where applicable):

| Layer | Coverage |
|---|---|
| Headers | required headers and values; MCP conditional rules; no key leakage outside `Authorization` |
| Requests | payload renames (`query→keywords`, `count→num`); `count=None` omits `num`; `url` payload shape |
| Responses | normalized shape; `took_ms > 0`; `url` (not `link`); bare-array image data; defensive coercion |
| Errors (HTTP) | 401 / 403 / 429 / 500 / 502, 2xx-non-JSON; each mapped to the correct exception + `code` |
| Errors (business) | each documented business code mapped; unknown code yields `business_unknown` with preserved `business_code` |
| Timeouts | `httpx.TimeoutException` → `IFlowTimeoutError`; cancellation propagates unchanged |
| Config | env-var read, explicit-arg precedence, missing-key error; MCP name / version regex validation; orphan MCP version rejected |
| Redaction | `<unset>`, `***`, partial-tail formats |

The smoke script `scripts/smoke_real_api.py` exercises the three endpoints against the real API. It is **opt-in** via `IFLOW_SMOKE=1`, reads the key from `os.environ` only, never writes to disk, and redacts the key in all log output.

---

## 11. Versioning and release

- Initial version: `0.1.0a0` (PEP 440 prerelease). `pip install iflow-search` returns "no matching distribution" until a non-prerelease lands; users must `pip install --pre iflow-search`. This is intentional — it provides the same opt-in surface as npm's `next` dist-tag.
- Publishing is manual. CI runs lint, typecheck, and tests; it does not upload to any registry.

### 11.1 Pre-publish checklist

```
[ ] git status clean
[ ] HEAD pushed; CI green
[ ] ruff check .                              → no findings
[ ] mypy src/iflow_search                     → no findings
[ ] pytest                                    → all green
[ ] python -m build                           → sdist + wheel produced
[ ] inspect sdist (tar tf dist/*.tar.gz):
      must contain: pyproject.toml, src/, README.md, LICENSE
      must NOT contain: .env, __pycache__/, tests/, scripts/
[ ] inspect wheel (unzip -l dist/*.whl):
      must contain: iflow_search/*.py, iflow_search-*.dist-info/{METADATA,RECORD,WHEEL}
      must NOT contain: tests/, scripts/, .env
[ ] secret scan over diff and working tree    → no matches
[ ] twine check dist/*                         → PASSED
[ ] upload to TestPyPI; cold-install into a fresh /tmp venv; smoke-import the package
[ ] upload to PyPI
```

### 11.2 Secret-leak protocol

If a real API key ever leaks into a published artifact: rotate the key at the iFlow platform first, *then* yank the affected PyPI release, then publish a fix. PyPI does not permit delete-and-republish of the same version, so the fix is always a new version.

---

## 12. Release verification — 0.1.0a0

This section records the evidence we *do* have for the `0.1.0a0` PyPI release of `iflow-search`, and is explicit about what was **not** captured at release time. It is meant to be the template for the stable `0.1.0` release record, at which point the gaps below must be filled in before the upload step.

### 12.1 Artifacts

- Published on PyPI as `iflow-search 0.1.0a0` (sdist + wheel).
- Reachable via `pip install --pre iflow-search==0.1.0a0`.
- **sha256 of the published sdist / wheel: not recorded at release time.** Future stable bumps must capture these from `python -m build` output and pin them in this section before upload.

### 12.2 CI gate

- The pre-publish branch passed the standard CI matrix (`ruff check`, `mypy src/iflow_search`, `pytest`, `python -m build`) across Python 3.10 – 3.13, per `.github/workflows/ci.yml`. The exact run URL was not pinned in this document.

### 12.3 Cold-install matrix

- **Not recorded at release time.** The pre-publish checklist (§11.1) requires a TestPyPI cold-install into a fresh `/tmp` venv, but the matrix (which Python versions / which OS) was not pinned. Future stable bumps must record the Python × OS combinations that were exercised cold.

### 12.4 Real-API smoke

- A real-API smoke is shipped at `scripts/smoke_real_api.py`, gated behind `IFLOW_SMOKE=1`, and documented in the package README (`packages/iflow-search/README.md` § "Real-API smoke"). It exercises `web_search`, `image_search`, and `web_fetch` end-to-end against the live iFlow platform.
- Per the same README, the script is opt-in, reads `IFLOW_API_KEY` from the environment only, redacts the key in all log output, and does not write any file.
- The release-time output of this script was not captured in this repository.

### 12.5 Tag

- Git tag for this release: bare `v0.1.0a0`, per the tag convention (core uses bare; adapters use `<pkg>/v<version>`).
- Tagged commit: `46742b9`, dated 2026-05-22.

### 12.6 Constraints honoured

- API key was read from `os.environ` only; no `.env` autoloading, no CLI flag, no filesystem path other than the process environment, per architectural invariant #7.
- `~/.pypirc` was not read by any in-repo automation. Upload credentials were supplied by the operator out of band.
- No `Co-Authored-By: Claude` trailer was added to the release commit.
