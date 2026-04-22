"""Tests for the Brave Web Search adapter."""

from __future__ import annotations

import io
import json
from typing import cast
from urllib.parse import parse_qs, urlparse
from urllib.request import Request

import pytest
from web_search_cli.adapters.brave_web_search import (
    BraveWebSearchAdapter,
    _normalize_brave_results,
)
from web_search_cli.adapters.result_normalization import DiscoverySearchCandidate
from web_search_cli.config import AppConfig
from web_search_cli.contracts.request import WebSearchRequest


class _JsonResponse(io.StringIO):
    """Minimal context-manager response for JSON urlopen stubs."""

    def __init__(self, payload: dict[str, object]) -> None:
        """Store the JSON payload and expose headers."""
        super().__init__(json.dumps(payload))
        self.headers = {"x-ratelimit-limit": "50, 0"}

    def __enter__(self) -> _JsonResponse:
        """Return the stream itself."""
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        """Close the in-memory stream."""
        self.close()


def test_brave_web_search_adapter_calls_api_and_normalizes_results(monkeypatch) -> None:
    """Brave adapter should normalize API results onto the existing CLI contract."""
    captured: dict[str, object] = {}

    def fake_urlopen(request, timeout: int) -> _JsonResponse:
        captured["request"] = request
        captured["timeout"] = timeout
        return _JsonResponse(
            {
                "query": {"original": "全自動コーヒーメーカー ABC-1234"},
                "web": {
                    "results": [
                        {
                            "title": "価格.com - 比較",
                            "url": "https://kakaku.com/item/example/",
                            "description": "価格比較ページ",
                            "extra_snippets": ["最安価格あり"],
                        }
                    ]
                },
            }
        )

    monkeypatch.setattr(
        "web_search_cli.adapters.brave_web_search.urllib.request.urlopen",
        fake_urlopen,
    )

    adapter = BraveWebSearchAdapter(config=_build_config())
    response = adapter.search(
        WebSearchRequest(
            query="全自動コーヒーメーカー ABC-1234",
            limit=3,
            language="ja-JP",
            engines=(),
            include_domains=(),
            exclude_domains=(),
        )
    )

    request = cast(Request, captured["request"])
    assert captured["timeout"] == 30
    assert request.get_header("X-subscription-token") == "test-brave-key"
    params = parse_qs(urlparse(request.full_url).query)
    assert params["q"] == ["全自動コーヒーメーカー ABC-1234"]
    assert params["search_lang"] == ["jp"]
    assert response.query == "全自動コーヒーメーカー ABC-1234"
    assert response.results[0].host == "kakaku.com"
    assert response.results[0].engines == ("brave",)
    assert "最安価格あり" in response.results[0].snippet


def test_brave_web_search_adapter_adds_site_filters_to_query(monkeypatch) -> None:
    """Included domains should be expressed in the Brave-side query string."""
    captured: dict[str, object] = {}

    def fake_urlopen(request, timeout: int) -> _JsonResponse:
        captured["request"] = request
        captured["timeout"] = timeout
        return _JsonResponse({"query": {"original": "query"}, "web": {"results": []}})

    monkeypatch.setattr(
        "web_search_cli.adapters.brave_web_search.urllib.request.urlopen",
        fake_urlopen,
    )

    adapter = BraveWebSearchAdapter(config=_build_config())
    adapter.search(
        WebSearchRequest(
            query="Office 2024 Home",
            limit=3,
            language="ja-JP",
            engines=(),
            include_domains=("microsoft.com", "yodobashi.com"),
            exclude_domains=(),
        )
    )

    request = cast(Request, captured["request"])
    params = parse_qs(urlparse(request.full_url).query)
    assert params["q"] == [
        "Office 2024 Home (site:microsoft.com OR site:yodobashi.com)"
    ]


def test_normalize_brave_results_filters_to_included_domains_without_reordering() -> None:
    """Included domains should behave as an allowlist and preserve source order."""
    payload = {
        "query": {"original": "全自動コーヒーメーカー ABC-1234"},
        "web": {
            "results": [
                {
                    "title": "Amazon offer",
                    "url": "https://www.amazon.co.jp/dp/example",
                    "description": "amazon",
                },
                {
                    "title": "Microsoft offer",
                    "url": "https://www.microsoft.com/ja-jp/store/configure/example",
                    "description": "microsoft",
                },
                {
                    "title": "Second Microsoft offer",
                    "url": "https://www.microsoft.com/ja-jp/microsoft-365/example",
                    "description": "microsoft second",
                },
            ]
        },
    }

    normalized = _normalize_brave_results(
        payload=payload,
        limit=5,
        include_domains=("microsoft.com",),
        exclude_domains=(),
        enable_price_research_normalize=True,
    )
    normalized_results = cast(tuple[DiscoverySearchCandidate, ...], normalized["results"])

    assert [item.host for item in normalized_results] == [
        "www.microsoft.com",
        "www.microsoft.com",
    ]
    assert [item.title for item in normalized_results] == [
        "Microsoft offer",
        "Second Microsoft offer",
    ]


def test_brave_web_search_adapter_requires_api_key() -> None:
    """Brave provider should fail fast when no API key is configured."""
    adapter = BraveWebSearchAdapter(config=_build_config(brave_api_key=None))

    with pytest.raises(ValueError, match="BRAVE_API_KEY"):
        adapter.search(
            WebSearchRequest(
                query="query",
                limit=3,
                language="ja-JP",
                engines=(),
                include_domains=(),
                exclude_domains=(),
            )
        )


def test_normalize_brave_results_preserves_provider_order() -> None:
    """Normalized Brave results should preserve provider order when no domain filter is set."""
    payload = {
        "query": {"original": "query"},
        "web": {
            "results": [
                {
                    "title": "First surviving result",
                    "url": "https://shop-a.example.com/item",
                    "description": "first",
                },
                {
                    "title": "Second surviving result",
                    "url": "https://shop-b.example.com/item",
                    "description": "second",
                },
            ]
        },
    }

    normalized = _normalize_brave_results(
        payload=payload,
        limit=5,
        include_domains=(),
        exclude_domains=(),
        enable_price_research_normalize=True,
    )
    normalized_results = cast(tuple[DiscoverySearchCandidate, ...], normalized["results"])

    assert [item.title for item in normalized_results] == [
        "First surviving result",
        "Second surviving result",
    ]


def _build_config(*, brave_api_key: str | None = "test-brave-key") -> AppConfig:
    """Create a representative AppConfig for Brave adapter tests."""
    return AppConfig(
        search_provider="brave",
        searxng_search_url="http://127.0.0.1:18888/search",
        searxng_engines=("google", "brave"),
        searxng_language="ja-JP",
        searxng_result_limit=8,
        enable_price_research_normalize=True,
        brave_endpoint="https://api.search.brave.com/res/v1/web/search",
        brave_api_key=brave_api_key,
        brave_country="JP",
        brave_search_lang="jp",
        brave_ui_lang="ja-JP",
        brave_result_filter=("web",),
        brave_extra_snippets=True,
    )
