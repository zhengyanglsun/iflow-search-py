# CrewAI upstream contribution draft — iFlow Search tool suite

**Status:** draft for maintainers — not yet filed on `crewAIInc/crewAI`.

**Reference integrations:** Tavily for external SDK + `package_dependencies`; Brave Search for endpoint-specific tool-suite structure.

**Standalone package:** `iflow-search-crewai==0.1.0` is available as the current standalone adapter. The upstream proposal below would add native `crewai_tools` classes that depend directly on the core `iflow-search` SDK.

---

## Issue draft

**Repository:** `crewAIInc/crewAI`

**Title:** `Add iFlow Search tool suite to crewAI tools`

### Summary

I would like to propose adding an **iFlow Search tool suite** to `lib/crewai-tools/`.

The proposed suite follows the endpoint-specific pattern used by Brave Search:

| Tool class             | iFlow capability                        | Proposed CrewAI tool name |
| ---------------------- | --------------------------------------- | ------------------------- |
| `IFlowWebSearchTool`   | Web search                              | `iflow_web_search`        |
| `IFlowImageSearchTool` | Image search                            | `iflow_image_search`      |
| `IFlowWebFetchTool`    | Web page fetch / URL content extraction | `iflow_web_fetch`         |

iFlow Search provides search APIs for AI agents, including web search, image search, and web page fetching. A standalone CrewAI adapter already exists as `iflow-search-crewai==0.1.0`; this proposal is for native in-tree tools for `crewai[tools]` users.

### Motivation

CrewAI already supports several search and research tools, including Tavily and Brave Search. iFlow Search fits the same tool category:

* web search for current information retrieval;
* image search as a differentiated capability;
* URL content extraction via web fetch;
* Python-first integration through the maintained `iflow-search` SDK;
* lower friction for users who prefer native `crewai_tools` over MCP stdio configuration.

### Non-goals

* This is **not** a request for an AMP / Studio provider tile.
* This does not add News, Video, or Research tools because iFlow Search does not expose matching endpoints today.
* This would not require users to configure MCP.

### Proposed implementation

Add a new tool suite under:

```text
lib/crewai-tools/src/crewai_tools/tools/iflow_search_tool/
```

Proposed public imports:

```python
from crewai_tools import (
    IFlowWebSearchTool,
    IFlowImageSearchTool,
    IFlowWebFetchTool,
)
```

Proposed configuration:

* required env var: `IFLOW_API_KEY`
* optional: `IFLOW_BASE_URL`, defaulting to `https://platform.iflow.cn`
* package dependency: `iflow-search>=0.1.0,<0.2`

The implementation would use the core `iflow-search` SDK directly rather than depending on the standalone `iflow-search-crewai` adapter.

### Documentation

I can add a single suite page, similar in spirit to the Brave Search docs page:

```text
docs/en/tools/search-research/iflowsearchtools.mdx
```

The page would include:

* a three-tool suite table;
* install/config instructions;
* examples for each tool;
* an Agent + Task example;
* a note that this is a native CrewAI tool integration, not an AMP provider tile.

### Metadata / specs

I can include or regenerate the relevant `tool.specs.json` changes if maintainers prefer that in the same PR, or leave that to the existing generation workflow if that is the preferred process.

### Affiliation

I maintain iFlow Search SDK integrations. Relevant links:

* iFlow API docs: `https://platform.iflow.cn/docs/`
* standalone CrewAI adapter: `iflow-search-crewai==0.1.0`
* core SDK dependency: `iflow-search>=0.1.0,<0.2`

### Questions for maintainers

1. Would you prefer this as one suite PR, or separate PRs for tools and docs?
2. Is the Brave-style endpoint-specific suite structure acceptable for iFlow?
3. Should the CrewAI tool names be snake_case (`iflow_web_search`) for consistency with existing iFlow adapters, or human-readable (`iFlow Web Search`) for consistency with some existing CrewAI tools?
4. Should `IFLOW_BASE_URL` be exposed in tool metadata, or only as a constructor option?
5. Should a small helper such as `create_iflow_search_tools()` be included, or should the upstream PR only export the three tool classes?

---

## PR draft

**Repository:** `crewAIInc/crewAI`

**Title:** `feat(tools): add iFlow Search tool suite`

**Base branch:** to be confirmed against the repository's current contribution branch before opening.

### Summary

This PR adds native CrewAI tools for iFlow Search:

* `IFlowWebSearchTool`
* `IFlowImageSearchTool`
* `IFlowWebFetchTool`

The tools use the maintained `iflow-search` Python SDK and are configured with `IFLOW_API_KEY`.

### Changes

```text
lib/crewai-tools/src/crewai_tools/tools/iflow_search_tool/
  __init__.py
  base.py
  schemas.py
  tools.py
  README.md

lib/crewai-tools/src/crewai_tools/__init__.py
lib/crewai-tools/tests/tools/iflow_search_tool_test.py

docs/en/tools/search-research/iflowsearchtools.mdx
docs/en/tools/search-research/overview.mdx
docs/docs.json
```

Depending on maintainer preference, this PR can also include regenerated `lib/crewai-tools/tool.specs.json`.

### Implementation notes

* Uses the core `iflow-search>=0.1.0,<0.2` SDK.
* Does not depend on the standalone `iflow-search-crewai` adapter.
* Adds three endpoint-specific tools rather than a single overloaded tool.
* Keeps News / Video / Research out of scope because iFlow does not expose those endpoints.
* Does not add or imply an AMP / Studio provider tile.
* Does not include any API keys, fixtures with real credentials, or live-network tests.

### Configuration

```bash
export IFLOW_API_KEY="YOUR_IFLOW_API_KEY"
```

Optional:

```bash
export IFLOW_BASE_URL="https://platform.iflow.cn"
```

### Example

```python
from crewai import Agent
from crewai_tools import IFlowWebSearchTool

agent = Agent(
    role="Web Researcher",
    goal="Find current information from the web",
    tools=[IFlowWebSearchTool()],
)
```

### Testing

Planned local checks:

```bash
cd lib/crewai-tools
python -m pytest tests/tools/iflow_search_tool_test.py -v
python -m ruff check src/crewai_tools/tools/iflow_search_tool tests/tools/iflow_search_tool_test.py
python -m mypy src/crewai_tools/tools/iflow_search_tool
```

Tests use mocks only and do not call the live iFlow API.

### Security

* No real API keys in tests, docs, or fixtures.
* `Authorization` headers are not logged.
* Error messages avoid leaking credentials.
* Live smoke tests, if any, are opt-in and not part of CI.

### Related

* Standalone adapter: `iflow-search-crewai==0.1.0`
* iFlow API docs: `https://platform.iflow.cn/docs/`
* Existing MCP docs PR: `crewAIInc/crewAI#5928` — complementary MCP route, not a replacement for native tools.
* Brave Search suite is the closest structural precedent.
