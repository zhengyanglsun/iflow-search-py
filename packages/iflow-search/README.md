# iflow-search

Python SDK for **iFlow Search (心流搜索)** — a search API that exposes web search, image search, and web-page fetching with AI-friendly structured output.

- **Product:** <https://platform.iflow.cn/>
- **API docs:** <https://platform.iflow.cn/docs/>
- **Status:** alpha pre-release (`0.1.0a0`), published on PyPI. Requires `--pre` to install — the Python analog of npm's `next` dist-tag.

This is the framework-agnostic **core** SDK: it has zero LangChain / MCP / FastAPI dependencies. The MCP adapter (`iflow-search-mcp`) ships from the same repository and depends on this package; LangChain and FastAPI/OpenAPI adapters are planned.

## Install

```bash
pip install --pre iflow-search
```

`--pre` is required while the version is still a pre-release. Without it, `pip` will report "no matching distribution".

For local development:

```bash
git clone https://github.com/zhengyanglsun/iflow-search-py.git
cd iflow-search-py/packages/iflow-search
python -m pip install -e ".[dev]"
```

## Quick start (sync)

```python
import os
from iflow_search import IFlowSearchClient

client = IFlowSearchClient(api_key=os.environ["IFLOW_API_KEY"])

result = client.web_search(query="flash attention", count=5)
for r in result.results:
    print(r.title, r.url)

images = client.image_search(query="iflow logo")
for i in images.images:
    print(i.image_url, i.source_url)

page = client.web_fetch(url="https://platform.iflow.cn/docs/")
print(page.title, len(page.content), "chars")
```

## Quick start (async)

```python
import asyncio, os
from iflow_search import AsyncIFlowSearchClient

async def main() -> None:
    async with AsyncIFlowSearchClient(api_key=os.environ["IFLOW_API_KEY"]) as client:
        result = await client.web_search(query="flash attention", count=5)
        for r in result.results:
            print(r.title, r.url)

asyncio.run(main())
```

## Configuration

| Parameter | Default | Notes |
|---|---|---|
| `api_key` | `os.environ["IFLOW_API_KEY"]` | Required. Falls back to env var; raises `IFlowConfigError` if neither is set. |
| `source` | `"python"` | Sent as `IFlow-Source` header. Adapter packages override this. |
| `integration_name` | `"iflow-search"` | Sent as `IFlow-Integration` header. |
| `integration_version` | installed package version | Sent as `IFlow-Integration-Version` header. |
| `base_url` | `https://platform.iflow.cn` | Useful for staging/proxy environments. |
| `timeout` | `30.0` seconds | Applied to each individual request. |
| `http_client` | new `httpx.Client` (or `AsyncClient`) | Inject one for connection pooling or testing (e.g. via `httpx.MockTransport`). |

## Attribution headers

Every outbound request carries:

```
Authorization:             Bearer <api-key>
Content-Type:              application/json
Accept:                    application/json
IFlow-Source:              python   (configurable)
IFlow-Integration:         iflow-search   (configurable)
IFlow-Integration-Version: <installed package version>
User-Agent:                iflow-search/<version>
```

These are built only by the SDK; constructor arguments let adapter packages set their own `source` / `integration_name` / `integration_version`. There is no API for users to override `Authorization`, `Content-Type`, `Accept`, or `User-Agent` directly.

## Errors

The SDK raises a typed exception hierarchy — never tuples, dicts, or sentinel values:

```
IFlowError
├── IFlowConfigError                 # missing api_key, invalid attribution
├── IFlowValidationError             # bad client-side input
├── IFlowAuthError                   # HTTP 401/403, business code 90402
├── IFlowRateLimitError              # HTTP 429, business code 40303
├── IFlowInsufficientCreditsError    # business code 60400
├── IFlowAPIError                    # HTTP 5xx, non-JSON 2xx, other non-2xx
├── IFlowBusinessError               # success=false with any other code
├── IFlowTimeoutError                # SDK-initiated timeout
└── IFlowNetworkError                # DNS / connection / TLS errors
```

Every exception carries `code` (stable string), `message`, `request` (`{method, url, endpoint}`), and `response_body_truncated` (first 500 chars when applicable). Switch on `code` rather than class identity if you want a stable contract across SDK versions.

```python
from iflow_search import IFlowSearchClient, IFlowError, IFlowRateLimitError

# Reads IFLOW_API_KEY from the environment.
client = IFlowSearchClient()

try:
    result = client.web_search(query="latest LLM benchmarks", count=3)
except IFlowRateLimitError:
    print("Rate limit exceeded")
except IFlowError as exc:
    print(f"iFlow error: {exc.code} {exc.message}")
```

`asyncio.CancelledError` is **not** wrapped — it propagates as itself so cooperative cancellation keeps working.

## Field renames

The wire format uses a few awkward field names. The SDK renames them:

| Request | Wire | Python |
|---|---|---|
| web/image | `keywords` | `query` |
| web/image | `num` | `count` |

| Response | Wire | Python |
|---|---|---|
| web | `link` | `url` (on `WebSearchResult`) |
| image | `url` | `image_url` |
| image | `refUrl` | `source_url` |
| web_fetch | `fromCache` | `from_cache` |
| all | — | `took_ms` (measured client-side) |

The raw envelope is preserved on `response.raw` for callers that need fields the SDK did not model.

## Security

- **Never commit API keys.** Use environment variables (`IFLOW_API_KEY`) or your platform's secret manager.
- The SDK does not auto-load `.env` files and does not read the key from any filesystem path other than the process environment.
- Tests in this repository use fake keys (literal `test-key`) and `httpx.MockTransport` — no real API is contacted, ever.

## Local development

From `packages/iflow-search/`:

```bash
python -m pytest -q                    # offline test suite
python -m ruff check .                 # lint
python -m mypy src/iflow_search        # strict typecheck
python -m build                        # build sdist + wheel into dist/
```

## Real-API smoke

A separate opt-in script exercises all three endpoints against the live API:

```bash
export IFLOW_API_KEY="your-api-key"
export IFLOW_SMOKE=1
python scripts/smoke_real_api.py
```

The script:

- Is **opt-in** — without `IFLOW_SMOKE=1` it refuses to call the live API.
- Reads `IFLOW_API_KEY` from the environment only — never from disk.
- Redacts the key in all log output.
- Does not write any file.

## Adapter packages

This package is the core. Adapter packages depend on it and live in the same repository:

- `iflow-search-mcp` — **published** on PyPI. MCP stdio server for Claude Code / Claude Desktop / Hermes / iFlow CLI. Install with `pip install --pre iflow-search-mcp`.
- `iflow-search-langchain` — planned. LangChain (and LangGraph) tools.
- `iflow-search-openapi` — planned. FastAPI OpenAPI server for Open WebUI / Coze.

## License

[MIT](./LICENSE)
