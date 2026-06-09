# iflow-search-crewai

[![PyPI version](https://img.shields.io/pypi/v/iflow-search-crewai)](https://pypi.org/project/iflow-search-crewai/)

CrewAI tools for **iFlow Search (心流搜索)** — web search, image search, and web-page fetching, exposed as native `crewai.tools.BaseTool` instances.

This package is a **CrewAI-native Python tool adapter**. It is **not** a CrewAI Studio / AMP official provider tile. To appear as a first-class “iFlow Search” integration inside CrewAI’s product UI, a separate official partnership / Catalog / Marketplace route is required.

- **Core SDK:** [`iflow-search`](https://pypi.org/project/iflow-search/)
- **Sibling adapters:** [`iflow-search-mcp`](https://pypi.org/project/iflow-search-mcp/), [`iflow-search-langchain`](https://pypi.org/project/iflow-search-langchain/)
- **API docs:** <https://platform.iflow.cn/docs/>

## Install

```bash
pip install iflow-search-crewai
```

## Configuration

```bash
export IFLOW_API_KEY="YOUR_IFLOW_API_KEY"
```

Optional:

```bash
export IFLOW_BASE_URL="https://platform.iflow.cn"
export IFLOW_TIMEOUT_MS="30000"
```

Never commit API keys. Do not hard-code keys in source files.

## Basic CrewAI usage

```python
from crewai import Agent
from iflow_search_crewai import create_iflow_search_tools

agent = Agent(
    role="Researcher",
    goal="Research current information from the web",
    backstory="You are a careful research assistant.",
    tools=create_iflow_search_tools(),
)
```

## Single-tool usage

```python
from iflow_search_crewai import IFlowWebSearchTool

web_search = IFlowWebSearchTool()
result = web_search.run(query="latest AI agent frameworks", count=5)
```

## Tools

| Class | Tool name | Purpose |
| --- | --- | --- |
| `IFlowWebSearchTool` | `iflow_web_search` | Web search by query |
| `IFlowImageSearchTool` | `iflow_image_search` | Image search by query |
| `IFlowWebFetchTool` | `iflow_web_fetch` | Fetch readable content from a URL |

### Arguments

| Tool | Parameters |
| --- | --- |
| Web Search | `query: str`, `count: int = 10` (1–50) |
| Image Search | `query: str`, `count: int = 10` (1–50) |
| Web Fetch | `url: str` (`http://` or `https://`) |

Each tool returns a **JSON string** with compact, LLM-friendly fields (titles, URLs, snippets, etc.).

## DeepSeek + CrewAI smoke example

Requires `crewai`, this package, and API keys in the environment. **Do not hard-code keys.**

```python
import os

from crewai import Agent, Crew, Task, LLM
from iflow_search_crewai import IFlowWebSearchTool

llm = LLM(
    model="deepseek/deepseek-chat",
    api_key=os.environ["DEEPSEEK_API_KEY"],
)

researcher = Agent(
    role="Web Researcher",
    goal="Answer questions using live web search",
    backstory="You use iflow_web_search when current information is needed.",
    tools=[IFlowWebSearchTool()],
    llm=llm,
    verbose=True,
)

task = Task(
    description="What is CrewAI? Give a one-sentence answer grounded in search results.",
    expected_output="A one-sentence summary with a source URL.",
    agent=researcher,
)

crew = Crew(agents=[researcher], tasks=[task], verbose=True)
result = crew.kickoff()
print(result)
```

If your CrewAI version prefers a different DeepSeek model string, adjust `model=` to match your installed CrewAI / LiteLLM configuration.

## vs MCP route

| | `iflow-search-crewai` | `iflow-search-mcp` / `@iflow-ai/search-mcp` |
| --- | --- | --- |
| Integration style | Native CrewAI `BaseTool` | MCP stdio server |
| Host setup | `pip install` + env var | `npx` or Python MCP binary + MCP config |
| Best for | Python-first CrewAI projects | MCP-native hosts and `MCPServerAdapter` |

Both call the same iFlow Search API via the shared `iflow-search` core SDK (Python) or MCP adapter (JS/Python).

## Boundaries

- Not a built-in CrewAI search provider.
- Not an AMP / Studio UI tile without CrewAI official integration work.
- Does not replace `iflow-search-mcp` for MCP-based workflows.

## Local development

```bash
cd packages/iflow-search-crewai
python -m pip install -e "../iflow-search"
python -m pip install -e ".[dev]"
python -m pytest -q
python -m ruff check .
python -m mypy src/iflow_search_crewai
```

## Optional real-API smoke

```bash
export IFLOW_API_KEY="YOUR_IFLOW_API_KEY"
export IFLOW_CREWAI_SMOKE=1
python scripts/smoke_real_api.py
```
