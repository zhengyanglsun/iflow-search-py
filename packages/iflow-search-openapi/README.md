# iflow-search-openapi

OpenAPI 3.1 tool server for **iFlow Search (心流搜索)** — exposes `iflow_web_search`, `iflow_image_search`, and `iflow_web_fetch` over plain HTTP so platforms that consume OpenAPI tool catalogues (Open WebUI, Coze, …) can wire them in directly.

- **Core SDK:** [`iflow-search`](https://pypi.org/project/iflow-search/) — this package wraps it; do not skip installing it (it is a transitive dependency, so `pip install` handles it).
- **Sibling adapters:** [`iflow-search-mcp`](https://pypi.org/project/iflow-search-mcp/) (MCP stdio server), [`iflow-search-langchain`](https://pypi.org/project/iflow-search-langchain/) (LangChain tools).
- **API docs:** <https://platform.iflow.cn/docs/>
- **Status:** alpha pre-release (`0.1.0a0`). Requires `pip install --pre`.

## Install

```bash
pip install --pre iflow-search-openapi
```

`--pre` is required while the version is still a PEP 440 prerelease.

## Run

```bash
export IFLOW_API_KEY="your-iflow-api-key"
iflow-search-openapi
```

Output (stderr):

```
[iflow-search-openapi] v0.1.0a0 listening on http://127.0.0.1:8787 — bearer auth DISABLED (open mode)
```

By default the server binds **`127.0.0.1:8787`** — local-only. Set `IFLOW_OPENAPI_HOST=0.0.0.0` to expose it to a LAN or a container network. See [Configuration](#configuration) for the full env list.

## Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/health` | Liveness probe — `{"ok": true, "version": "..."}` |
| `GET` | `/openapi.json` | OpenAPI 3.1 schema (auto-generated from Pydantic models) |
| `POST` | `/tools/iflow_web_search` | `{"query": "...", "count": 3}` |
| `POST` | `/tools/iflow_image_search` | `{"query": "...", "count": 3}` |
| `POST` | `/tools/iflow_web_fetch` | `{"url": "https://example.com"}` |

Each tool route declares an explicit OpenAPI `operationId` matching its path-level name (`iflow_web_search`, `iflow_image_search`, `iflow_web_fetch`). Tool hosts such as Open WebUI and Coze dispatch by `operationId` and surface it as the tool name to the consuming LLM — pinning them keeps the LLM-facing names stable across releases.

### Success envelope

```json
{
  "ok": true,
  "data": {
    "query": "latest LLM benchmarks",
    "results": [
      {"title": "...", "url": "https://...", "snippet": "...", "position": 1}
    ],
    "took_ms": 142
  }
}
```

Field names are **snake_case**. The core SDK's `raw` (upstream envelope) is excluded by default — it bloats LLM context for fields the model cannot act on.

### Error envelope

```json
{
  "ok": false,
  "error": {
    "code": "business_rate_limited",
    "message": "Rate limit exceeded.",
    "status_code": 429
  }
}
```

`code` is a stable string; switch on it (not on HTTP status alone) for retry/backoff decisions. The full code table is in [`docs/design/python-openapi-design.md` §8.3](https://github.com/zhengyanglsun/iflow-search-py/blob/main/docs/design/python-openapi-design.md).

## Use with Open WebUI

1. Run `iflow-search-openapi` somewhere Open WebUI can reach.
   - Same host as Open WebUI: defaults are fine.
   - Open WebUI in Docker, this server on the host: bind with `IFLOW_OPENAPI_HOST=0.0.0.0` and use `http://host.docker.internal:<port>` from inside the container.
2. In Open WebUI → **Settings → Admin Settings → Tools → External Tool Servers → Add Connection**, paste the server URL (e.g. `http://host.docker.internal:8787`). The path defaults to `openapi.json`.
3. If you set `IFLOW_OPENAPI_AUTH_TOKEN`, choose **Bearer** auth and paste the token. Otherwise leave auth as **None** — the server is open, exactly as configured.
4. Open WebUI fetches `/openapi.json` and registers the three tools. They appear as `iflow_web_search`, `iflow_image_search`, `iflow_web_fetch` in the model's tool list (matching the explicit `operationId` values).

If Open WebUI runs in a browser on a different origin from this server, set `IFLOW_OPENAPI_CORS_ORIGIN=https://your-open-webui-host`.

The same registration can be driven over HTTP for headless setups — POST to `/api/v1/configs/tool_servers` on Open WebUI with a `TOOL_SERVER_CONNECTIONS` payload mirroring the UI fields above.

## Use with Coze

1. Run `iflow-search-openapi` somewhere Coze can reach.
2. Coze → **Plugins → Create plugin → Import from OpenAPI** → URL `http://your-host:8787/openapi.json`.
3. Provide the bearer token (`IFLOW_OPENAPI_AUTH_TOKEN`) when prompted.
4. The three tools appear as plugin actions; attach to a bot as usual.

## Authentication

Two distinct credentials:

| Credential | Direction | Source |
|---|---|---|
| `IFLOW_API_KEY` | this server → iFlow API | env, required |
| `IFLOW_OPENAPI_AUTH_TOKEN` | external client → this server | env, optional |

When `IFLOW_OPENAPI_AUTH_TOKEN` is **unset**, the server is open: any caller that can reach the socket can invoke the tools. Intended for local dev or behind a private network / reverse proxy.

When **set**, all routes except `/health` require `Authorization: Bearer <token>`. The compare is constant-time. `/openapi.json` is also gated so the schema (which advertises the server as an iFlow proxy) stays behind the bearer.

`IFLOW_API_KEY` is **never** echoed in any response, log line, OpenAPI schema, or startup banner — only its *presence* is implied by the server having started successfully.

## Configuration

All configuration is via environment variables. **No `.env` loader. No CLI flags. No config file.**

| Variable | Required | Default | Notes |
|---|---|---|---|
| `IFLOW_API_KEY` | yes | — | iFlow API key. Read once at startup, never echoed. |
| `IFLOW_BASE_URL` | no | core default | Override iFlow API base URL (staging/proxy). |
| `IFLOW_TIMEOUT_MS` | no | `30000` | Per-request timeout in milliseconds. |
| `IFLOW_OPENAPI_HOST` | no | `127.0.0.1` | Bind address. Use `0.0.0.0` for LAN/container exposure. |
| `IFLOW_OPENAPI_PORT` | no | `8787` | Bind port. |
| `IFLOW_OPENAPI_AUTH_TOKEN` | no | unset (open mode) | Bearer token required from external callers when set. |
| `IFLOW_OPENAPI_CORS_ORIGIN` | no | unset (no CORS) | `*` or an exact origin (`https://host[:port]`). |
| `IFLOW_OPENAPI_CLIENT` | no | unset | Free-form host name (e.g. `open-webui`). Banner only — not on the wire. |

### Heroku / App Engine / fly.io — bridging `PORT`

This package uses `IFLOW_OPENAPI_PORT` instead of the generic `PORT` so a platform's auto-injected port can't silently take over the bind. If your platform requires `PORT`, bridge it in your start command:

```bash
IFLOW_OPENAPI_PORT="$PORT" IFLOW_OPENAPI_HOST=0.0.0.0 iflow-search-openapi
```

## CORS

`IFLOW_OPENAPI_CORS_ORIGIN`:

- **unset** — no CORS headers; server is intended for same-origin or server-to-server use.
- `*` — wildcard allow-origin.
- `http(s)://host[:port]` — exact-origin allow.

Anything with a path, query, fragment, or non-printable character is rejected at startup with `ConfigError` and exit code 1 — header-injection guard.

Preflight (`OPTIONS`) short-circuits before the bearer check and returns HTTP 200 with the correct `Access-Control-Allow-*` headers, so browser-side tool importers (Open WebUI) can complete preflight without a token.

`Access-Control-Allow-Headers` is `Content-Type, Authorization, X-Session-Id`. `X-Session-Id` is allowed for Open WebUI compatibility; the adapter does not read it.

## Attribution

The adapter does not construct any `Authorization`, `IFlow-*`, or `User-Agent` header itself — that's the core SDK's job. Outbound requests to iFlow carry:

| Header | Value |
|---|---|
| `Authorization` | `Bearer <IFLOW_API_KEY>` |
| `IFlow-Source` | `openapi` |
| `IFlow-Integration` | `iflow-search-openapi` |
| `IFlow-Integration-Version` | this package's `__version__` |
| `User-Agent` | `iflow-search-openapi/<version>` |

`IFLOW_OPENAPI_CLIENT` is **not** forwarded as a wire header (that namespace belongs to MCP transports). It appears in the startup banner only.

## What's not included in v0.1.0a0

- TLS termination — put a reverse proxy in front.
- Streaming / SSE / WebSocket — iFlow Search is request/response.
- Per-platform packages (no `iflow-search-open-webui`, no `iflow-search-coze`).
- A public Python embedding API (`build_app(...)` is underscore-prefixed and not part of the contract).
- `.env` file loading, a CLI flag for the API key, or any config file.
- Per-request access logs — operators put a reverse proxy in front for those.

## Public Python surface

```python
from iflow_search_openapi import __version__
```

That is the only supported import in MVP. Internal modules (`_app`, `_routes`, `_auth`, etc.) are underscore-prefixed; they may be reorganised without notice. The stable contract is the **HTTP surface**, not the Python surface.

## Local development

From `packages/iflow-search-openapi/`:

```bash
python -m pip install -e ".[dev]"
python -m pytest -q
python -m ruff check .
python -m mypy src/iflow_search_openapi
python -m build
```

## Real-API smoke

```bash
cd packages/iflow-search-openapi
export IFLOW_API_KEY="your-api-key"
export IFLOW_OPENAPI_SMOKE=1
python scripts/smoke_real_api.py
```

The script:

- Is **opt-in** — without `IFLOW_OPENAPI_SMOKE=1` it refuses to call the live API.
- Reads `IFLOW_API_KEY` from the environment only — never from disk.
- Redacts the key in all log output.
- Does not write any file.

## License

[MIT](./LICENSE)
