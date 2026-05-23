"""``_run`` exercises the sync client, returns ``(content, artifact)``, and
emits the wire-format renames inherited from the core."""

from __future__ import annotations

import json
from collections.abc import Callable

import httpx
from iflow_search import IFlowSearchClient

from iflow_search_langchain._tools import (
    _ImageSearchTool,
    _WebFetchTool,
    _WebSearchTool,
)


def _ok_response(envelope: dict) -> httpx.Response:
    return httpx.Response(200, json=envelope)


def _make_sync(transport: httpx.MockTransport) -> IFlowSearchClient:
    return IFlowSearchClient(
        api_key="test-key",
        http_client=httpx.Client(transport=transport),
    )


def test_web_search_run_calls_endpoint_with_renamed_fields(
    make_mock_transport: Callable, fake_envelope: Callable
) -> None:
    envelope = fake_envelope(
        data={
            "organic": [
                {"title": "A", "link": "https://a", "snippet": "alpha"},
                {"title": "B", "link": "https://b", "snippet": "beta"},
            ]
        }
    )
    transport, recorder = make_mock_transport(lambda req: _ok_response(envelope))
    sync_client = _make_sync(transport)

    tool = _WebSearchTool(sync_client=sync_client, async_client=sync_client)  # type: ignore[arg-type]

    content, artifact = tool._run(query="flash attention", count=2)

    assert len(recorder.calls) == 1
    call = recorder.calls[0]
    assert call.url.endswith("/api/search/webSearch")
    body = json.loads(call.body)
    assert body == {"keywords": "flash attention", "num": 2}

    assert isinstance(content, str)
    assert "flash attention" in content
    assert "https://a" in content

    assert isinstance(artifact, dict)
    assert artifact["query"] == "flash attention"
    assert "raw" in artifact
    assert artifact["raw"] == envelope


def test_web_search_run_omits_count_when_none(
    make_mock_transport: Callable, fake_envelope: Callable
) -> None:
    transport, recorder = make_mock_transport(
        lambda req: _ok_response(fake_envelope(data={"organic": []}))
    )
    sync_client = _make_sync(transport)

    tool = _WebSearchTool(sync_client=sync_client, async_client=sync_client)  # type: ignore[arg-type]
    tool._run(query="x", count=None)

    body = json.loads(recorder.calls[0].body)
    assert body == {"keywords": "x"}


def test_image_search_run_calls_endpoint(
    make_mock_transport: Callable, fake_envelope: Callable
) -> None:
    envelope = fake_envelope(
        data=[
            {"url": "https://img1", "refUrl": "https://page1", "title": "T1"},
        ]
    )
    transport, recorder = make_mock_transport(lambda req: _ok_response(envelope))
    sync_client = _make_sync(transport)
    tool = _ImageSearchTool(sync_client=sync_client, async_client=sync_client)  # type: ignore[arg-type]

    content, artifact = tool._run(query="cat", count=1)

    assert recorder.calls[0].url.endswith("/api/search/imageSearch")
    assert json.loads(recorder.calls[0].body) == {"keywords": "cat", "num": 1}
    assert isinstance(content, str)
    assert "https://img1" in content
    assert artifact["query"] == "cat"
    assert artifact["images"][0]["image_url"] == "https://img1"
    assert artifact["images"][0]["source_url"] == "https://page1"


def test_web_fetch_run_calls_endpoint(
    make_mock_transport: Callable, fake_envelope: Callable
) -> None:
    envelope = fake_envelope(
        data={
            "url": "https://e.com",
            "title": "Example",
            "content": "Hello.",
            "fromCache": True,
        }
    )
    transport, recorder = make_mock_transport(lambda req: _ok_response(envelope))
    sync_client = _make_sync(transport)
    tool = _WebFetchTool(sync_client=sync_client, async_client=sync_client)  # type: ignore[arg-type]

    content, artifact = tool._run(url="https://e.com")

    assert recorder.calls[0].url.endswith("/api/search/webFetch")
    assert json.loads(recorder.calls[0].body) == {"url": "https://e.com"}
    assert "Example" in content
    assert artifact["url"] == "https://e.com"
    assert artifact["from_cache"] is True


def test_tools_have_response_format_content_and_artifact() -> None:
    assert _WebSearchTool.model_fields["response_format"].default == "content_and_artifact"
    assert _ImageSearchTool.model_fields["response_format"].default == "content_and_artifact"
    assert _WebFetchTool.model_fields["response_format"].default == "content_and_artifact"


def test_tool_names_match_design_spec() -> None:
    assert _WebSearchTool.model_fields["name"].default == "iflow_web_search"
    assert _ImageSearchTool.model_fields["name"].default == "iflow_image_search"
    assert _WebFetchTool.model_fields["name"].default == "iflow_web_fetch"


def test_tools_have_nonempty_description() -> None:
    for cls in (_WebSearchTool, _ImageSearchTool, _WebFetchTool):
        desc = cls.model_fields["description"].default
        assert isinstance(desc, str)
        assert len(desc) > 20
