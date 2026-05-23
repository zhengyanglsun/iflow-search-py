# iflow-search-langchain

LangChain (and LangGraph) tools for **iFlow Search (心流搜索)** — web search, image search, and web-page fetching, exposed as `langchain_core.tools.BaseTool` instances.

- **Core SDK:** [`iflow-search`](https://pypi.org/project/iflow-search/) — this package wraps it; do not skip installing it.
- **Sibling adapter:** [`iflow-search-mcp`](https://pypi.org/project/iflow-search-mcp/) — MCP stdio server.
- **API docs:** <https://platform.iflow.cn/docs/>
- **Status:** alpha pre-release (`0.1.0a0`). Requires `pip install --pre`.

## Install

```bash
pip install --pre iflow-search-langchain
```

`--pre` is required while the version is still a PEP 440 prerelease.

## Quick start — agent with all three tools

```python
import os
from iflow_search_langchain import create_iflow_search_tools

tools = create_iflow_search_tools(api_key=os.environ["IFLOW_API_KEY"])
# tools is a list of three langchain_core BaseTool instances, in fixed order:
#   [iflow_web_search, iflow_image_search, iflow_web_fetch]
# All three share one sync + one async client (one connection pool per direction).

# Wire `tools` into your agent of choice (LangChain create_react_agent,
# LangGraph ToolNode, etc.) the same way you would any other LangChain tool.
```

## Single-tool factories

```python
from iflow_search_langchain import (
    create_iflow_web_search_tool,
    create_iflow_image_search_tool,
    create_iflow_web_fetch_tool,
)

web = create_iflow_web_search_tool()  # reads IFLOW_API_KEY from env
out = web.invoke({"query": "latest LLM benchmarks", "count": 3})
print(out)  # short LLM-facing text summary
```

## Return shape — `content_and_artifact`

Each tool sets `response_format = "content_and_artifact"`. From `_run` / `_arun` you get a `tuple[str, dict[str, Any]]`:

- **`content`** — a short LLM-friendly text summary (titles, URLs, snippets).
- **`artifact`** — the core SDK's normalized response as a JSON-serializable dict, including the raw envelope on `artifact["raw"]`.

LangChain's `tool.invoke({...})` returns just the content string. To get the artifact, use a `ToolCall`-shaped input per the LangChain docs for your installed `langchain-core` version, or call the underlying client directly.

## LangGraph

LangGraph consumes LangChain tools directly — there is no separate `iflow-search-langgraph` package.

```python
import os
from langgraph.prebuilt import create_react_agent
from iflow_search_langchain import create_iflow_search_tools

# Replace `chat_model_of_your_choice` with any LangChain chat model. The
# adapter is provider-free; bring your own LLM.
agent = create_react_agent(
    model=chat_model_of_your_choice,
    tools=create_iflow_search_tools(api_key=os.environ["IFLOW_API_KEY"]),
)
```

## Configuration

| Argument | Default | Notes |
|---|---|---|
| `api_key` | `IFLOW_API_KEY` env var | Required for auto-built clients. Raises `IFlowConfigError` at factory-call time (not at first tool invocation) if missing. |
| `base_url` | core SDK default | Useful for staging / proxy environments. |
| `timeout` | core SDK default | Applied to each individual request. |
| `client` | newly built `IFlowSearchClient` | Pass your own for connection pooling or test injection. |
| `async_client` | newly built `AsyncIFlowSearchClient` | Pass your own for connection pooling or test injection. |

## Attribution and telemetry — read this if it matters to you

When the factory auto-builds the underlying clients (the common case), they carry adapter attribution: `IFlow-Source: langchain`, `IFlow-Integration: iflow-search-langchain`, `IFlow-Integration-Version: <package version>`.

When you pass your own `client` / `async_client`, the factory **does not mutate them**. Whatever attribution your client was built with is what reaches iFlow's telemetry — so a bare `AsyncIFlowSearchClient(api_key=...)` lands as `source="python"` (the core's default), not `langchain`.

If you want your LangChain-driven traffic correctly attributed:

- **Recommended:** let the factory build the client (don't pass `client=` / `async_client=`).
- **Or:** construct the client yourself with the matching attribution kwargs and pass it in:

  ```python
  from iflow_search import IFlowSearchClient
  IFlowSearchClient(
      api_key=...,
      source="langchain",
      integration_name="iflow-search-langchain",
      integration_version="0.1.0a0",
  )
  ```

## Errors

The adapter does not wrap or remap errors — every `IFlowError` from the core SDK propagates through the tool boundary with its stable `code` intact.

```python
from iflow_search import IFlowError, IFlowRateLimitError
from iflow_search_langchain import create_iflow_web_search_tool

tool = create_iflow_web_search_tool()
try:
    out = tool.invoke({"query": "x"})
except IFlowRateLimitError:
    ...
except IFlowError as exc:
    print(exc.code, exc.message)
```

`asyncio.CancelledError` is **not** wrapped — it propagates as itself so LangGraph's `ToolNode` and `asyncio.wait_for(...)` keep working.

## Lifecycle

Auto-built clients are owned by the tool instance. For long-running services that need deterministic cleanup, pass caller-managed clients and close them yourself:

```python
import asyncio
from iflow_search import AsyncIFlowSearchClient
from iflow_search_langchain import create_iflow_search_tools

async def main() -> None:
    async with AsyncIFlowSearchClient() as ac:
        tools = create_iflow_search_tools(async_client=ac)
        # ... use tools ...
```

## What's not included in v0.1.0a0

- `BaseRetriever`, `BaseLoader`, `BaseToolkit` — tools only.
- A separate `iflow-search-langgraph` package — LangGraph consumes the tools above directly.
- A CLI. The package is a library.
- Streaming. iFlow Search is request/response.
- Bundled LLM-provider code.

## Local development

From `packages/iflow-search-langchain/`:

```bash
python -m pip install -e ".[dev]"
python -m pytest -q
python -m ruff check .
python -m mypy src/iflow_search_langchain
python -m build
```

## Real-API smoke

```bash
cd packages/iflow-search-langchain
export IFLOW_API_KEY="your-api-key"
export IFLOW_LANGCHAIN_SMOKE=1
python scripts/smoke_real_api.py
```

The script:

- Is **opt-in** — without `IFLOW_LANGCHAIN_SMOKE=1` it refuses to call the live API.
- Reads `IFLOW_API_KEY` from the environment only — never from disk.
- Redacts the key in all log output.
- Does not write any file.
- Does not import LangGraph or any LLM provider — the adapter contract is `(content, artifact)` shape correctness, not "an LLM picks the right tool."

## License

[MIT](./LICENSE)
