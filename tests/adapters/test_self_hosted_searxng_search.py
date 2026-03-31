"""Tests for the self-hosted SearXNG adapter."""

from __future__ import annotations

from urllib.parse import urlparse

from searxng_search_cli.adapters.self_hosted_search import (
    _desired_searxng_result_count,
    _normalize_searxng_results,
)


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

    assert normalized["query"] == payload["query"]
    assert len(normalized["results"]) == 1
    assert normalized["results"][0].host == urlparse(payload["results"][0]["url"]).netloc


def test_normalize_searxng_results_prioritizes_included_domains() -> None:
    """Preferred domains should be ranked ahead of other surviving results."""
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
        ],
    }

    normalized = _normalize_searxng_results(
        payload=payload,
        limit=5,
        include_domains=("microsoft.com",),
        exclude_domains=(),
        enable_price_research_normalize=True,
    )

    expected_hosts = [
        urlparse(payload["results"][1]["url"]).netloc,
        urlparse(payload["results"][0]["url"]).netloc,
    ]
    assert [item.host for item in normalized["results"]] == expected_hosts


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

    expected_hosts = [urlparse(item["url"]).netloc for item in payload["results"]]
    assert [item.host for item in normalized["results"]] == expected_hosts
