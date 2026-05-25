"""API key / bearer token never leak to any output (design §15, §14).

Spawns the CLI under several error conditions and asserts that neither the
literal ``sk-`` prefix nor the configured bearer-token string appear anywhere
in stdout or stderr. Also exercises the in-process error-envelope path to
verify HTTP responses never echo credentials.
"""

from __future__ import annotations

import os
import signal
import socket
import subprocess
import sys
import time
from collections.abc import Callable

import httpx
import pytest
from conftest import envelope, make_config

_SECRET_API_KEY = b"sk-leak-test-token-value-9999"
_SECRET_BEARER = b"bearer-leak-test-token-zzzz"


def _baseline_env() -> dict[str, str]:
    env = {k: v for k, v in os.environ.items() if k.startswith("PATH") or k == "HOME"}
    env["PYTHONPATH"] = os.pathsep.join(sys.path)
    return env


def _pick_free_port() -> int:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def _spawn(env: dict[str, str]) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        [sys.executable, "-m", "iflow_search_openapi._bin"],
        env=env,
        input=b"",
        capture_output=True,
        timeout=10,
    )


# --- CLI / subprocess paths -------------------------------------------------


def test_invalid_timeout_does_not_leak_api_key() -> None:
    env = _baseline_env()
    env["IFLOW_API_KEY"] = _SECRET_API_KEY.decode()
    env["IFLOW_TIMEOUT_MS"] = "not-a-number"
    proc = _spawn(env)
    assert proc.returncode == 1
    assert _SECRET_API_KEY not in proc.stdout
    assert _SECRET_API_KEY not in proc.stderr
    assert b"sk-" not in proc.stdout
    assert b"sk-" not in proc.stderr


def test_invalid_port_does_not_leak_api_key() -> None:
    env = _baseline_env()
    env["IFLOW_API_KEY"] = _SECRET_API_KEY.decode()
    env["IFLOW_OPENAPI_PORT"] = "70000"
    proc = _spawn(env)
    assert proc.returncode == 1
    assert _SECRET_API_KEY not in proc.stderr
    assert b"sk-" not in proc.stderr


def test_invalid_cors_does_not_leak_api_key() -> None:
    env = _baseline_env()
    env["IFLOW_API_KEY"] = _SECRET_API_KEY.decode()
    env["IFLOW_OPENAPI_CORS_ORIGIN"] = "definitely not an origin"
    proc = _spawn(env)
    assert proc.returncode == 1
    assert _SECRET_API_KEY not in proc.stderr


def test_good_env_banner_does_not_leak_credentials() -> None:
    port = _pick_free_port()
    env = _baseline_env()
    env["IFLOW_API_KEY"] = _SECRET_API_KEY.decode()
    env["IFLOW_OPENAPI_AUTH_TOKEN"] = _SECRET_BEARER.decode()
    env["IFLOW_OPENAPI_HOST"] = "127.0.0.1"
    env["IFLOW_OPENAPI_PORT"] = str(port)
    env["IFLOW_OPENAPI_CORS_ORIGIN"] = "*"
    proc = subprocess.Popen(
        [sys.executable, "-m", "iflow_search_openapi._bin"],
        env=env,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    try:
        deadline = time.monotonic() + 5.0
        listening = False
        while time.monotonic() < deadline:
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
    assert _SECRET_API_KEY not in stdout
    assert _SECRET_API_KEY not in stderr
    assert _SECRET_BEARER not in stdout
    assert _SECRET_BEARER not in stderr
    assert b"sk-" not in stdout
    assert b"sk-" not in stderr


def _port_open(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.1)
        try:
            s.connect(("127.0.0.1", port))
            return True
        except (ConnectionRefusedError, OSError):
            return False


# --- In-process error-envelope paths ----------------------------------------


@pytest.mark.asyncio
async def test_wrong_bearer_does_not_leak_configured_token(
    client_factory: Callable[..., tuple],
) -> None:
    cfg = make_config(
        api_key="sk-real-upstream-creds-DO-NOT-LEAK",
        auth_token="bearer-DO-NOT-LEAK-via-response",
    )

    def _h(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=envelope(data={"query": "x", "results": [], "tookMs": 0}))

    test_client, _core, _rec = client_factory(upstream_handler=_h, config=cfg)
    resp = await test_client.post(
        "/tools/iflow_web_search",
        json={"query": "x"},
        headers={"Authorization": "Bearer wrong"},
    )
    assert resp.status_code == 401
    assert "sk-real-upstream-creds-DO-NOT-LEAK" not in resp.text
    assert "bearer-DO-NOT-LEAK-via-response" not in resp.text


@pytest.mark.asyncio
async def test_upstream_error_envelope_does_not_leak_api_key(
    client_factory: Callable[..., tuple],
) -> None:
    cfg = make_config(api_key="sk-real-upstream-creds-DO-NOT-LEAK")

    def _h(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json=envelope(success=False, code="90402", message="bad upstream key"),
        )

    test_client, _core, _rec = client_factory(upstream_handler=_h, config=cfg)
    resp = await test_client.post("/tools/iflow_web_search", json={"query": "x"})
    assert "sk-real-upstream-creds-DO-NOT-LEAK" not in resp.text


@pytest.mark.asyncio
async def test_validation_error_envelope_does_not_leak_api_key(
    client_factory: Callable[..., tuple],
) -> None:
    cfg = make_config(api_key="sk-real-upstream-creds-DO-NOT-LEAK")

    def _h(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=envelope(data={"query": "x", "results": [], "tookMs": 0}))

    test_client, _core, _rec = client_factory(upstream_handler=_h, config=cfg)
    resp = await test_client.post("/tools/iflow_web_search", json={"query": "", "count": -3})
    assert resp.status_code == 400
    assert "sk-real-upstream-creds-DO-NOT-LEAK" not in resp.text
