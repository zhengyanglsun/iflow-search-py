"""LLM-facing content summary builders per design §9."""

from __future__ import annotations

from iflow_search import (
    ImageResult,
    ImageSearchResponse,
    WebFetchResponse,
    WebSearchResponse,
    WebSearchResult,
)

from iflow_search_langchain._format import (
    format_image_search,
    format_web_fetch,
    format_web_search,
)


def test_format_web_search_zero_results() -> None:
    resp = WebSearchResponse(query="flash attention", results=[])
    out = format_web_search(resp)
    assert "0 results" in out
    assert "flash attention" in out


def test_format_web_search_includes_titles_and_urls() -> None:
    resp = WebSearchResponse(
        query="flash attention",
        results=[
            WebSearchResult(title="Paper A", url="https://a", snippet="Lorem ipsum"),
            WebSearchResult(title="Paper B", url="https://b", snippet="Dolor sit"),
        ],
    )
    out = format_web_search(resp)
    assert "2 results" in out
    assert "Paper A" in out and "https://a" in out
    assert "Paper B" in out and "https://b" in out
    assert "Lorem ipsum" in out


def test_format_web_search_truncates_long_snippet() -> None:
    long = "x" * 1000
    resp = WebSearchResponse(
        query="q",
        results=[WebSearchResult(title="T", url="https://t", snippet=long)],
    )
    out = format_web_search(resp)
    assert len(out) < 600


def test_format_image_search_zero_results() -> None:
    resp = ImageSearchResponse(query="cat", images=[])
    out = format_image_search(resp)
    assert "0 images" in out
    assert "cat" in out


def test_format_image_search_lists_urls() -> None:
    resp = ImageSearchResponse(
        query="cat",
        images=[
            ImageResult(image_url="https://img1", source_url="https://page1"),
            ImageResult(image_url="https://img2", source_url="https://page2"),
        ],
    )
    out = format_image_search(resp)
    assert "2 images" in out
    assert "https://img1" in out and "https://page1" in out
    assert "https://img2" in out and "https://page2" in out


def test_format_web_fetch_includes_title_and_content_prefix() -> None:
    resp = WebFetchResponse(
        url="https://e.com",
        title="Example Domain",
        content="Hello world. " * 100,
    )
    out = format_web_fetch(resp)
    assert "Example Domain" in out
    assert "Hello world" in out


def test_format_web_fetch_truncates_long_content() -> None:
    resp = WebFetchResponse(url="https://e.com", title="T", content="x" * 5000)
    out = format_web_fetch(resp)
    assert len(out) < 800


def test_format_web_fetch_empty_content() -> None:
    resp = WebFetchResponse(url="https://e.com", title="T", content="")
    out = format_web_fetch(resp)
    assert "T" in out
