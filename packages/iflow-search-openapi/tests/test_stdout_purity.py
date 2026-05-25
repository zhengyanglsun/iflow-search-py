"""Stdout purity (design §15, §14).

Bad env: exit 1, all diagnostics on stderr, stdout empty.
Good env: banner on stderr, stdout empty (process is killed after the banner
appears — full lifecycle is covered by the smoke script).
"""

from __future__ import annotations

import os
import signal
import socket
import subprocess
import sys
import time


def _spawn(env: dict[str, str]) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        [sys.executable, "-m", "iflow_search_openapi._bin"],
        env=env,
        input=b"",
        capture_output=True,
        timeout=10,
    )


def _pick_free_port() -> int:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def _baseline_env() -> dict[str, str]:
    env = {k: v for k, v in os.environ.items() if k.startswith("PATH") or k == "HOME"}
    # PYTHONPATH so the subprocess can resolve the in-tree package & sibling.
    env["PYTHONPATH"] = os.pathsep.join(sys.path)
    return env


def test_missing_api_key_exits_1_with_empty_stdout() -> None:
    env = _baseline_env()
    proc = _spawn(env)
    assert proc.returncode == 1
    assert proc.stdout == b""
    assert b"IFLOW_API_KEY" in proc.stderr


def test_invalid_timeout_exits_1_with_empty_stdout() -> None:
    env = _baseline_env()
    env.update({"IFLOW_API_KEY": "test-key", "IFLOW_TIMEOUT_MS": "abc"})
    proc = _spawn(env)
    assert proc.returncode == 1
    assert proc.stdout == b""
    assert b"IFLOW_TIMEOUT_MS" in proc.stderr


def test_invalid_port_exits_1_with_empty_stdout() -> None:
    env = _baseline_env()
    env.update({"IFLOW_API_KEY": "test-key", "IFLOW_OPENAPI_PORT": "70000"})
    proc = _spawn(env)
    assert proc.returncode == 1
    assert proc.stdout == b""
    assert b"IFLOW_OPENAPI_PORT" in proc.stderr


def test_invalid_cors_origin_exits_1_with_empty_stdout() -> None:
    env = _baseline_env()
    env.update(
        {
            "IFLOW_API_KEY": "test-key",
            "IFLOW_OPENAPI_CORS_ORIGIN": "not a valid origin",
        }
    )
    proc = _spawn(env)
    assert proc.returncode == 1
    assert proc.stdout == b""
    assert b"IFLOW_OPENAPI_CORS_ORIGIN" in proc.stderr


def test_good_env_starts_with_banner_and_empty_stdout() -> None:
    port = _pick_free_port()
    env = _baseline_env()
    env.update(
        {
            "IFLOW_API_KEY": "test-key",
            "IFLOW_OPENAPI_HOST": "127.0.0.1",
            "IFLOW_OPENAPI_PORT": str(port),
        }
    )
    proc = subprocess.Popen(
        [sys.executable, "-m", "iflow_search_openapi._bin"],
        env=env,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    try:
        # Wait up to 5 s for the server to open its port.
        deadline = time.monotonic() + 5.0
        listening = False
        while time.monotonic() < deadline:
            # Non-blocking read attempt by polling the socket itself.
            if _port_open(port):
                listening = True
                break
            time.sleep(0.05)
        assert listening, "server never opened its port"
    finally:
        proc.send_signal(signal.SIGINT)
        try:
            stdout, stderr = proc.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            stdout, stderr = proc.communicate()
    assert stdout == b"", f"stdout was not empty: {stdout!r}"
    assert b"[iflow-search-openapi]" in stderr
    assert b"listening on http://127.0.0.1" in stderr
    assert b"bearer auth DISABLED (open mode)" in stderr


def _port_open(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.1)
        try:
            s.connect(("127.0.0.1", port))
            return True
        except (ConnectionRefusedError, OSError):
            return False
