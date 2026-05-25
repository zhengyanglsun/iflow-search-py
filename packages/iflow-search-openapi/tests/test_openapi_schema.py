"""GET /openapi.json — generated schema shape (design §7.4, §6.2)."""

from __future__ import annotations

from collections.abc import Callable

import httpx
import pytest
from conftest import envelope, make_config

from iflow_search_openapi._version import __version__


def _upstream_ok(_request: httpx.Request) -> httpx.Response:
    return httpx.Response(
        200,
        json=envelope(data={"query": "x", "results": [], "tookMs": 0}),
    )


@pytest.mark.asyncio
async def test_openapi_basic_shape(client_factory: Callable[..., tuple]) -> None:
    test_client, _core, _rec = client_factory(upstream_handler=_upstream_ok)
    resp = await test_client.get("/openapi.json")
    assert resp.status_code == 200
    schema = resp.json()
    assert schema["openapi"].startswith("3.1")
    assert schema["info"]["version"] == __version__
    assert "iFlow" in schema["info"]["title"]


@pytest.mark.asyncio
async def test_openapi_lists_three_tool_paths(
    client_factory: Callable[..., tuple],
) -> None:
    test_client, _core, _rec = client_factory(upstream_handler=_upstream_ok)
    resp = await test_client.get("/openapi.json")
    paths = resp.json()["paths"]
    assert "/tools/iflow_web_search" in paths
    assert "/tools/iflow_image_search" in paths
    assert "/tools/iflow_web_fetch" in paths
    for tool in (
        "/tools/iflow_web_search",
        "/tools/iflow_image_search",
        "/tools/iflow_web_fetch",
    ):
        assert "post" in paths[tool]


@pytest.mark.asyncio
async def test_request_body_schema_web_search(
    client_factory: Callable[..., tuple],
) -> None:
    test_client, _core, _rec = client_factory(upstream_handler=_upstream_ok)
    schema = (await test_client.get("/openapi.json")).json()
    ref = schema["paths"]["/tools/iflow_web_search"]["post"]["requestBody"]["content"][
        "application/json"
    ]["schema"]["$ref"]
    name = ref.split("/")[-1]
    body_schema = schema["components"]["schemas"][name]
    assert "query" in body_schema["properties"]
    assert "count" in body_schema["properties"]
    assert body_schema["required"] == ["query"]
    assert body_schema.get("additionalProperties") is False


@pytest.mark.asyncio
async def test_request_body_schema_web_fetch(
    client_factory: Callable[..., tuple],
) -> None:
    test_client, _core, _rec = client_factory(upstream_handler=_upstream_ok)
    schema = (await test_client.get("/openapi.json")).json()
    ref = schema["paths"]["/tools/iflow_web_fetch"]["post"]["requestBody"]["content"][
        "application/json"
    ]["schema"]["$ref"]
    name = ref.split("/")[-1]
    body_schema = schema["components"]["schemas"][name]
    assert body_schema["required"] == ["url"]


@pytest.mark.asyncio
async def test_security_scheme_present_when_token_configured(
    client_factory: Callable[..., tuple],
) -> None:
    cfg = make_config(auth_token="s3cret")
    test_client, _core, _rec = client_factory(upstream_handler=_upstream_ok, config=cfg)
    resp = await test_client.get("/openapi.json", headers={"Authorization": "Bearer s3cret"})
    schema = resp.json()
    assert "BearerAuth" in schema["components"]["securitySchemes"]
    assert schema["security"] == [{"BearerAuth": []}]


@pytest.mark.asyncio
async def test_security_scheme_absent_when_no_token(
    client_factory: Callable[..., tuple],
) -> None:
    test_client, _core, _rec = client_factory(upstream_handler=_upstream_ok)
    schema = (await test_client.get("/openapi.json")).json()
    assert "security" not in schema
    assert "BearerAuth" not in schema.get("components", {}).get("securitySchemes", {})
