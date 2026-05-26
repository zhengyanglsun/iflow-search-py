# iflow-search-mcp

[![PyPI - Version](https://img.shields.io/pypi/v/iflow-search-mcp?include_prereleases)](https://pypi.org/project/iflow-search-mcp/)
[![Python Versions](https://img.shields.io/pypi/pyversions/iflow-search-mcp)](https://pypi.org/project/iflow-search-mcp/)

**MCP stdio server for [iFlow Search](https://platform.iflow.cn/) (心流搜索).**

Exposes three MCP tools backed by the `iflow-search` core SDK:

- `iflow_web_search` — web search
- `iflow_image_search` — image search
- `iflow_web_fetch` — fetch the readable contents of a URL

This package is a thin adapter. All HTTP, authentication, attribution-header
construction, response normalization, and error mapping live in the
[`iflow-search`](https://pypi.org/project/iflow-search/) core SDK. This package
owns only the MCP server wiring — tool definitions, tool dispatch, and the
stdio entry point.

## Install

```bash
pip install --pre iflow-search-mcp
```

> The package is currently published as a PEP 440 prerelease (`0.1.0a0`), so
> the `--pre` flag is required. Installing pulls in the MCP Python SDK, which
> transitively depends on `starlette`, `uvicorn`, `sse-starlette`,
> `python-multipart`, `pyjwt[crypto]`, and `jsonschema` — even though this
> server only uses stdio. There is no `[stdio]` extra on the upstream package.

## Configure your MCP host

The server reads its configuration from environment variables only — no
`.env` files, no CLI flags, no config files.

| Variable | Required | Notes |
|---|---|---|
| `IFLOW_API_KEY` | yes | iFlow API key |
| `IFLOW_BASE_URL` | no | Override the platform base URL |
| `IFLOW_TIMEOUT_MS` | no | Request timeout in milliseconds (positive integer) |
| `IFLOW_MCP_CLIENT` | no | Identifier for the MCP host (e.g. `claude-desktop`); regex `^[a-z0-9._-]{1,64}$` |
| `IFLOW_MCP_CLIENT_VERSION` | no | Version of the MCP host; only valid when `IFLOW_MCP_CLIENT` is set |

### Example: Claude Desktop / Claude Code

```jsonc
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

Claude Code 2.1.148 has been verified to discover and connect to the
`0.1.0a0` artifact via `claude mcp list` / `claude mcp get` (stdio
`initialize` + capability exchange). The wire protocol used by `tools/call`
is exercised separately by the offline `scripts/smoke_stdio.py` and by a
reference-client smoke against the live iFlow API; see
[`docs/design/python-mcp-design.md` §15](https://github.com/zhengyanglsun/iflow-search-py/blob/main/docs/design/python-mcp-design.md#15-claude-code-direct-host-verification--010a0-2026-05-25)
for the full record.

### Example: OpenCode

OpenCode's MCP config schema differs from Claude Desktop's in a few small
ways: the root key is `mcp` (not `mcpServers`), each server declares
`type: "local"` for stdio transport, `command` is a string-array (not a
string), and the env block is named `environment` (not `env`). OpenCode
does **not** expand `${VAR}` references in that block, but it does
inherit the parent process env into the MCP child — so `IFLOW_API_KEY`
belongs in the shell you launch `opencode` from, not in `opencode.json`:

```jsonc
{
  "$schema": "https://opencode.ai/config.json",
  "mcp": {
    "iflow-search": {
      "type": "local",
      "command": ["iflow-search-mcp"],
      "enabled": true,
      "environment": {
        "IFLOW_MCP_CLIENT": "opencode"
      }
    }
  }
}
```

OpenCode 1.15.10 (installed via `brew install sst/tap/opencode`) has been
verified to discover and connect to the `0.1.0a0` artifact via
`opencode mcp list` — reports `connected · local`, and
`opencode --log-level DEBUG mcp list` records `toolCount=3` and
`successfully created client`. `opencode mcp debug` is documented as an
OAuth debugger for remote MCP servers and is not applicable to
`type: "local"` (stdio) entries; the stdio health check is
`opencode mcp list` itself. The wire protocol used by `tools/call` is
exercised separately by the reference-client smoke against the live
iFlow API; see
[`docs/design/python-mcp-design.md` §16](https://github.com/zhengyanglsun/iflow-search-py/blob/main/docs/design/python-mcp-design.md#16-opencode-direct-host-verification--010a0-2026-05-25)
for the full record.

## Behavior

- **Transport:** stdio only. `stdout` is reserved for the JSON-RPC stream;
  all human-readable output (banner, errors) goes to `stderr`.
- **Exit codes:** `0` on clean shutdown after `SIGINT` / `SIGTERM`,
  `1` on configuration or init error.
- **Errors:** tool failures return `isError: true` results with a stable
  `structuredContent.error.code` (mirroring the core SDK's error contract).

## License

MIT. See [LICENSE](LICENSE).
