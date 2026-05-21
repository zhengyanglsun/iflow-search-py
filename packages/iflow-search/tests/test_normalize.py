"""Tests for envelope normalization and field-rename behavior."""

from __future__ import annotations

from iflow_search._normalize import (
    build_image_search_response,
    build_web_fetch_response,
    build_web_search_response,
    truncate_body,
)


def test_web_search_renames_link_to_url() -> None:
    data = {
        "query": "flash attention",
        "organic": [
            {"title": "T1", "link": "https://example.com/1", "snippet": "s1", "position": 1},
            {"title": "T2", "link": "https://example.com/2", "snippet": "s2", "position": 2},
        ],
    }
    raw = {"success": True, "code": "200", "data": data}
    out = build_web_search_response(data=data, raw=raw, took_ms=42, query_echo="flash attention")
    assert out.query == "flash attention"
    assert len(out.results) == 2
    assert out.results[0].url == "https://example.com/1"
    assert out.results[1].url == "https://example.com/2"
    assert out.took_ms == 42
    assert out.raw == raw


def test_image_search_bare_array_data() -> None:
    """iFlow returns ``data`` as a bare list for image search — handle it."""
    items = [
        {"url": "https://img/1.jpg", "refUrl": "https://src/1", "title": "i1"},
        {"url": "https://img/2.jpg", "refUrl": "https://src/2", "title": "i2"},
    ]
    raw = {"success": True, "code": "200", "data": items}
    out = build_image_search_response(data=items, raw=raw, took_ms=10, query_echo="q")
    assert len(out.images) == 2
    assert out.images[0].image_url == "https://img/1.jpg"
    assert out.images[0].source_url == "https://src/1"
    assert out.images[1].title == "i2"


def test_image_search_dict_data_also_supported() -> None:
    """Belt-and-braces: if iFlow ever returns ``data: {images: [...]}``, handle that too."""
    data = {"images": [{"url": "https://img/x", "refUrl": "https://src/x", "title": "x"}]}
    raw = {"success": True, "code": "200", "data": data}
    out = build_image_search_response(data=data, raw=raw, took_ms=5, query_echo="q")
    assert len(out.images) == 1
    assert out.images[0].image_url == "https://img/x"


def test_web_fetch_renames_from_cache() -> None:
    data = {
        "title": "iFlow Docs",
        "content": "lorem ipsum",
        "url": "https://platform.iflow.cn/docs/",
        "fromCache": True,
    }
    raw = {"success": True, "code": "200", "data": data}
    out = build_web_fetch_response(
        data=data, raw=raw, took_ms=12, url_echo="https://platform.iflow.cn/docs/"
    )
    assert out.title == "iFlow Docs"
    assert out.content == "lorem ipsum"
    assert out.url == "https://platform.iflow.cn/docs/"
    assert out.from_cache is True


def test_normalizer_tolerates_missing_fields() -> None:
    out = build_web_search_response(
        data={"organic": [{"title": "T"}]},  # no link/snippet
        raw={},
        took_ms=0,
        query_echo="q",
    )
    assert out.results[0].title == "T"
    assert out.results[0].url == ""
    assert out.results[0].snippet == ""


def test_normalizer_ignores_non_dict_items() -> None:
    out = build_web_search_response(
        data={"organic": [None, "garbage", {"title": "T", "link": "u"}]},
        raw={},
        took_ms=0,
        query_echo="q",
    )
    assert len(out.results) == 1
    assert out.results[0].url == "u"


def test_truncate_body_under_limit() -> None:
    assert truncate_body("short") == "short"


def test_truncate_body_at_500_chars() -> None:
    body = "x" * 600
    out = truncate_body(body)
    assert out is not None
    assert len(out) == 500


def test_truncate_body_handles_bytes() -> None:
    out = truncate_body(b"hello")
    assert out == "hello"


def test_truncate_body_handles_none() -> None:
    assert truncate_body(None) is None


def test_raw_preserved_on_response() -> None:
    raw = {"success": True, "code": "200", "message": "ok", "data": {}, "exception": None}
    out = build_web_search_response(data={}, raw=raw, took_ms=1, query_echo="q")
    assert out.raw == raw
