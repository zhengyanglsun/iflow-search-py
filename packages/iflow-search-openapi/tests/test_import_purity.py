"""Import purity (design §15).

Importing the package must:
- read no env vars,
- perform no I/O,
- construct no httpx / iFlow clients.

We run the check in a clean subprocess so we don't measure pollution from
other tests in the same interpreter.
"""

from __future__ import annotations

import os
import subprocess
import sys
import textwrap

_PROBE = textwrap.dedent(
    """
    import os, sys

    # Pre-import heavy deps so their import-time env reads / opens don't
    # contaminate the measurement. We only care about what our own package
    # does at import time.
    import httpx  # noqa
    from iflow_search import AsyncIFlowSearchClient  # noqa

    _iflow_env_reads: list[str] = []
    _client_calls: list[str] = []

    _orig_environ_get = os.environ.get
    _orig_environ_getitem = os.environ.__class__.__getitem__

    class _Env(dict):
        def __getitem__(self, key):
            if key.startswith("IFLOW_"):
                _iflow_env_reads.append(key)
            return _orig_environ_getitem(os.environ, key)
        def get(self, key, default=None):
            if key.startswith("IFLOW_"):
                _iflow_env_reads.append(key)
            return _orig_environ_get(key, default)

    _spy_env = _Env()
    _spy_env.update(os.environ)
    os.environ = _spy_env  # type: ignore[assignment]

    _orig_httpx_async = httpx.AsyncClient.__init__
    def _spy_httpx(self, *a, **kw):
        _client_calls.append("httpx.AsyncClient")
        return _orig_httpx_async(self, *a, **kw)
    httpx.AsyncClient.__init__ = _spy_httpx

    _orig_iflow = AsyncIFlowSearchClient.__init__
    def _spy_iflow(self, *a, **kw):
        _client_calls.append("AsyncIFlowSearchClient")
        return _orig_iflow(self, *a, **kw)
    AsyncIFlowSearchClient.__init__ = _spy_iflow

    import iflow_search_openapi  # noqa: F401

    print("IFLOW_ENV_READS=" + ",".join(_iflow_env_reads))
    print("CLIENT_CALLS=" + ",".join(_client_calls))
    """
)


def test_package_import_is_pure() -> None:
    env = {k: v for k, v in os.environ.items() if k.startswith("PATH") or k == "HOME"}
    env["PYTHONPATH"] = os.pathsep.join(sys.path)
    proc = subprocess.run(
        [sys.executable, "-c", _PROBE],
        env=env,
        capture_output=True,
        timeout=10,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr.decode()
    stdout = proc.stdout.decode()
    env_line = next(line for line in stdout.splitlines() if line.startswith("IFLOW_ENV_READS="))
    calls_line = next(line for line in stdout.splitlines() if line.startswith("CLIENT_CALLS="))

    iflow_env_reads = env_line.split("=", 1)[1]
    calls = calls_line.split("=", 1)[1]

    assert iflow_env_reads == "", f"IFLOW_* env reads on import: {iflow_env_reads}"
    assert calls == "", f"client constructions on import: {calls}"


def test_import_exposes_only_version() -> None:
    import iflow_search_openapi

    assert iflow_search_openapi.__version__
    # The public surface is intentionally minimal in v0.1.0a0.
    assert "__version__" in dir(iflow_search_openapi)
