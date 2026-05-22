# iFlow Search Python SDK

Python SDK for the **iFlow Search API (心流搜索 API)** — web search, image search, and web-page fetching, returning structured data suitable for use by LLMs and AI agents.

This is the framework-agnostic core SDK. Adapter packages (LangChain, MCP, OpenAPI) are planned and will live in this same repository under `packages/`.

## Links

- API docs: <https://platform.iflow.cn/docs/>
- Skill docs: <https://platform.iflow.cn/docs/skill>
- Official skill repo: <https://github.com/iflow-ai/iflow-skills/tree/main/skills/iflow-search>
- JS SDK repo: <https://github.com/zhengyanglsun/iflow-search-js>

## Status

- ✅ Core SDK implemented (`packages/iflow-search/`)
- ✅ Sync and async clients
- ✅ Real-API smoke verified for all three endpoints
- ✅ pytest / ruff / mypy strict / `python -m build` all green
- ⏳ PyPI release pending
- ⏳ Planned adapters (not yet implemented): `iflow-search-langchain`, `iflow-search-mcp`, `iflow-search-openapi`

## Installation

PyPI release is pending.

For local development:

```bash
git clone https://github.com/zhengyanglsun/iflow-search-py.git
cd iflow-search-py/packages/iflow-search
python -m pip install -e ".[dev]"
```

After the first PyPI release, install with:

```bash
pip install --pre iflow-search
```

`--pre` is required while the version is still a PEP 440 pre-release (`0.1.0a0`). Without it, `pip` will report "no matching distribution".

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

The MCP adapter (planned) will additionally emit:

- `IFlow-MCP-Client`
- `IFlow-MCP-Client-Version`

**The API key is never placed in any attribution header.** Attribution headers exist solely for usage statistics and must remain free of credentials.

## Repository layout

```
iflow-search-py/
├── docs/design/python-sdk-design.md   ← public design document
├── packages/
│   └── iflow-search/                   ← core SDK (this is what ships to PyPI)
│       ├── src/iflow_search/
│       ├── tests/
│       ├── scripts/smoke_real_api.py
│       ├── pyproject.toml
│       ├── README.md                   ← PyPI long_description
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

## Roadmap

Planned (not yet implemented) packages:

- `iflow-search-langchain` — LangChain tools (LangGraph reuses these; no separate package).
- `iflow-search-mcp` — MCP stdio server for use by Claude Code, Claude Desktop, Hermes, and other MCP-capable hosts.
- `iflow-search-openapi` — FastAPI / OpenAPI server for Open WebUI, Coze, and similar platforms.

See `docs/design/python-sdk-design.md` for the design rationale.

## License

[MIT](./packages/iflow-search/LICENSE)
