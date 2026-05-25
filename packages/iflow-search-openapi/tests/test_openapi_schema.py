"""GET /openapi.json — generated schema shape (design §7.4, §6.2)."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

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
async def test_operation_ids_are_stable_tool_names(
    client_factory: Callable[..., tuple],
) -> None:
    # Open WebUI and Coze dispatch tools by OpenAPI operationId — that's the
    # name surfaced to the consuming LLM. FastAPI defaults derive ugly IDs
    # like "web_search_tools_iflow_web_search_post" from the handler name;
    # we pin explicit IDs so the LLM sees iflow_web_search / iflow_image_search
    # / iflow_web_fetch on every host. See platform-smoke report 2026-05-25.
    test_client, _core, _rec = client_factory(upstream_handler=_upstream_ok)
    paths = (await test_client.get("/openapi.json")).json()["paths"]
    assert paths["/tools/iflow_web_search"]["post"]["operationId"] == "iflow_web_search"
    assert paths["/tools/iflow_image_search"]["post"]["operationId"] == "iflow_image_search"
    assert paths["/tools/iflow_web_fetch"]["post"]["operationId"] == "iflow_web_fetch"


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


# ---------------------------------------------------------------------------
# 200 response-body schemas.
#
# Coze (and any other tool host that materialises responses against the
# declared schema) drops fields the schema does not enumerate. When the routes
# return a bare ``JSONResponse`` and declare no ``response_model``, FastAPI
# emits an empty ``"schema": {}`` for the 200 response, which Coze rejects at
# import time and which causes payload-stripping at runtime. These tests pin
# the success-envelope shape so the canonical schema is importable everywhere.
# See platform-smoke report 2026-05-25.
# ---------------------------------------------------------------------------


def _resolve_ref(schema: dict, ref: str) -> dict:
    """Walk a ``"#/components/schemas/Name"`` ref to its component dict."""
    assert ref.startswith("#/"), ref
    node: Any = schema
    for part in ref[2:].split("/"):
        node = node[part]
    return node


def _resolve_response_schema(schema: dict, tool_path: str) -> dict:
    raw = schema["paths"][tool_path]["post"]["responses"]["200"]["content"]["application/json"][
        "schema"
    ]
    return _resolve_ref(schema, raw["$ref"]) if "$ref" in raw else raw


def _resolve_property(schema: dict, parent: dict, prop_name: str) -> dict:
    prop = parent["properties"][prop_name]
    return _resolve_ref(schema, prop["$ref"]) if "$ref" in prop else prop


@pytest.mark.asyncio
async def test_tool_200_schemas_are_non_empty_envelopes(
    client_factory: Callable[..., tuple],
) -> None:
    test_client, _core, _rec = client_factory(upstream_handler=_upstream_ok)
    schema = (await test_client.get("/openapi.json")).json()
    for tool in (
        "/tools/iflow_web_search",
        "/tools/iflow_image_search",
        "/tools/iflow_web_fetch",
    ):
        envelope_schema = _resolve_response_schema(schema, tool)
        assert envelope_schema.get("type") == "object", tool
        # No bare empty schemas. Coze rejects these as
        # "API response schema must be json object/array".
        assert envelope_schema.get("properties"), tool
        assert "ok" in envelope_schema["properties"], tool
        assert "data" in envelope_schema["properties"], tool
        # ``ok`` and ``data`` must both be required on the success envelope —
        # the consuming LLM cannot tell a missing field from a falsy one.
        assert set(envelope_schema.get("required", [])) >= {"ok", "data"}, tool


@pytest.mark.asyncio
async def test_web_search_200_data_shape(
    client_factory: Callable[..., tuple],
) -> None:
    test_client, _core, _rec = client_factory(upstream_handler=_upstream_ok)
    schema = (await test_client.get("/openapi.json")).json()
    envelope_schema = _resolve_response_schema(schema, "/tools/iflow_web_search")
    data = _resolve_property(schema, envelope_schema, "data")
    assert data["type"] == "object"
    assert set(data["properties"]) >= {"query", "results", "took_ms"}
    assert set(data["required"]) >= {"query", "results", "took_ms"}
    results_schema = data["properties"]["results"]
    assert results_schema["type"] == "array"
    item = (
        _resolve_ref(schema, results_schema["items"]["$ref"])
        if "$ref" in results_schema["items"]
        else results_schema["items"]
    )
    assert item["type"] == "object"
    assert set(item["properties"]) >= {"title", "url", "snippet", "position", "date"}


@pytest.mark.asyncio
async def test_image_search_200_data_shape(
    client_factory: Callable[..., tuple],
) -> None:
    test_client, _core, _rec = client_factory(upstream_handler=_upstream_ok)
    schema = (await test_client.get("/openapi.json")).json()
    envelope_schema = _resolve_response_schema(schema, "/tools/iflow_image_search")
    data = _resolve_property(schema, envelope_schema, "data")
    assert data["type"] == "object"
    assert set(data["properties"]) >= {"query", "images", "took_ms"}
    assert set(data["required"]) >= {"query", "images", "took_ms"}
    images_schema = data["properties"]["images"]
    assert images_schema["type"] == "array"
    item = (
        _resolve_ref(schema, images_schema["items"]["$ref"])
        if "$ref" in images_schema["items"]
        else images_schema["items"]
    )
    assert item["type"] == "object"
    assert set(item["properties"]) >= {
        "image_url",
        "source_url",
        "title",
        "width",
        "height",
        "position",
    }


@pytest.mark.asyncio
async def test_web_fetch_200_data_shape(
    client_factory: Callable[..., tuple],
) -> None:
    test_client, _core, _rec = client_factory(upstream_handler=_upstream_ok)
    schema = (await test_client.get("/openapi.json")).json()
    envelope_schema = _resolve_response_schema(schema, "/tools/iflow_web_fetch")
    data = _resolve_property(schema, envelope_schema, "data")
    assert data["type"] == "object"
    expected = {"url", "title", "content", "from_cache", "took_ms"}
    assert set(data["properties"]) >= expected
    # ``url``, ``content``, and ``took_ms`` are the load-bearing fields the LLM
    # consumes; ``title`` and ``from_cache`` are informational.
    assert set(data["required"]) >= {"url", "content", "took_ms"}
