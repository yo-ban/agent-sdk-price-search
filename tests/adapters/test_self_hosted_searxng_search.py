"""Tests for the self-hosted SearXNG-backed web search adapter."""

from __future__ import annotations

import io
import json
from typing import cast
from urllib.parse import urlparse

from web_search_cli.adapters.self_hosted_search import (
    NormalizedSearxngResult,
    _call_searxng,
    _desired_searxng_result_count,
    _normalize_searxng_results,
)


class _JsonResponse(io.StringIO):
    """Minimal context-manager response for JSON urlopen stubs."""

    def __enter__(self) -> _JsonResponse:
        """Return the stream itself."""
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        """Close the in-memory stream."""
        self.close()


def test_normalize_searxng_results_filters_social_and_news_noise() -> None:
    """Noisy social or news style results should be excluded from normalized output."""
    payload = {
        "query": "全自動コーヒーメーカー ABC-1234",
        "results": [
            {
                "title": "全自動コーヒーメーカー ABC-1234 価格比較",
                "url": "https://kakaku.com/item/K0000700536/",
                "content": "価格比較ページ",
                "engines": ["google"],
                "category": "general",
                "score": 0.5,
            },
            {
                "title": "最新ニュース",
                "url": "https://news.yahoo.co.jp/articles/example",
                "content": "news",
                "engines": ["google"],
                "category": "general",
                "score": 0.1,
            },
            {
                "title": "Official Music Video",
                "url": "https://www.youtube.com/watch?v=demo",
                "content": "watch now",
                "engines": ["google"],
                "category": "video",
                "score": 0.2,
            },
        ],
    }

    normalized = _normalize_searxng_results(
        payload=payload,
        limit=5,
        include_domains=(),
        exclude_domains=(),
        enable_price_research_normalize=True,
    )
    normalized_results = cast(tuple[NormalizedSearxngResult, ...], normalized["results"])

    assert normalized["query"] == payload["query"]
    assert len(normalized_results) == 1
    assert normalized_results[0].host == urlparse(payload["results"][0]["url"]).netloc


def test_normalize_searxng_results_filters_to_included_domains_without_reordering() -> None:
    """Included domains should behave as an allowlist and preserve source order."""
    payload = {
        "query": "全自動コーヒーメーカー ABC-1234",
        "results": [
            {
                "title": "Amazon offer",
                "url": "https://www.amazon.co.jp/dp/example",
                "content": "amazon",
                "engines": ["google"],
                "category": "general",
                "score": 0.2,
            },
            {
                "title": "Microsoft offer",
                "url": "https://www.microsoft.com/ja-jp/store/configure/example",
                "content": "microsoft",
                "engines": ["google"],
                "category": "general",
                "score": 0.3,
            },
            {
                "title": "Second Microsoft offer",
                "url": "https://www.microsoft.com/ja-jp/microsoft-365/example",
                "content": "microsoft second",
                "engines": ["google"],
                "category": "general",
                "score": 0.1,
            },
        ],
    }

    normalized = _normalize_searxng_results(
        payload=payload,
        limit=5,
        include_domains=("microsoft.com",),
        exclude_domains=(),
        enable_price_research_normalize=True,
    )
    normalized_results = cast(tuple[NormalizedSearxngResult, ...], normalized["results"])

    assert [item.host for item in normalized_results] == [
        urlparse(payload["results"][1]["url"]).netloc,
        urlparse(payload["results"][2]["url"]).netloc,
    ]
    assert [item.title for item in normalized_results] == [
        payload["results"][1]["title"],
        payload["results"][2]["title"],
    ]


def test_desired_searxng_result_count_oversamples_with_cap() -> None:
    """Internal fetch count should oversample but respect the hard cap."""
    small_limit = 1
    medium_limit = 5
    large_limit = 20
    small_result_count = _desired_searxng_result_count(limit=small_limit)
    medium_result_count = _desired_searxng_result_count(limit=medium_limit)
    large_result_count = _desired_searxng_result_count(limit=large_limit)

    assert small_result_count > small_limit
    assert medium_result_count > medium_limit
    assert large_result_count >= large_limit
    assert small_result_count < medium_result_count
    assert medium_result_count < large_result_count
    assert large_result_count == _desired_searxng_result_count(limit=large_limit * 2)


def test_call_searxng_adds_site_filters_to_query(monkeypatch) -> None:
    """Included domains should be expressed in the SearXNG-side query string."""
    captured: dict[str, object] = {}

    def fake_urlopen(request, timeout: int) -> _JsonResponse:
        captured["url"] = request.full_url
        captured["timeout"] = timeout
        return _JsonResponse(json.dumps({"query": "query", "results": []}))

    monkeypatch.setattr(
        "web_search_cli.adapters.self_hosted_search.urllib.request.urlopen",
        fake_urlopen,
    )

    _call_searxng(
        search_url="http://127.0.0.1:18888/search",
        query="Office 2024 Home",
        include_domains=("microsoft.com", "yodobashi.com"),
        engines=("google",),
        language="ja-JP",
        desired_result_count=8,
    )

    assert (
        "q=Office+2024+Home+%28site%3Amicrosoft.com+OR+site%3Ayodobashi.com%29"
        in str(captured["url"])
    )


def test_normalize_searxng_results_preserves_provider_order() -> None:
    """Normalized results should preserve provider order when no domain filter is set."""
    payload = {
        "query": "全自動コーヒーメーカー ABC-1234",
        "results": [
            {
                "title": "First surviving result",
                "url": "https://shop-a.example.com/item",
                "content": "first",
                "engines": ["google"],
                "category": "general",
                "score": 0.2,
            },
            {
                "title": "Second surviving result",
                "url": "https://shop-b.example.com/item",
                "content": "second",
                "engines": ["google"],
                "category": "general",
                "score": 0.1,
            },
        ],
    }

    normalized = _normalize_searxng_results(
        payload=payload,
        limit=5,
        include_domains=(),
        exclude_domains=(),
        enable_price_research_normalize=True,
    )
    normalized_results = cast(tuple[NormalizedSearxngResult, ...], normalized["results"])

    assert [item.title for item in normalized_results] == [
        "First surviving result",
        "Second surviving result",
    ]


def test_normalize_searxng_results_can_be_disabled() -> None:
    """Disabling price-research normalization should keep otherwise noisy results."""
    payload = {
        "query": "全自動コーヒーメーカー ABC-1234",
        "results": [
            {
                "title": "最新ニュース",
                "url": "https://news.yahoo.co.jp/articles/example",
                "content": "news",
                "engines": ["google"],
                "category": "general",
                "score": 0.1,
            },
            {
                "title": "Official Music Video",
                "url": "https://www.youtube.com/watch?v=demo",
                "content": "watch now",
                "engines": ["google"],
                "category": "video",
                "score": 0.2,
            },
        ],
    }

    normalized = _normalize_searxng_results(
        payload=payload,
        limit=5,
        include_domains=(),
        exclude_domains=(),
        enable_price_research_normalize=False,
    )
    normalized_results = cast(tuple[NormalizedSearxngResult, ...], normalized["results"])

    expected_hosts = [urlparse(item["url"]).netloc for item in payload["results"]]
    assert [item.host for item in normalized_results] == expected_hosts
