"""Args-schema constraints per design §7."""

from __future__ import annotations

import pytest
from pydantic import BaseModel, ValidationError

from iflow_search_langchain._schemas import (
    ImageSearchArgs,
    WebFetchArgs,
    WebSearchArgs,
)


class TestWebSearchArgs:
    def test_is_pydantic_basemodel(self) -> None:
        assert issubclass(WebSearchArgs, BaseModel)

    def test_minimal_valid(self) -> None:
        m = WebSearchArgs(query="hello")
        assert m.query == "hello"
        assert m.count is None

    def test_with_count(self) -> None:
        m = WebSearchArgs(query="hello", count=5)
        assert m.count == 5

    def test_empty_query_rejected(self) -> None:
        with pytest.raises(ValidationError):
            WebSearchArgs(query="")

    def test_count_zero_rejected(self) -> None:
        with pytest.raises(ValidationError):
            WebSearchArgs(query="x", count=0)

    def test_count_negative_rejected(self) -> None:
        with pytest.raises(ValidationError):
            WebSearchArgs(query="x", count=-1)

    def test_count_large_value_accepted(self) -> None:
        m = WebSearchArgs(query="x", count=999)
        assert m.count == 999


class TestImageSearchArgs:
    def test_is_pydantic_basemodel(self) -> None:
        assert issubclass(ImageSearchArgs, BaseModel)

    def test_minimal_valid(self) -> None:
        m = ImageSearchArgs(query="cat")
        assert m.query == "cat"
        assert m.count is None

    def test_empty_query_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ImageSearchArgs(query="")

    def test_count_zero_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ImageSearchArgs(query="x", count=0)

    def test_count_large_value_accepted(self) -> None:
        m = ImageSearchArgs(query="x", count=500)
        assert m.count == 500


class TestWebFetchArgs:
    def test_is_pydantic_basemodel(self) -> None:
        assert issubclass(WebFetchArgs, BaseModel)

    def test_minimal_valid(self) -> None:
        m = WebFetchArgs(url="https://example.com")
        assert m.url == "https://example.com"

    def test_empty_url_rejected(self) -> None:
        with pytest.raises(ValidationError):
            WebFetchArgs(url="")
