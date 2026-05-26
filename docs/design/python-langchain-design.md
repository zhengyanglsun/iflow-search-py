# `iflow-search-langchain` — Python LangChain adapter design

Companion design document for the **`iflow-search-langchain`** package, a LangChain (and LangGraph) adapter for the iFlow Search API. Sibling to `iflow-search` (the core SDK, see `python-sdk-design.md`) and `iflow-search-mcp` (the MCP stdio server, see `python-mcp-design.md`). This document covers v0.1.0a0.

The package wraps `iflow-search`'s `IFlowSearchClient` and `AsyncIFlowSearchClient` in three LangChain `BaseTool` subclasses (`iflow_web_search`, `iflow_image_search`, `iflow_web_fetch`) exposed through four factory functions. It does not introduce new HTTP, attribution, or error-handling logic — every architectural invariant of the core SDK applies unchanged.

## 1. Scope

In scope for v0.1.0a0:

- Three LangChain `BaseTool` subclasses, one per iFlow Search endpoint, exposed via the factory functions in §5.
- Both sync (`_run`) and async (`_arun`) execution paths on every tool, each using the matching core client type.
- Pydantic v2 args schemas that match the core SDK's Python-side parameter names (`query`, `count`, `url`).
- `response_format = "content_and_artifact"` return shape: short LLM-facing text plus a JSON-serializable artifact carrying the full normalized response.
- Attribution headers (`IFlow-Source`, `IFlow-Integration`, `IFlow-Integration-Version`) set by the factories when they auto-build clients.
- A LangGraph usage example in the README.

Out of scope for v0.1.0a0:

- `BaseRetriever` / `BaseLoader` / `BaseToolkit` integrations. The package ships tools only.
- Chains, prompts, output parsers, or any LangChain Expression Language helpers.
- A separate `iflow-search-langgraph` package. LangGraph is supported by reusing the LangChain tools returned by the factories below (LangGraph consumes LangChain tools directly). A separate package is not currently planned.
- A CLI entry point. The package is a library only.
- Streaming. iFlow Search is request/response; pretending otherwise would be dishonest.
- Bundled LLM-provider integrations (OpenAI, Anthropic, etc.). The adapter is policy-free and provider-free.
- LangSmith-specific code. LangChain's built-in callbacks handle tracing without our involvement; the artifact preserves `took_ms` for downstream consumers.

## 2. Distribution

| Attribute | Value |
|---|---|
| PyPI name | `iflow-search-langchain` |
| Module name | `iflow_search_langchain` |
| Version (initial) | `0.1.0a0` (PEP 440 prerelease — requires `pip install --pre`) |
| Console scripts | none |
| License | MIT |

The `iflow-search-*` family is the convention for adapters originating in this repository. The `langchain-<vendor>` partner-package convention (e.g. `langchain-openai`) was considered but rejected to keep the family naming consistent with `iflow-search`, `iflow-search-mcp`, and the planned `iflow-search-openapi`. See §15.2.

## 3. Python version and runtime dependencies

```toml
[project]
requires-python = ">=3.10"
dependencies = [
    "iflow-search>=0.1.0a0,<0.2",
    "langchain-core>=1.0,<2.0",
    "pydantic>=2.7,<3.0",
]
```

- `requires-python = ">=3.10"` — same baseline as the core and the MCP adapter.
- `iflow-search>=0.1.0a0,<0.2` — the adapter depends on the core for HTTP, attribution, error mapping, and response normalization. Bumping past `0.2.0` is a deliberate compatibility event.
- `langchain-core>=1.0,<2.0` — targets the modern (1.x) `BaseTool` surface. This deliberately excludes pre-1.0 LangChain installs; callers still on 0.3.x can pin an older release if one ever exists. See §15.3.
- `pydantic>=2.7,<3.0` — explicit even though `langchain-core` already requires it, because this adapter defines its own pydantic `BaseModel` args schemas and tests assert their constraints directly. Listing the dep makes that ownership obvious and avoids relying on a transitive pin.

The adapter does **not** depend on `langchain`, `langchain-community`, or `langgraph`. LangGraph users bring their own `langgraph` install.

Dev/test dependencies include `httpx` explicitly (in addition to whatever is brought transitively via `iflow-search`), so the test suite can use `httpx.MockTransport` without relying on a transitive dependency by accident. See §13.

## 4. Repository layout

```
packages/iflow-search-langchain/
├── src/iflow_search_langchain/
│   ├── __init__.py        # public re-exports: four factories + __version__
│   ├── _version.py        # __version__ = "0.1.0a0"
│   ├── _constants.py      # SOURCE, INTEGRATION_NAME (private attribution constants)
│   ├── _schemas.py        # WebSearchArgs / ImageSearchArgs / WebFetchArgs (pydantic v2)
│   ├── _tools.py          # private BaseTool subclasses (one per endpoint)
│   ├── _factories.py      # public factory functions
│   └── _format.py         # LLM-facing content summary builders
├── tests/                 # offline only — httpx.MockTransport
├── scripts/
│   └── smoke_real_api.py  # opt-in live smoke; gated by IFLOW_LANGCHAIN_SMOKE=1
├── pyproject.toml
├── README.md              # PyPI long_description; includes a LangGraph usage example
└── LICENSE
```

Module-name conventions:

- Public re-exports live in `__init__.py`. Everything else has a leading underscore.
- `_constants.py` exists specifically so that no string literal for `"langchain"` or `"iflow-search-langchain"` ever appears outside that one module. Factories read from `_constants` and `_version` and forward the values into core-client constructor kwargs (§11).

## 5. Public API surface

Public symbols, re-exported from `iflow_search_langchain.__init__`:

```python
__all__ = [
    "create_iflow_web_search_tool",
    "create_iflow_image_search_tool",
    "create_iflow_web_fetch_tool",
    "create_iflow_search_tools",
    "__version__",
]
```

That is the full public surface. The `BaseTool` subclasses (`_WebSearchTool`, `_ImageSearchTool`, `_WebFetchTool` or similar) live in `_tools.py` and are private; their class identity is not part of the compatibility contract. The factory return type is annotated as `BaseTool` (from `langchain_core.tools`).

**Import-time behavior.** `import iflow_search_langchain` performs no I/O, reads no environment variables, and constructs no clients. Every side effect is deferred to factory invocation. This matters for hosts that import the package at startup but only build tools per-request.

## 6. Tool registry

All three tool names match the MCP adapter (`python-mcp-design.md` §7) and the JS sibling `@iflow-ai/search-langchain`. Consistency across adapters reduces prompt-engineering surprises when the same agent fleet uses more than one.

| Tool name | Core SDK call | Args schema |
|---|---|---|
| `iflow_web_search` | `client.web_search(query=, count=)` | `WebSearchArgs` |
| `iflow_image_search` | `client.image_search(query=, count=)` | `ImageSearchArgs` |
| `iflow_web_fetch` | `client.web_fetch(url=)` | `WebFetchArgs` |

## 7. Args schemas

Defined in `_schemas.py` as pydantic v2 `BaseModel` subclasses. The snippet below shows the validation constraints; per-field descriptions (which become part of the LLM-visible tool schema alongside the per-tool description in §8) are omitted here and documented separately:

```python
from pydantic import BaseModel, Field

class WebSearchArgs(BaseModel):
    query: str = Field(..., min_length=1)
    count: int | None = Field(None, ge=1)

class ImageSearchArgs(BaseModel):
    query: str = Field(..., min_length=1)
    count: int | None = Field(None, ge=1)

class WebFetchArgs(BaseModel):
    url: str = Field(..., min_length=1)
```

### 7.1 Wire-format renames inherited from core

The Python-side names are `query` / `count` / `url`. The core SDK rewrites them to wire `keywords` / `num` / `url` (the latter unchanged); the adapter does not see or duplicate those renames. This is the same contract the core's own README documents and the same one that the MCP adapter relies on.

### 7.2 No client-side clamping

`count` is bounded from below (`ge=1`) only. There is intentionally no upper bound, no client-side ceiling, no `le=10`-style clamp. Per the core SDK's invariant (`python-sdk-design.md` §6.3 "Input validation"), the iFlow server is authoritative on `count` ceilings. If a caller passes `count=999`, the adapter forwards it untouched and the server's response is what determines the outcome.

### 7.3 Validation lives in LangChain, not in the adapter

LangChain validates inputs through `args_schema` before invoking the tool. The adapter does not duplicate validation inside `_run` / `_arun`. How validation errors are surfaced is controlled by LangChain / the caller's tool or agent configuration; the README may document a recommended `handle_validation_error` policy if needed.

## 8. Tool descriptions (LLM-facing)

Each tool's `description` attribute becomes part of the function-calling tool schema and is how the LLM picks between them. Initial copy:

- **`iflow_web_search`** — *"Search the public web for pages matching a query. Returns a ranked list of titles, URLs, snippets, and (when available) publication dates. Use for current events, references, product comparisons, or whenever you need URLs to ground an answer."*
- **`iflow_image_search`** — *"Search the public web for images matching a query. Returns image URLs and the page each image came from. Use when the user asks for pictures, diagrams, logos, or visual examples."*
- **`iflow_web_fetch`** — *"Fetch and extract the main readable content of a single web page by URL. Use when the user provides a URL or after `iflow_web_search` when you need the full text of a specific result."*

Descriptions are deliberately short, action-oriented, and disambiguate *when* each tool should be picked. They are part of the public LLM-visible surface but are not part of the Python ABI — copy may be revised in a minor release without API impact.

## 9. Return shape — `content_and_artifact`

Each `BaseTool` subclass sets `response_format = "content_and_artifact"`. `_run` and `_arun` return a `tuple[str, dict[str, Any]]`:

- **`content`** (the `str` half) — a short, LLM-friendly text summary built by `_format.py`. The format is deliberately terse to economize LLM context. Sketched format per tool:
  - `iflow_web_search`: `<N> results for "<query>":\n1. <title> (<url>) — <snippet ≤200 chars>\n…`
  - `iflow_image_search`: `<N> images for "<query>":\n1. <image_url> (from <source_url>)\n…`
  - `iflow_web_fetch`: `Title: <title>\nContent (<N> chars): <first 400 chars>…`
- **`artifact`** (the `dict` half) — `response.model_dump(mode="json")` on the core SDK's normalized response object. JSON-serializable, transport-safe, and preserves every field the SDK modeled — including `took_ms` and the original `raw` envelope. The `raw` field must round-trip intact so downstream callers can recover server fields the SDK did not promote.

### 9.1 Why both halves

`content` is what the LLM reads. `artifact` is what downstream nodes / chains read when they need structured data — e.g., a follow-up node that picks URLs from `artifact["results"]` and calls `iflow_web_fetch` on the top one. Discarding the artifact would force downstream code to re-invoke the SDK manually to recover the structured form.

### 9.2 Not used

- `return_direct=True` — the agent always sees the tool result and decides what to do next. Forcing direct return would short-circuit agent loops.
- Streaming. iFlow Search is request/response only.

## 10. Client lifecycle and factories

### 10.1 Why each tool needs both a sync and an async client

LangChain `BaseTool` ships both `_run` and `_arun`. If a tool only implements `_run`, LangChain's default falls back to invoking it from a threadpool when `ainvoke()` is called — which would silently violate the core SDK invariant ("Never run the sync client in a thread pool to satisfy an async caller — that deadlocks under FastAPI/asyncio"). Every adapter tool therefore implements both methods, and each method uses the matching client type. `_run` calls `IFlowSearchClient`. `_arun` calls `AsyncIFlowSearchClient`. There is no cross-delegation in either direction.

### 10.2 Single-tool factory signature

```python
def create_iflow_web_search_tool(
    *,
    api_key: str | None = None,
    base_url: str | None = None,
    timeout: float | None = None,
    client: IFlowSearchClient | None = None,
    async_client: AsyncIFlowSearchClient | None = None,
) -> BaseTool: ...
```

The three single-tool factories share this signature, differing only in which private `BaseTool` subclass they instantiate.

Factory-time logic, observable contract:

1. If `client is not None`: use it as-is. The factory does not mutate its `api_key`, `base_url`, `timeout`, or attribution — caller-supplied clients are taken verbatim.
2. If `client is None`: construct an `IFlowSearchClient` with the supplied `api_key` / `base_url` / `timeout` plus the attribution constants from §11. When `api_key is None`, the constructed client must follow the core SDK's documented env-loading path (e.g. a `from_env(…)` constructor if the core exposes one), or if that path does not support overrides cleanly, an adapter-side helper that reads `IFLOW_API_KEY` / `IFLOW_BASE_URL` / `IFLOW_TIMEOUT_MS` from the environment and then calls the normal constructor. The factory contract is: `api_key=None` falls back to `IFLOW_API_KEY` env.
3. Same auto-build vs passthrough logic for `async_client`.
4. Mixed inputs are supported: if the caller passes `client` but not `async_client` (or vice versa), the missing counterpart is auto-built using factory args / env.
5. The tool instance stores both clients.

### 10.3 `create_iflow_search_tools` — shared client pair

```python
def create_iflow_search_tools(
    *,
    api_key: str | None = None,
    base_url: str | None = None,
    timeout: float | None = None,
    client: IFlowSearchClient | None = None,
    async_client: AsyncIFlowSearchClient | None = None,
) -> list[BaseTool]:
    """Returns [web_search, image_search, web_fetch] sharing one sync + one async client."""
```

The returned list is in fixed order — `web_search`, `image_search`, `web_fetch` — to match the MCP adapter's `tools/list` order. Tests assert that order; downstream code may rely on it.

All three returned tools share the **same** underlying `IFlowSearchClient` and `AsyncIFlowSearchClient` instances. The caller gets one sync connection pool and one async pool, not three of each. This is the recommended setup path for agents that wire all three tools; the single-tool factories exist for callers who want only one or two.

### 10.4 Lifecycle

Auto-built clients are owned by the tool instance. v0.1.0a0 does not expose a public `close` / `aclose` method on tools. For long-running services that need deterministic cleanup, pass caller-managed clients and close them with the core SDK's context-manager / `close` APIs:

```python
async with AsyncIFlowSearchClient(...) as ac:
    tools = create_iflow_search_tools(async_client=ac)
    # ... use agent ...
```

The implementation may lazily construct sync and/or async clients to avoid creating ones the caller will never use, but the public factory contract above is unchanged. In particular, config-error fail-fast semantics still apply per §12.3.

## 11. Attribution

### 11.1 Auto-built clients

When the factory constructs a client itself, it passes:

| Constructor kwarg | Value | Source |
|---|---|---|
| `source` | `"langchain"` | `_constants.SOURCE` |
| `integration_name` | `"iflow-search-langchain"` | `_constants.INTEGRATION_NAME` |
| `integration_version` | current package version | `_version.__version__` |

`User-Agent` and the `IFlow-Integration-Version` header are derived inside the core client from those kwargs. The factories never construct raw header dicts; that responsibility belongs exclusively to `iflow-search._attribution`.

### 11.2 Caller-supplied clients

When the caller passes a pre-built `client` or `async_client`, **the factory does not override that client's attribution headers**. Mutating a caller-supplied client would violate the core's single-source-of-truth rule for `_attribution.py`. Whatever `source` / `integration_name` / `integration_version` the caller's client was built with is what reaches the iFlow backend.

This has a telemetry implication that the README must document loudly: a caller who passes a bare `AsyncIFlowSearchClient()` (no attribution overrides) will land in iFlow's usage statistics as `source="python"` (the core's default), not `source="langchain"`. Callers who want their LangChain-driven traffic correctly attributed should either:

- Let the factory build the client (recommended; attribution is automatic), or
- Construct the client themselves with the same attribution kwargs and pass it in.

## 12. Error model and cancellation

### 12.1 Pass-through, not wrapping

The adapter does not wrap, remap, or invent error types. `_run` and `_arun` let `IFlowError` subclasses from the core SDK propagate as raised, with their `code` strings and attributes intact. The stable `code` contract (`api_unauthorized`, `business_rate_limited`, `business_insufficient_credits`, etc.) flows end-to-end: an agent or `RunnableRetry` policy can switch on `exc.code` regardless of which adapter the error originated in.

Concrete propagation expectations:

| Cause | Exception raised from `_run` / `_arun` |
|---|---|
| HTTP 401 / 403, business `90402` | `IFlowAuthError(code="api_unauthorized")` |
| HTTP 429, business `40303` | `IFlowRateLimitError(code="business_rate_limited")` |
| Business `60400` | `IFlowInsufficientCreditsError(code="business_insufficient_credits")` |
| HTTP 5xx, non-JSON 2xx, other non-2xx | `IFlowAPIError` |
| SDK-initiated timeout | `IFlowTimeoutError` |
| DNS / connection / TLS error | `IFlowNetworkError` |
| Bad args (empty `query`, missing `url`, `count < 1`) | `pydantic.ValidationError` raised by LangChain's `args_schema` validation **before** `_run`/`_arun` is invoked (see §7.3) |

### 12.2 Cancellation — `asyncio.CancelledError` propagates unwrapped

The core SDK guarantees that `asyncio.CancelledError` is never caught or wrapped — it propagates as itself so cooperative cancellation keeps working. The adapter inherits this guarantee by not adding any `except BaseException:` or `except Exception:` blocks around the client calls. `_arun` is implemented as `return await self._async_client.web_search(...)` plus the `_format` step on success; there is no exception handler to interfere.

This matters for production deployments: LangGraph's `ToolNode` and `asyncio.wait_for(...)` around agent invocations rely on `CancelledError` actually propagating to cancel in-flight work.

### 12.3 Where `IFlowConfigError` surfaces

`IFlowConfigError` (missing API key, invalid attribution) is an observable contract about **when** it raises, not just whether:

- **Auto-build path** (factory needs to build the missing client): if `api_key` is not supplied and `IFLOW_API_KEY` is not in the environment, the factory call raises `IFlowConfigError` — agent setup fails fast, before any LLM round-trip.
- **Both clients supplied**: if the caller passes both `client` and `async_client`, the factory uses them as-is and does not require `IFLOW_API_KEY`. This is the deliberate path for environments that have no `IFLOW_API_KEY` env var by design.
- **One client supplied**: env / `api_key` validation applies only to the auto-built counterpart. The supplied client is taken verbatim.

This contract is preserved even under the §10.4 lazy-construction implementation note: lazy implementations must still validate api-key eagerly (e.g., by running the same validation that the core constructor runs, or by eagerly constructing at least one client). Tests will assert that missing-api-key raises at factory call time, not at first tool invocation.

### 12.4 What the adapter does not do

- **No `ToolException` wrapping.** LangChain's `ToolException` is a marker that opts an exception into the `handle_tool_error` flow with custom formatting. The adapter does not use it — `IFlowError` carries everything an agent needs (`code`, `message`, `request`, `response_body_truncated`), and forcing `ToolException` would hide the original type from callers who want to `except IFlowAuthError:` specifically.
- **No `handle_tool_error` set on the tools.** That is the caller's agent-level policy, not the adapter's. Caller-side LangChain / agent configuration controls whether tool exceptions propagate or are converted into tool messages. The adapter itself does not set `handle_tool_error`.
- **No re-validation inside `_run` / `_arun`.** LangChain has already validated args against `args_schema`. Adding a second layer would be dead code.
- **No stdout / stderr logging from inside the tool body.** Observability is the agent framework's job (LangSmith callbacks, etc.). The adapter is silent.

## 13. Testing

### 13.1 Offline only, by default

Tests are fully offline and use `httpx.MockTransport` only. No real network, no real API key, no live iFlow endpoint. `tests/conftest.py` provides:

- `make_mock_transport` — returns `(transport, captured_requests)` so tests can assert on outbound request shape (URL, body, headers).
- `make_mock_async_client` / `make_mock_sync_client` — build `AsyncIFlowSearchClient(api_key="test-key", http_client=httpx.AsyncClient(transport=…))` and the sync equivalent, pre-wired with attribution kwargs so attribution-header tests can prove which `source` / `integration_name` reaches the wire.
- `make_envelope` — wrap canned response dicts in iFlow's `{success, code, message, data, …}` envelope.

Tests call the public factories with mock clients via `client=` / `async_client=` and exercise the tool's `_run` / `_arun` methods.

### 13.2 Test file layout

| File | Covers |
|---|---|
| `tests/conftest.py` | shared fixtures (above) |
| `tests/test_factories.py` | factory contracts from §10 and §12.3: `api_key` / env handling, caller-supplied client passthrough, shared-client behavior across the three tools, fail-fast `IFlowConfigError` matrix (the three §12.3 cases) |
| `tests/test_schemas.py` | args-schema correctness: `query` / `url` `min_length=1` reject empty strings, `count` `ge=1` rejects `0`, no upper bound enforced |
| `tests/test_tools_sync.py` | `_run` for all three tools: request body (Python→wire renames `query→keywords`, `count→num`), URL, captured headers; return-tuple shape and `content` / `artifact` contents |
| `tests/test_tools_async.py` | mirror of `test_tools_sync.py` against `_arun` |
| `tests/test_attribution.py` | auto-built path emits `IFlow-Source: langchain`, `IFlow-Integration: iflow-search-langchain`, `IFlow-Integration-Version: <__version__>`. Caller-supplied client preserves *its* attribution (e.g. passing a client built with `source="custom"` results in `IFlow-Source: custom`, not `langchain` — proves §11.2's "we do not mutate" rule) |
| `tests/test_errors.py` | error pass-through: 401 → `IFlowAuthError`, 429 → `IFlowRateLimitError`, 5xx → `IFlowAPIError`, business `60400` → `IFlowInsufficientCreditsError`. Parametrized over status × business-code |
| `tests/test_cancellation.py` | inside an asyncio task, the mock transport blocks; cancel the task mid-flight; assert the raised exception is exactly `asyncio.CancelledError` and not anything wrapped |
| `tests/test_import.py` | `import iflow_search_langchain` with no env and no `IFLOW_API_KEY`: no exception, no HTTP, no client construction. Factory call without `api_key` in env *does* raise per §12.3 |
| `tests/test_langchain_contract.py` | the tool is a valid `BaseTool` — see §13.3 |

Test count target: ~50–70 offline tests, comparable to `iflow-search`'s 103 and `iflow-search-mcp`'s similar order.

`asyncio_mode = "strict"` per `pyproject.toml`; every async test is marked `@pytest.mark.asyncio`.

### 13.3 What `test_langchain_contract.py` asserts (and avoids)

`langchain-core` 1.x is a moving surface internally. The contract tests assert only the stable, externally documented contract:

- `tool.name` matches the spec.
- `tool.description` is non-empty and matches the spec.
- `tool.args_schema` is a pydantic v2 `BaseModel` subclass with the constraints from §7.
- Direct `tool.invoke({"query": "..."})` returns the expected content behavior (`response_format="content_and_artifact"` means `invoke` returns the content string).
- ToolCall-style invocation preserves the artifact, if and as supported by the installed `langchain-core` version.

The tests deliberately do **not** make brittle assertions about every field of the generated JSON tool schema unless a specific field is part of the public contract. Over-snapshotting LangChain internals would make this suite a tax on every `langchain-core` 1.x point release.

### 13.4 Explicit dev / test dependencies

The test suite imports `httpx` directly to build `MockTransport` instances. `httpx` is added explicitly to `[project.optional-dependencies].dev`, even though it is transitively present via `iflow-search`. Relying on a transitive dependency for direct imports is a latent break; the explicit listing prevents it.

### 13.5 What we explicitly do not test

- The core SDK's error mapping logic (covered in `iflow-search` tests). Error tests here prove that **the adapter doesn't interfere** — given the core mapped a wire response to `IFlowAuthError`, the adapter surfaces it unchanged through the tool boundary.
- LangChain's args-validation machinery. The schema tests prove constraints; they do not re-validate pydantic itself.
- The `_format` helpers in isolation beyond a few snapshot-style assertions; their output appears directly in the `content` half of `_run` / `_arun` returns, so the tool-level tests cover them transitively.
- Anything against a real LLM provider. No mock LLM in an agent loop. The contract proved is "this tool is shaped correctly for LangChain to consume," not "LLMs choose it correctly" — the latter is a prompt-engineering concern outside the adapter's scope.

### 13.6 Real-API smoke (opt-in, never in CI)

`scripts/smoke_real_api.py`, gated by `IFLOW_LANGCHAIN_SMOKE=1`. Same posture as the core's `IFLOW_SMOKE=1` and the MCP adapter's `IFLOW_MCP_SMOKE=1`: without the explicit env opt-in, the script refuses to run.

What it does:

1. Builds the three tools via `create_iflow_search_tools(api_key=os.environ["IFLOW_API_KEY"])`.
2. Invokes each tool once with a fixed innocuous query / URL.
3. Asserts the returned `content` is a non-empty string and the `artifact` is a `dict` whose `raw` key is preserved (proving end-to-end normalization).
4. Prints a brief summary. The API key is redacted in every log line.
5. Does not write any file. Does not import LangGraph or any LLM provider.

No LangGraph end-to-end smoke in v0.1.0a0 — that would require either a mock LLM (brittle, not what is being tested) or a real LLM provider (paid, key-handling complexity, not the adapter's contract). Documented as a non-goal here.

## 14. CI and release

### 14.1 CI extends the existing workflow

Following the same convention the MCP adapter adopted (`python-mcp-design.md` §13.3 "CI extends the existing matrix; no new workflow"), `.github/workflows/ci.yml` gains a third `working-directory:` block per gate, pointed at `packages/iflow-search-langchain`. Gates per package: `pytest`, `ruff check`, `ruff format --check`, `mypy --strict`, `python -m build`. Python matrix: 3.10 / 3.11 / 3.12 / 3.13.

No real `IFLOW_API_KEY` is supplied to CI. No `IFLOW_LANGCHAIN_SMOKE` flag is set in CI. The opt-in smoke is local-only.

`langchain-core` version pin in CI is whatever resolves at install time within the `>=1.0,<2.0` range; no multi-version matrix in v0.1. Adding one is straightforward later if the surface starts to see meaningful 1.x churn.

### 14.2 Publishing

Publishing is **not** automated. CI runs lint / typecheck / tests / build only — no `twine upload` from any workflow. The publish pre-flight is the same checklist that `python-mcp-design.md` §14 established for the MCP adapter:

1. Build `dist/` once locally with `python -m build`.
2. Capture sha256 of both wheel and sdist.
3. Upload to TestPyPI first; cold-install in a fresh `/tmp` venv with `pip install --pre --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple/`; verify the wheel's sha256 matches the local hash via the TestPyPI JSON API.
4. Run an opt-in real smoke from that venv (LangChain agent harness consuming the adapter; same `IFLOW_LANGCHAIN_SMOKE=1` script as §13.6).
5. Upload to PyPI without rebuilding; verify byte-identical sha256 against PyPI's JSON API.
6. Repeat the cold-install + smoke from PyPI.
7. Tag with the namespaced convention: `iflow-search-langchain/v0.1.0a0`. Push the tag only.

## 15. Design decisions

### 15.1 Tools only — no Retriever, Loader, or Toolkit in v0.1

`BaseTool` is the smallest, most universally-consumed LangChain primitive: every agent loop, `create_react_agent`, `ToolNode`, and assistant-style chain consumes tools. Adding `BaseRetriever` would also be reasonable (web_search → RAG chain), but doing so means picking a `Document` mapping (which iFlow field becomes `page_content`? which becomes `metadata`?), more tests, and another compatibility contract. `BaseLoader` for `web_fetch` is plausible but is one-line glue most callers can write themselves. A `BaseToolkit` class would force most consumers through an extra hop they don't need. Tools-only keeps the surface small enough to ship cleanly; the other surfaces can be added in a minor release if a concrete user asks.

### 15.2 Package name follows the `iflow-search-*` family, not the `langchain-<vendor>` convention

The LangChain community convention for partner packages is `langchain-<vendor>` (e.g. `langchain-openai`, `langchain-anthropic`). The repo's own family convention is `iflow-search-*` (sibling to `iflow-search`, `iflow-search-mcp`, `iflow-search-openapi`). The latter wins here: someone who has just `pip install --pre iflow-search` and `iflow-search-mcp` will obviously try `pip install --pre iflow-search-langchain` next. A dual-name strategy (both PyPI projects, alias metapackage) was considered and rejected — it would double release operations for marginal discoverability gain.

### 15.3 `langchain-core>=1.0,<2.0` (modern only)

`langchain-core` 1.0 GA shipped in late 2025 and is mature. Pinning to 1.x only lets the adapter use the stable `BaseTool` surface — `response_format="content_and_artifact"`, modern pydantic v2 args schema handling, current tool-call wiring — without version-conditional code. Supporting 0.3.x in addition was considered (matching the JS sibling's `^0.3.0 || ^1.0.0` posture) but rejected: some `BaseTool` features evolved between 0.3 and 1.0, and avoiding them or shimming around them is real maintenance tax for the benefit of a shrinking install base. Including future 2.x was also rejected; that's a promise the adapter cannot keep without verifying against an unreleased library.

### 15.4 Factory functions, not class exports or a Toolkit

Factory functions (`create_iflow_*_tool(...)`) mirror the JS sibling's API 1:1, minimize the public surface that becomes a compatibility contract (the private `BaseTool` subclasses can be refactored without breaking callers), and naturally accommodate the shared-client pattern in `create_iflow_search_tools`. Exporting the `BaseTool` subclasses directly was considered (idiomatic for some LangChain built-ins like `TavilySearchResults`) but rejected because class identity then becomes the contract — refactoring the class hierarchy would be a major bump. A toolkit class was considered and rejected as the heaviest abstraction with no current consumer demand.

### 15.5 Both `_run` and `_arun` always; no sync/async cross-delegation

The core SDK's invariant forbids running the sync client in a thread pool to satisfy an async caller (FastAPI/asyncio deadlocks). LangChain `BaseTool`'s default behavior — if only `_run` is defined, `_arun` invokes it in a threadpool — would silently violate that. Every tool therefore implements both, each method using the matching client type.

### 15.6 `create_iflow_search_tools` shares one sync + one async client pair

Three tools wired into one agent should reuse one connection pool per direction, not three. Sharing the client pair across the three returned tools is the path of least surprise and the one that minimizes httpx overhead in the common case (agent has all three tools available). Single-tool factories exist for the asymmetric case (caller only wants `web_search`).

### 15.7 Caller-supplied clients keep their own attribution

If the caller passes a pre-built `client` or `async_client`, the factory does not mutate it. This is forced by the core's single-source-of-truth rule for `_attribution.py` — the adapter cannot reach inside another module's client to rewrite headers. The telemetry consequence (caller's bare `AsyncIFlowSearchClient()` lands as `source="python"`, not `langchain`) is documented in §11.2 and in the README.

### 15.8 `content_and_artifact` return shape

Discarding structured data on every tool call would force downstream chains to re-invoke the SDK manually whenever they need URL lists, image references, or `took_ms`. `content_and_artifact` preserves both halves at zero serialization cost (the artifact is already a `dict` from `model_dump(mode="json")`). It mirrors the JS sibling's two-part return and the MCP adapter's `content` + `structuredContent` split.

### 15.9 No streaming, no `return_direct`

iFlow Search is request/response only — streaming would be cargo-cult. `return_direct=True` would short-circuit the agent loop, hiding tool output from the LLM; that is a caller-side policy choice if anyone wants it, not an adapter default.

### 15.10 No separate LangGraph package, no LangSmith-specific code

LangGraph consumes LangChain tools directly through `create_react_agent` and `ToolNode`. A separate `iflow-search-langgraph` package would just re-export the same factories. The README's LangGraph example makes the integration concrete. A separate package is not currently planned.

LangSmith tracing happens automatically through LangChain's `BaseTool` callbacks; no adapter-specific code is needed. The `took_ms` field in the artifact gives downstream callers exact server-call timing if they want it.

### 15.11 Adapter-only real smoke; no LLM provider coupling

The smoke script invokes each tool directly against the live API and verifies the `(content, artifact)` shape. It does not build a `create_react_agent`, does not import any LLM provider, and does not assume any tool-calling LLM is reachable. The adapter's contract is "this tool is shaped correctly for LangChain to consume"; whether a given LLM picks the right tool is the user's prompt-engineering concern, downstream of this contract.

## 16. Release verification — `0.1.0a0` (2026-05-24)

Record of what was verified for the first published release of `iflow-search-langchain`. Kept here so future maintainers can see what the bar was and where the artifacts came from. Mirrors §14 of the MCP design doc.

### 16.1 Artifacts

Both files were built once locally with `python -m build` from commit `4270538` and uploaded byte-identically to TestPyPI and then PyPI. No rebuild between hops.

| Artifact | Size | sha256 |
|---|---|---|
| `iflow_search_langchain-0.1.0a0-py3-none-any.whl` | 11,929 B | `5d33ca3638fb7cfe10bdaac0eef14c97f352e81a1c62ce3ec45f71176efe49f8` |
| `iflow_search_langchain-0.1.0a0.tar.gz` | 8,879 B | `2458692a2ace01e7f1550ae01a79a488acf1ac7d31e012c327d117c8c74b5e00` |

Hashes were compared against the `digests.sha256` field returned by the TestPyPI and PyPI JSON APIs (`/pypi/iflow-search-langchain/0.1.0a0/json`) at each hop. All four digests match.

### 16.2 CI gate

GitHub Actions run [`26359768591`](https://github.com/zhengyanglsun/iflow-search-py/actions/runs/26359768591) on commit `4270538` was the green CI that unblocked the publish flow. It exercised the full package matrix:

| Package | Python versions | Result |
|---|---|---|
| `iflow-search` | 3.10 / 3.11 / 3.12 / 3.13 | ✅ |
| `iflow-search-mcp` | 3.10 / 3.11 / 3.12 / 3.13 | ✅ |
| `iflow-search-langchain` | 3.10 / 3.11 / 3.12 / 3.13 | ✅ |

12/12 jobs ran ruff, mypy strict, pytest, and `python -m build`. No CI job uploads anywhere — publishing is manual `twine upload` only (§14.2).

The preceding push (`05efdbf`) had failed CI on `iflow-search-langchain, py3.10` because `tests/test_version.py` used the 3.11-only stdlib `tomllib`. Fix `4270538` added `tomli>=2.0; python_version<'3.11'` to the dev extras and gated the import on `sys.version_info >= (3, 11)`. No other package's tests touch `tomllib`; this gotcha is langchain-only because only this adapter's tests assert the published `__version__` matches `pyproject.toml`.

### 16.3 Cold-install matrix

For each source, a fresh Python 3.12 venv was created in `/var/folders/.../iflow-langchain-*`, the package was installed with `pip install --pre iflow-search-langchain==0.1.0a0`, and both an **offline import smoke** (no `IFLOW_API_KEY` set) and the **real-API smoke** (`scripts/smoke_real_api.py` with `IFLOW_LANGCHAIN_SMOKE=1`) were run.

| Source | Index URL | Offline smoke | Real-API smoke |
|---|---|---|---|
| Local wheel | `file:///…/packages/iflow-search-langchain/dist/` | ✅ | ✅ (from source tree) |
| TestPyPI | `https://test.pypi.org/simple/` + PyPI as `--extra-index-url` for deps | ✅ | ✅ (from cold venv) |
| PyPI | default index | ✅ | ✅ (from cold venv) |

The TestPyPI install uses PyPI as `--extra-index-url` because the runtime dependency `iflow-search==0.1.0a0` only exists on PyPI; TestPyPI cannot resolve it on its own. The same reasoning applies to `langchain-core` and `pydantic`.

Offline smoke asserted: `import iflow_search_langchain` succeeds with no API key set, `__all__` exposes exactly the four factories plus `__version__`, and `create_iflow_web_search_tool()` raises `IFlowConfigError(code="missing_api_key")` at factory-call time rather than at first invocation.

### 16.4 Real-API smoke — what was verified end-to-end

`scripts/smoke_real_api.py` exercised all three tools against the live iFlow API from each venv. The script reads `IFLOW_API_KEY` from the environment only, redacts the key in all log output (first 4 chars + `***` + last 2), writes no files, and refuses to run without `IFLOW_LANGCHAIN_SMOKE=1`.

Per §15.11, the smoke does **not** build an agent and does **not** import LangGraph or any LLM provider. What it verifies is the adapter contract:

- `iflow_web_search._run(query="hello world", count=2)` → 2 results, non-empty `(content, artifact)` tuple with `artifact["raw"]` present.
- `iflow_image_search._run(query="cat", count=2)` → 2 images, `artifact["images"]` populated.
- `iflow_web_fetch._run(url="https://example.com")` → `artifact["title"] == "Example Domain"`.

All three passed from the source tree, the TestPyPI cold venv, and the PyPI cold venv (9 successful tool invocations total against the live API).

### 16.5 Attribution headers on the wire

The offline test suite (`tests/test_attribution.py`) already proves that auto-built clients emit `IFlow-Source: langchain`, `IFlow-Integration: iflow-search-langchain`, `IFlow-Integration-Version: 0.1.0a0` against an `httpx.MockTransport` recorder, and that caller-supplied clients pass through unchanged (per §11.2). The live smoke would have failed with `IFlowAuthError` if attribution had broken the request — it succeeded, confirming the headers reached the server end-to-end.

### 16.6 Tag convention

A namespaced git tag was created and pushed for this release, matching the `iflow-search-mcp` precedent (§14.5 of the MCP design):

```
iflow-search-langchain/v0.1.0a0  →  commit 4270538
```

The convention `<package-name>/v<version>` is now established for every package in this monorepo. The legacy unnamespaced `v0.1.0a0` tag remains in place for the core `iflow-search` release.

### 16.7 Constraints honoured throughout

- No real API key was ever written to the repository, committed to git, or printed to stdout. The smoke output shows only the redacted form `sk-e***16`.
- No `.env` file or other on-disk credential store was introduced. `IFLOW_API_KEY` was sourced from the developer's shell environment only.
- The wheel and sdist uploaded to PyPI are bit-for-bit identical to the local `dist/` artifacts; the four sha256 digests (local / TestPyPI / PyPI for each of wheel and sdist) all match.
- No CI workflow was modified to publish. Every upload to TestPyPI and PyPI was a manual, audited `twine upload`.
- `~/.pypirc` was created and edited by the developer in their own editor with tokens never entering tool I/O; the only filesystem checks performed against it were `test -f` and `stat -f %A` (mode = 600), never `cat` / `head` / `less` / `grep`.
- `DEEPSEEK_API_KEY` was not read at any point in the release flow; the LangChain adapter has no LLM-provider coupling (§15.11).
- Release commits omit the `Co-Authored-By: Claude` trailer per the repository's commit-message convention.

## 17. Release verification — `0.1.0` stable (2026-05-26)

Record of what was verified for the first stable PyPI release of `iflow-search-langchain`. Mirrors §16 of this document and §17 of the MCP design doc. Section §16 (the `0.1.0a0` prerelease record) is preserved verbatim above; this section captures the prerelease → stable transition.

### 17.1 Artifacts

Both files were built once locally with `python -m build` from commit `7d1cfd9` and uploaded byte-identically to TestPyPI and then PyPI. No rebuild between hops.

| Artifact | Size | sha256 |
|---|---|---|
| `iflow_search_langchain-0.1.0-py3-none-any.whl` | 12,598 B | `65d28a462ae0eb3abac9ad705245997544744256a9027851a9710615be74b321` |
| `iflow_search_langchain-0.1.0.tar.gz` | 9,538 B | `c09a21c97858e6e446a0868c87d5ca808c398a8737b735bd2570eab93b9d4496` |

Hashes were compared against the `digests.sha256` field returned by the TestPyPI and PyPI JSON APIs (`/pypi/iflow-search-langchain/0.1.0/json`) at each hop. All four digests match.

### 17.2 Version, dependency, and metadata changes vs. `0.1.0a0`

The bump commit (`7d1cfd9`) touched only the version-bearing surfaces; no runtime code, tool schema, factory signature, or return shape changed.

- `pyproject.toml`: `version = "0.1.0a0"` → `"0.1.0"`; `Development Status :: 3 - Alpha` → `4 - Beta`; runtime dep floor `iflow-search>=0.1.0a0,<0.2` → `>=0.1.0,<0.2`.
- `src/iflow_search_langchain/_version.py`: `__version__ = "0.1.0a0"` → `"0.1.0"`.
- `tests/test_version.py`: now asserts the version is PEP 440 stable (`\d+\.\d+\.\d+`, no `a/b/rc/.dev/.post` suffix) in addition to matching `pyproject.toml`.
- READMEs (root and package): install snippet drops `--pre`; status line reflects stable.

### 17.3 CI gate

GitHub Actions run [`26440269469`](https://github.com/zhengyanglsun/iflow-search-py/actions/runs/26440269469) on commit `7d1cfd9` was the green CI that unblocked the publish flow. It exercised the full monorepo matrix:

| Package | Python versions | Result |
|---|---|---|
| `iflow-search` | 3.10 / 3.11 / 3.12 / 3.13 | ✅ |
| `iflow-search-mcp` | 3.10 / 3.11 / 3.12 / 3.13 | ✅ |
| `iflow-search-langchain` | 3.10 / 3.11 / 3.12 / 3.13 | ✅ |
| `iflow-search-openapi` | 3.10 / 3.11 / 3.12 / 3.13 | ✅ |

16/16 jobs ran ruff, mypy strict, pytest, and `python -m build`. No CI job uploads anywhere — publishing remained manual `twine upload` only (§14.2).

### 17.4 Cold-install matrix

For each source, a fresh Python 3.11 venv was created in `/var/folders/.../iflow-langchain-010-*`, the package was installed via `uv pip install iflow-search-langchain==0.1.0` (no `--pre`, since the release is now PEP 440 stable), and both an **offline import smoke** and an **offline LangChain tool smoke** (mock `httpx` transport — see §17.5) were run.

| Source | Index URL | Offline import smoke | Offline tool smoke |
|---|---|---|---|
| TestPyPI | `https://test.pypi.org/simple/` + PyPI as `--extra-index-url` for deps | ✅ | ✅ |
| PyPI | default index (`--refresh` to bypass cache) | ✅ | ✅ |

The TestPyPI install uses PyPI as `--extra-index-url` because the runtime dependency `iflow-search==0.1.0` only lives on PyPI; the same applies to `langchain-core` and `pydantic`. In both venvs, dependency resolution pulled `iflow-search==0.1.0` (stable, no `--pre`), confirming the dep-floor bump in §17.2 holds end-to-end.

Offline import smoke asserted: `import iflow_search_langchain` succeeds with no API key set, `__version__ == "0.1.0"`, `__all__` exposes exactly the four factories plus `__version__`, and `create_iflow_web_search_tool()` raises `IFlowConfigError(code="missing_api_key")` at factory-call time rather than at first invocation.

### 17.5 LangChain tool smoke on the installed wheel (offline, mock transport)

The 0.1.0 stable release was verified end-to-end inside the cold PyPI venv by exercising the LangChain `BaseTool` contract against an `httpx.MockTransport` — no live API call, no `IFLOW_API_KEY` from the developer's shell. The script:

- Imports `create_iflow_search_tools` from the PyPI-installed wheel.
- Confirms the returned list contains exactly three `BaseTool` instances, in fixed order: `iflow_web_search`, `iflow_image_search`, `iflow_web_fetch`.
- Confirms each tool has `response_format == "content_and_artifact"`.
- Constructs a caller-supplied `IFlowSearchClient` with explicit langchain attribution (`source="langchain"`, `integration_name="iflow-search-langchain"`, `integration_version=iflow_search_langchain.__version__`) and an `httpx.Client(transport=httpx.MockTransport(handler))`, then passes it via `client=` so the factory does not auto-build (per §15.7, caller-supplied clients are not mutated).
- Invokes `iflow_web_search._run(query="hello", count=2)` against the mock, asserts the returned `(content: str, artifact: dict)` tuple is shaped correctly, `artifact["results"]` is populated from the canned envelope, and `artifact["raw"]` carries the original response.

All assertions passed against the wheel installed from PyPI. No real API key was used; no live HTTP request was made.

### 17.6 Attribution headers verified offline

The mock transport in §17.5 recorded the outbound request headers and asserted:

- `IFlow-Source: langchain`
- `IFlow-Integration: iflow-search-langchain`
- `IFlow-Integration-Version: 0.1.0`
- `Authorization: Bearer <test-key>` (synthetic key, never a real credential)

This wire-verifies that the published wheel emits stable-release attribution end-to-end, including the version-string flip from `0.1.0a0` to `0.1.0`.

### 17.7 Tag

A namespaced annotated git tag was created and pushed for this release, in the convention established in §16.6:

```
iflow-search-langchain/v0.1.0
  tag object   cdce8577bcff49ce27c6f3be4f708281e8e2c1c1
  ↳ commit     7d1cfd95e4054740cf21c7f347afa114f07df472   (chore(langchain): bump iflow-search-langchain to 0.1.0)
```

The legacy `iflow-search-langchain/v0.1.0a0` tag remains in place pointing at commit `4270538` for historical reference. No existing tag was moved.

### 17.8 Constraints honoured throughout

- No real API key was ever printed, written to the repository, or committed. The offline tool smoke used the literal synthetic value `"test-key"`.
- `DEEPSEEK_API_KEY` was not read at any point — the LangChain adapter has no LLM-provider coupling (§15.11), and the stable verification went one step further by replacing the live-API smoke with a mock-transport smoke.
- `~/.pypirc` was not read via `cat` / `head` / `less` / `grep`; only `test -f` and `stat` (mode check) were performed. `twine upload --non-interactive` used the developer-managed credential store; tool output was scrubbed for any `pypi-`, `Bearer`, or `password` line before inspection.
- The wheel and sdist uploaded to PyPI are bit-for-bit identical to the local `dist/` artifacts; the four sha256 digests (local / TestPyPI / PyPI for each of wheel and sdist) all match (§17.1).
- No CI workflow was modified to publish. Every upload was a manual, audited `twine upload`.
- No runtime code, public API, tool schema, factory signature, or return shape changed between `0.1.0a0` and `0.1.0` (§17.2). The transition is purely metadata + version.
- The release commit (`7d1cfd9`) and this docs commit omit the `Co-Authored-By: Claude` trailer per the repository's commit-message convention.
