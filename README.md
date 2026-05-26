# iFlow Search Python SDK

Python SDK for the **iFlow Search API (心流搜索 API)** — web search, image search, and web-page fetching, returning structured data suitable for use by LLMs and AI agents.

The framework-agnostic core SDK, the MCP adapter, the LangChain adapter, and the OpenAPI tool server all ship from this repository as sibling packages under `packages/`.

## Links

- API docs: <https://platform.iflow.cn/docs/>
- Skill docs: <https://platform.iflow.cn/docs/skill>
- Official skill repo: <https://github.com/iflow-ai/iflow-skills/tree/main/skills/iflow-search>
- JS SDK repo: <https://github.com/zhengyanglsun/iflow-search-js>

## Status

- ✅ Core SDK implemented (`packages/iflow-search/`) — published on PyPI as `iflow-search==0.1.0`
- ✅ Sync and async clients
- ✅ Real-API smoke verified for all three endpoints
- ✅ pytest / ruff / mypy strict / `python -m build` all green
- ✅ MCP adapter (`packages/iflow-search-mcp/`) — published on PyPI as `iflow-search-mcp==0.1.0`
- ✅ LangChain adapter (`packages/iflow-search-langchain/`) — published on PyPI as `iflow-search-langchain==0.1.0`
- ✅ OpenAPI tool server (`packages/iflow-search-openapi/`) — published on PyPI as `iflow-search-openapi==0.1.0a2`

## Installation

```bash
pip install iflow-search
```

`iflow-search-openapi` is still in PEP 440 prerelease and requires `pip install --pre iflow-search-openapi`.

For local development:

```bash
git clone https://github.com/zhengyanglsun/iflow-search-py.git
cd iflow-search-py/packages/iflow-search
python -m pip install -e ".[dev]"
```

## Configuration

Set your API key in the shell environment:

```bash
export IFLOW_API_KEY="your-api-key"
```

**Security**:

- Do not commit API keys.
- Do not store keys in this README, in tests, in fixtures, in logs, or in `.env` files.
- The SDK reads `IFLOW_API_KEY` from the shell environment only — never from a file, never from a CLI flag.

## Quickstart — sync

```python
from iflow_search import IFlowSearchClient

# Reads IFLOW_API_KEY from the environment.
client = IFlowSearchClient()

web = client.web_search(query="latest LLM benchmarks", count=3)
print(web.results[0].title, web.results[0].url)

images = client.image_search(query="great wall of china", count=3)
print(images.images[0].image_url)

page = client.web_fetch(url="https://example.com")
print(page.title)
```

## Quickstart — async

```python
import asyncio
from iflow_search import AsyncIFlowSearchClient

async def main() -> None:
    async with AsyncIFlowSearchClient() as client:
        web = await client.web_search(query="latest LLM benchmarks", count=3)
        print(web.results[0].title, web.results[0].url)

asyncio.run(main())
```

## Capabilities

| Method | Endpoint | Returns |
|---|---|---|
| `web_search(query=..., count=None)` | `POST /api/search/webSearch` | `WebSearchResponse` with `.results: list[WebSearchResult]` |
| `image_search(query=..., count=None)` | `POST /api/search/imageSearch` | `ImageSearchResponse` with `.images: list[ImageResult]` |
| `web_fetch(url=...)` | `POST /api/search/webFetch` | `WebFetchResponse` with `.title`, `.content`, `.from_cache` |

The Python API uses `query` / `count`; the SDK rewrites them on the wire to `keywords` / `num`. The raw response envelope is always preserved on `response.raw` for callers that need fields the SDK did not model.

## Attribution headers

The SDK sends the following headers on every request:

| Header | Purpose |
|---|---|
| `Authorization` | `Bearer <api_key>` — built internally from `IFLOW_API_KEY`; not user-overridable |
| `Content-Type` | `application/json` |
| `Accept` | `application/json` |
| `IFlow-Source` | adapter identifier (default `"python"`) |
| `IFlow-Integration` | package name (default `"iflow-search"`) |
| `IFlow-Integration-Version` | installed package version |
| `User-Agent` | `<integration_name>/<integration_version>` |

The MCP adapter additionally emits, when the host sets the corresponding env vars:

- `IFlow-MCP-Client`
- `IFlow-MCP-Client-Version`

**The API key is never placed in any attribution header.** Attribution headers exist solely for usage statistics and must remain free of credentials.

## Repository layout

```
iflow-search-py/
├── docs/design/python-sdk-design.md       ← core design document
├── docs/design/python-mcp-design.md       ← MCP adapter design document
├── docs/design/python-langchain-design.md ← LangChain adapter design document
├── docs/design/python-openapi-design.md   ← OpenAPI adapter design document
├── packages/
│   ├── iflow-search/                      ← core SDK (PyPI: iflow-search)
│   │   ├── src/iflow_search/
│   │   ├── tests/
│   │   ├── scripts/smoke_real_api.py
│   │   ├── pyproject.toml
│   │   ├── README.md                      ← PyPI long_description
│   │   └── LICENSE
│   ├── iflow-search-mcp/                  ← MCP stdio server (PyPI: iflow-search-mcp)
│   │   ├── src/iflow_search_mcp/
│   │   ├── tests/
│   │   ├── scripts/smoke_stdio.py
│   │   ├── pyproject.toml
│   │   ├── README.md                      ← PyPI long_description
│   │   └── LICENSE
│   ├── iflow-search-langchain/            ← LangChain adapter (PyPI: iflow-search-langchain)
│   │   ├── src/iflow_search_langchain/
│   │   ├── tests/
│   │   ├── scripts/smoke_real_api.py
│   │   ├── pyproject.toml
│   │   ├── README.md                      ← PyPI long_description
│   │   └── LICENSE
│   └── iflow-search-openapi/              ← OpenAPI tool server (PyPI: iflow-search-openapi)
│       ├── src/iflow_search_openapi/
│       ├── tests/
│       ├── scripts/smoke_real_api.py
│       ├── pyproject.toml
│       ├── README.md                      ← PyPI long_description
│       └── LICENSE
└── .github/workflows/ci.yml
```

## Development commands

From `packages/iflow-search/`:

```bash
python -m pytest -q                    # 103 offline tests
python -m ruff check .                 # lint
python -m mypy src/iflow_search        # strict typecheck
python -m build                        # build sdist + wheel into dist/
```

## Real-API smoke

A separate opt-in script exercises all three endpoints against the live API:

```bash
cd packages/iflow-search
export IFLOW_API_KEY="your-api-key"
export IFLOW_SMOKE=1
python scripts/smoke_real_api.py
```

The smoke script:

- Is **opt-in** — without `IFLOW_SMOKE=1` it refuses to call the live API.
- Reads `IFLOW_API_KEY` from the environment only — never from disk.
- Redacts the key in all log output.
- Does not write any file.

## Adapters

### `iflow-search-mcp` — published

MCP stdio server for use by Claude Code, Claude Desktop, Hermes, OpenCode, and other MCP-capable hosts. Exposes `iflow_web_search`, `iflow_image_search`, and `iflow_web_fetch` as MCP tools over the official Python `mcp` SDK.

```bash
pip install iflow-search-mcp
```

Configure your MCP host to launch the `iflow-search-mcp` console script. Example for Claude Desktop's `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "iflow-search": {
      "command": "iflow-search-mcp",
      "env": {
        "IFLOW_API_KEY": "sk-..."
      }
    }
  }
}
```

Recognised env vars: `IFLOW_API_KEY` (required), `IFLOW_BASE_URL`, `IFLOW_TIMEOUT_MS`, `IFLOW_MCP_CLIENT`, `IFLOW_MCP_CLIENT_VERSION`. The package's own README covers per-host config and the full tool schemas; see `docs/design/python-mcp-design.md` for the design rationale.

### `iflow-search-langchain` — published

LangChain `BaseTool` factories for `iflow_web_search`, `iflow_image_search`, and `iflow_web_fetch`. LangGraph consumes these tools directly (`create_react_agent`, `ToolNode`), so there is no separate `iflow-search-langgraph` package.

```bash
pip install iflow-search-langchain
```

```python
import os
from iflow_search_langchain import create_iflow_search_tools

tools = create_iflow_search_tools(api_key=os.environ["IFLOW_API_KEY"])
# [iflow_web_search, iflow_image_search, iflow_web_fetch] — wire into your agent.
```

Each tool uses `response_format="content_and_artifact"`: `_run` / `_arun` return `(content: str, artifact: dict)`. Auto-built clients carry `IFlow-Source: langchain` attribution; caller-supplied clients are not mutated. The package's own README covers configuration, attribution, lifecycle, and the LangGraph example; see `docs/design/python-langchain-design.md` for the design rationale.

### `iflow-search-openapi` — published

FastAPI / OpenAPI 3.1 tool server for Open WebUI, Coze, and similar platforms that consume OpenAPI tool catalogues. Exposes `iflow_web_search`, `iflow_image_search`, and `iflow_web_fetch` as `POST /tools/*` endpoints; serves `/openapi.json` and `/health`.

```bash
pip install --pre iflow-search-openapi
export IFLOW_API_KEY="your-api-key"
iflow-search-openapi
```

Default bind is `127.0.0.1:8787` (local-only). Set `IFLOW_OPENAPI_HOST=0.0.0.0` for LAN / container exposure. Optional bearer auth for external callers via `IFLOW_OPENAPI_AUTH_TOKEN`; configurable CORS via `IFLOW_OPENAPI_CORS_ORIGIN`. The package's own README covers configuration and per-platform import flows; see `docs/design/python-openapi-design.md` for the design rationale.

See `docs/design/python-sdk-design.md` for the core design rationale.

## License

[MIT](./packages/iflow-search/LICENSE)
