"""Tool behavior tests — fully mocked, no real network."""

from __future__ import annotations

import json
from collections.abc import Callable

import httpx
import pytest
from iflow_search import IFlowSearchClient
from pydantic import ValidationError

from iflow_search_crewai._schemas import ImageSearchInput, WebFetchInput, WebSearchInput
from iflow_search_crewai.tools import (
    IFlowImageSearchTool,
    IFlowWebFetchTool,
    IFlowWebSearchTool,
    create_iflow_search_tools,
)


def _ok_response(envelope: dict) -> httpx.Response:
    return httpx.Response(200, json=envelope)


def _make_client(transport: httpx.MockTransport) -> IFlowSearchClient:
    return IFlowSearchClient(
        api_key="test-key",
        http_client=httpx.Client(transport=transport),
    )


def test_tool_descriptions_are_non_empty() -> None:
    assert IFlowWebSearchTool().description
    assert IFlowImageSearchTool().description
    assert IFlowWebFetchTool().description


def test_create_iflow_search_tools_returns_three_instances() -> None:
    tools = create_iflow_search_tools(api_key="k")
    assert len(tools) == 3
    assert {t.name for t in tools} == {
        "iflow_web_search",
        "iflow_image_search",
        "iflow_web_fetch",
    }


def test_web_search_maps_query_and_count(
    make_mock_transport: Callable, fake_envelope: Callable, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("IFLOW_API_KEY", raising=False)
    envelope = fake_envelope(
        data={
            "organic": [
                {"title": "A", "link": "https://a.example", "snippet": "alpha"},
            ]
        }
    )
    transport, recorder = make_mock_transport(lambda req: _ok_response(envelope))
    tool = IFlowWebSearchTool(client=_make_client(transport))
    raw = tool._run(query="CrewAI integration", count=2)
    payload = json.loads(raw)

    assert len(recorder.calls) == 1
    assert recorder.calls[0].url.endswith("/api/search/webSearch")
    assert recorder.calls[0].body_json == {"keywords": "CrewAI integration", "num": 2}
    assert payload["query"] == "CrewAI integration"
    assert payload["result_count"] == 1
    assert payload["results"][0]["url"] == "https://a.example"


def test_image_search_maps_query_and_count(
    make_mock_transport: Callable, fake_envelope: Callable, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("IFLOW_API_KEY", raising=False)
    envelope = fake_envelope(
        data={
            "images": [
                {
                    "title": "Pic",
                    "imageUrl": "https://img.example/p.png",
                    "refUrl": "https://src.example",
                    "width": 100,
                    "height": 50,
                }
            ]
        }
    )
    transport, recorder = make_mock_transport(lambda req: _ok_response(envelope))
    tool = IFlowImageSearchTool(client=_make_client(transport))
    raw = tool._run(query="cherry blossom", count=3)
    payload = json.loads(raw)

    assert recorder.calls[0].url.endswith("/api/search/imageSearch")
    assert recorder.calls[0].body_json == {"keywords": "cherry blossom", "num": 3}
    assert payload["image_count"] == 1
    assert payload["images"][0]["image_url"] == "https://img.example/p.png"
    assert payload["images"][0]["width"] == 100


def test_web_fetch_maps_url(
    make_mock_transport: Callable, fake_envelope: Callable, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("IFLOW_API_KEY", raising=False)
    envelope = fake_envelope(
        data={
            "url": "https://example.com",
            "title": "Example",
            "content": "Hello world",
            "fromCache": False,
        }
    )
    transport, recorder = make_mock_transport(lambda req: _ok_response(envelope))
    tool = IFlowWebFetchTool(client=_make_client(transport))
    raw = tool._run(url="https://example.com")
    payload = json.loads(raw)

    assert recorder.calls[0].url.endswith("/api/search/webFetch")
    assert recorder.calls[0].body_json == {"url": "https://example.com"}
    assert payload["title"] == "Example"
    assert "Hello world" in payload["content"]


def test_explicit_api_key_preferred_over_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("IFLOW_API_KEY", "env-should-not-be-used")
    tool = IFlowWebSearchTool(api_key="explicit-key")
    assert tool._config.api_key == "explicit-key"


def test_auth_error_returns_json_without_leaking_key(
    make_mock_transport: Callable, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("IFLOW_API_KEY", raising=False)
    transport, _ = make_mock_transport(lambda req: httpx.Response(401, text="unauthorized"))
    tool = IFlowWebSearchTool(client=_make_client(transport))
    raw = tool._run(query="x", count=1)
    payload = json.loads(raw)
    assert "error" in payload
    assert "IFLOW_API_KEY" in payload["error"]
    assert "test-key" not in raw
    assert "Bearer" not in raw


def test_rate_limit_returns_friendly_json(
    make_mock_transport: Callable, fake_envelope: Callable, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("IFLOW_API_KEY", raising=False)
    transport, _ = make_mock_transport(
        lambda req: httpx.Response(
            200,
            json=fake_envelope(success=False, code="40303", message="rate limited"),
        )
    )
    tool = IFlowWebSearchTool(client=_make_client(transport))
    payload = json.loads(tool._run(query="x", count=1))
    assert "Rate limit" in payload["error"]


def test_count_validation_bounds() -> None:
    with pytest.raises(ValidationError):
        WebSearchInput(query="ok", count=0)
    with pytest.raises(ValidationError):
        WebSearchInput(query="ok", count=51)
    WebSearchInput(query="ok", count=50)


def test_url_validation_requires_http_scheme() -> None:
    with pytest.raises(ValidationError):
        WebFetchInput(url="ftp://example.com")
    with pytest.raises(ValidationError):
        WebFetchInput(url="example.com")
    WebFetchInput(url="https://example.com")


def test_empty_query_rejected() -> None:
    with pytest.raises(ValidationError):
        ImageSearchInput(query="")
