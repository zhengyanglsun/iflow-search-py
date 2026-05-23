"""Stdout purity (design §5).

Stdout is the JSON-RPC stream — any non-protocol bytes break MCP clients.
Configuration failures must exit 1 with all human-readable output on stderr
and an empty stdout. The API key is never echoed.
"""

from __future__ import annotations

import subprocess
import sys


def _spawn(env: dict[str, str]) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        [sys.executable, "-m", "iflow_search_mcp._bin"],
        env=env,
        input=b"",
        capture_output=True,
        timeout=10,
    )


def test_missing_api_key_exits_1_with_empty_stdout() -> None:
    proc = _spawn({})
    assert proc.returncode == 1
    assert proc.stdout == b""
    assert b"IFLOW_API_KEY" in proc.stderr


def test_invalid_timeout_exits_1_with_empty_stdout() -> None:
    proc = _spawn({"IFLOW_API_KEY": "test-key", "IFLOW_TIMEOUT_MS": "abc"})
    assert proc.returncode == 1
    assert proc.stdout == b""
    assert b"IFLOW_TIMEOUT_MS" in proc.stderr


def test_orphan_mcp_client_version_exits_1() -> None:
    proc = _spawn(
        {
            "IFLOW_API_KEY": "test-key",
            "IFLOW_MCP_CLIENT_VERSION": "1.2.3",
        }
    )
    assert proc.returncode == 1
    assert proc.stdout == b""
    assert b"IFLOW_MCP_CLIENT" in proc.stderr


def test_api_key_value_never_appears_in_stderr() -> None:
    proc = _spawn({"IFLOW_API_KEY": "sk-super-secret-test-token", "IFLOW_TIMEOUT_MS": "abc"})
    assert proc.returncode == 1
    assert proc.stdout == b""
    assert b"sk-super-secret-test-token" not in proc.stderr
    assert b"sk-" not in proc.stderr
