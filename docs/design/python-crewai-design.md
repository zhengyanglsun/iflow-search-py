# `iflow-search-crewai` — Python CrewAI adapter design

Companion design document for the **`iflow-search-crewai`** package, a CrewAI `BaseTool` adapter for the iFlow Search API. Sibling to `iflow-search` (core SDK), `iflow-search-mcp`, `iflow-search-langchain`, and `iflow-search-openapi`.

The package wraps `iflow-search`'s `IFlowSearchClient` in three CrewAI `BaseTool` subclasses (`iflow_web_search`, `iflow_image_search`, `iflow_web_fetch`) plus a `create_iflow_search_tools()` factory. It does not introduce new HTTP or normalization logic — every architectural invariant of the core SDK applies unchanged.

## 1. Scope

In scope for v0.1.0:

- Three CrewAI `BaseTool` subclasses, one per iFlow Search endpoint (Brave Search–style tool suite).
- Pydantic v2 args schemas (`query` + `count` for search tools; `url` for fetch).
- JSON-string return payloads (compact, LLM-friendly fields).
- Attribution headers (`IFlow-Source: crewai`, `IFlow-Integration: iflow-search-crewai`, `IFlow-Integration-Version`) via the core client.
- Lazy client construction (tools can be instantiated without a key; `_run()` fails with a clear message).
- Opt-in smoke scripts (`IFLOW_CREWAI_SMOKE=1`, `IFLOW_CREWAI_AGENT_SMOKE=1`).

Out of scope for v0.1.0:

- CrewAI AMP / Studio provider tile (requires official CrewAI partnership).
- News Search, Video Search, or Research tools (no matching iFlow API endpoints).
- In-tree contribution to `crewAIInc/crewAI` (planned separately; see `crewai-upstream-contribution.md`).
- True async HTTP (`_arun` delegates to `_run`).
- Bundled LLM-provider integrations.

## 2. Distribution

| Attribute | Value |
|---|---|
| PyPI name | `iflow-search-crewai` |
| Module name | `iflow_search_crewai` |
| Version (initial stable) | `0.1.0` |
| Console scripts | none |
| License | MIT |

## 3. Python version and runtime dependencies

```toml
dependencies = [
    "iflow-search>=0.1.0,<0.2",
    "crewai>=0.80.0,<2.0",
    "pydantic>=2.7,<3.0",
]
```

- `requires-python = ">=3.10"` — same baseline as sibling adapters.
- `crewai` is required because tools inherit `crewai.tools.BaseTool` and declare `EnvVar` metadata.

## 4. Repository layout

```
packages/iflow-search-crewai/
├── src/iflow_search_crewai/
│   ├── __init__.py
│   ├── _version.py
│   ├── _constants.py
│   ├── _config.py
│   ├── _schemas.py
│   ├── _serialize.py
│   ├── _errors.py
│   └── tools.py
├── tests/
├── scripts/
│   ├── smoke_real_api.py
│   └── smoke_crewai_deepseek.py
├── pyproject.toml
├── README.md
└── LICENSE
```

## 5. Public API

| Export | Tool `name` | Endpoint |
|---|---|---|
| `IFlowWebSearchTool` | `iflow_web_search` | Web search |
| `IFlowImageSearchTool` | `iflow_image_search` | Image search |
| `IFlowWebFetchTool` | `iflow_web_fetch` | Web fetch |
| `create_iflow_search_tools()` | (factory) | Returns all three in fixed order |

## 6. Release verification — `0.1.0` stable (2026-06-09)

Record of what was verified for the first stable PyPI release of `iflow-search-crewai`. Release commit: `ebab1f7` (`feat(crewai): add iFlow Search tools`).

### 6.1 Artifacts

Both files were built once locally with `python -m build` from commit `ebab1f7` and uploaded byte-identically to TestPyPI and then PyPI. No rebuild between hops.

| Artifact | Size | sha256 |
|---|---|---|
| `iflow_search_crewai-0.1.0-py3-none-any.whl` | 11,010 B | `3885a7bf20a7eaa184451d75f748d8dacd74516d729f1f2e361723029cdb1600` |
| `iflow_search_crewai-0.1.0.tar.gz` | 8,013 B | `64413b0d46428da03cd6e15fe9d7ed47e74e9a915732b3cd62f93fe5033e0712` |

Hashes were compared against the `digests.sha256` field returned by the TestPyPI and PyPI JSON APIs (`/pypi/iflow-search-crewai/0.1.0/json`) at each hop. All six digests (local + TestPyPI + PyPI for each artifact) match.

### 6.2 CI gate

GitHub Actions run [`27191452082`](https://github.com/zhengyanglsun/iflow-search-py/actions/runs/27191452082) on commit `ebab1f7` was green (20/20 jobs). Matrix: five packages × Python 3.10 / 3.11 / 3.12 / 3.13 — each job ran ruff, mypy strict, pytest, and `python -m build`. No CI job uploads anywhere; publishing was manual `twine upload` only.

### 6.3 Local gates (pre-upload)

Run from `packages/iflow-search-crewai/`:

| Gate | Result |
|---|---|
| `ruff check .` | pass |
| `mypy src/iflow_search_crewai` | pass |
| `pytest -q` | 17 passed |
| `python -m build` | wheel + sdist produced |
| `python -m twine check dist/*` | PASSED for both files |

### 6.4 TestPyPI cold install

Source: <https://test.pypi.org/project/iflow-search-crewai/0.1.0/>.

- Fresh venv: `/tmp/iflow-crewai-010-testpypi-verify` (CPython 3.12.13).
- Install command:

  ```
  uv pip install \
      --index-url https://test.pypi.org/simple/ \
      --extra-index-url https://pypi.org/simple/ \
      --index-strategy unsafe-best-match \
      iflow-search-crewai==0.1.0
  ```

- `--index-strategy unsafe-best-match` was required so uv resolves `iflow-search-crewai` from TestPyPI while pulling `iflow-search`, `crewai`, and `pydantic` from PyPI.
- Provenance: `iflow_search_crewai.__file__` under `site-packages/`; `__version__ == "0.1.0"`; `__all__` exposes the three tool classes, factory, and `__version__`; tool names `iflow_web_search`, `iflow_image_search`, `iflow_web_fetch`.

### 6.5 Official PyPI cold install

Source: <https://pypi.org/project/iflow-search-crewai/0.1.0/>.

- Fresh venv: `/tmp/iflow-crewai-010-pypi-verify` (CPython 3.12.13).
- Install command:

  ```
  uv pip install --refresh iflow-search-crewai==0.1.0
  ```

- Resolved from PyPI including transitive `iflow-search==0.1.0` and `crewai` — confirming `pip install iflow-search-crewai` works without flags.

### 6.6 Offline CrewAI tool smoke on installed wheels

Both cold venvs (§6.4, §6.5) ran the same offline harness:

- Import `IFlowWebSearchTool` and `create_iflow_search_tools` from the installed wheel.
- Factory returns three tools in fixed order with expected `name` fields.
- Construct `IFlowSearchClient` with `httpx.MockTransport` and explicit crewai attribution; pass via `client=` to `IFlowWebSearchTool`.
- `_run(query="hello", count=2)` returns JSON with `result_count == 1` and expected title from canned envelope.
- Outbound request carries `iflow-source: crewai`, `iflow-integration: iflow-search-crewai`, `iflow-integration-version: 0.1.0`, and `authorization: Bearer test-key` (synthetic key only).

All assertions passed against wheels from both TestPyPI and PyPI. No real API key; no live HTTP.

### 6.7 Tag

```
iflow-search-crewai/v0.1.0  →  commit ebab1f7d26d5061617f7ef18ecc383e708743d09
```

Annotated tag following the namespaced `<package-name>/v<version>` convention used by sibling adapters.

### 6.8 Constraints honoured throughout

- No real iFlow API smoke ran for this release verification record. Prior development smokes (documented in README) used opt-in env gates; the publish verification used mock transport only.
- `IFLOW_API_KEY` and `DEEPSEEK_API_KEY` were never printed in any captured log.
- `~/.pypirc` was not read via `cat` / `grep`; only `test -f` and `stat` (mode `600`) were performed. `twine upload --non-interactive` used the developer-managed credential store; upload output was scrubbed before inspection.
- Wheel and sdist uploaded to TestPyPI and PyPI are bit-for-bit identical to local `dist/`.
- No CI workflow was modified to publish.
- Release commit and this docs-closure commit omit `Co-Authored-By` trailers.
