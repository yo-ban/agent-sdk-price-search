"""Self-hosted SearXNG JSON API adapter."""

from __future__ import annotations

import json
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any

from searxng_search_cli.config import AppConfig
from searxng_search_cli.contracts.request import SearxngSearchRequest
from searxng_search_cli.contracts.response import (
    SearxngSearchResponse,
    SearxngSearchResultResponse,
)
from searxng_search_cli.ports.search_port import SearxngSearchPort

EXCLUDED_SEARXNG_CATEGORIES = frozenset({"videos", "video", "music"})
EXCLUDED_RESULT_HOST_KEYWORDS = (
    "youtube.com",
    "youtu.be",
    "music.youtube.com",
    "spotify.com",
    "music.apple.com",
    "x.com",
    "twitter.com",
    "instagram.com",
    "tiktok.com",
    "facebook.com",
    "m.facebook.com",
    "news.yahoo.co.jp",
)
SEARXNG_FETCH_MULTIPLIER = 3
SEARXNG_MAX_FETCH_RESULTS = 30
SEARXNG_MAX_FETCH_PAGES = 3


@dataclass(frozen=True)
class NormalizedSearxngResult:
    """Internal normalized discovery result."""

    title: str
    url: str
    host: str
    snippet: str
    engines: tuple[str, ...]
    category: str | None
    score: float | None


class SelfHostedSearxngSearchAdapter(SearxngSearchPort):
    """Concrete adapter for a local self-hosted SearXNG instance."""

    def __init__(self, config: AppConfig) -> None:
        """Store environment-derived connection settings."""
        self._config = config

    def search(self, request: SearxngSearchRequest) -> SearxngSearchResponse:
        """Call the SearXNG API and normalize the returned results."""
        payload = _call_searxng(
            search_url=self._config.searxng_search_url,
            query=request.query,
            engines=request.engines,
            language=request.language,
            desired_result_count=_desired_searxng_result_count(limit=request.limit),
        )
        normalized = _normalize_searxng_results(
            payload=payload,
            limit=request.limit,
            include_domains=request.include_domains,
            exclude_domains=request.exclude_domains,
            enable_price_research_normalize=self._config.enable_price_research_normalize,
        )
        return SearxngSearchResponse(
            query=str(normalized.get("query") or request.query),
            results=tuple(
                SearxngSearchResultResponse(
                    title=item.title,
                    url=item.url,
                    host=item.host,
                    snippet=item.snippet,
                    engines=item.engines,
                    category=item.category,
                    score=item.score,
                )
                for item in normalized["results"]
            ),
        )


def _call_searxng(
    *,
    search_url: str,
    query: str,
    engines: tuple[str, ...],
    language: str,
    desired_result_count: int,
) -> dict[str, Any]:
    """Call the SearXNG JSON API and merge paginated results."""
    merged_payload: dict[str, Any] | None = None
    merged_results: list[dict[str, Any]] = []
    seen_urls: set[str] = set()

    for page_no in range(1, SEARXNG_MAX_FETCH_PAGES + 1):
        params = {
            "q": query,
            "format": "json",
            "categories": "general",
            "pageno": page_no,
        }
        if engines:
            params["engines"] = ",".join(engines)
        if language:
            params["language"] = language
        url = _build_searxng_search_url(search_url=search_url, params=params)
        http_request = urllib.request.Request(url=url, method="GET")
        with urllib.request.urlopen(http_request, timeout=60) as response:
            payload = json.load(response)

        if merged_payload is None:
            merged_payload = payload
        page_results = payload.get("results", [])
        if not page_results:
            break
        for item in page_results:
            result_url = str(item.get("url") or "").strip()
            if not result_url or result_url in seen_urls:
                continue
            seen_urls.add(result_url)
            merged_results.append(item)
            if len(merged_results) >= desired_result_count:
                break
        if len(merged_results) >= desired_result_count:
            break

    if merged_payload is None:
        return {"query": query, "results": []}
    merged_payload["results"] = merged_results
    return merged_payload


def _build_searxng_search_url(*, search_url: str, params: dict[str, Any]) -> str:
    """Build the SearXNG API URL with encoded query parameters."""
    return f"{search_url}?{urllib.parse.urlencode(params)}"


def _desired_searxng_result_count(*, limit: int) -> int:
    """Compute the internal oversampling count before filtering."""
    return min(SEARXNG_MAX_FETCH_RESULTS, max(limit * SEARXNG_FETCH_MULTIPLIER, limit))


def _normalize_searxng_results(
    *,
    payload: dict[str, Any],
    limit: int,
    include_domains: tuple[str, ...],
    exclude_domains: tuple[str, ...],
    enable_price_research_normalize: bool,
) -> dict[str, Any]:
    """Filter and rank raw SearXNG results for price research discovery."""
    if not enable_price_research_normalize:
        return _map_raw_searxng_results(payload=payload, limit=limit)

    include_domains_lower = tuple(domain.lower() for domain in include_domains)
    exclude_domains_lower = tuple(domain.lower() for domain in exclude_domains)
    normalized_results: list[NormalizedSearxngResult] = []

    for item in payload.get("results", []):
        url = str(item.get("url") or "").strip()
        if not url:
            continue
        parsed_url = urllib.parse.urlparse(url)
        host = parsed_url.netloc.lower()
        title = str(item.get("title") or "").strip()
        snippet = str(item.get("content") or "").strip()
        category = str(item.get("category") or "").strip().lower()
        if exclude_domains_lower and any(domain in host for domain in exclude_domains_lower):
            continue
        if _should_exclude_searxng_result(
            host=host,
            path=parsed_url.path.lower(),
            category=category,
            title=title,
            snippet=snippet,
        ):
            continue
        normalized_results.append(
            NormalizedSearxngResult(
                title=title,
                url=url,
                host=host,
                snippet=snippet,
                engines=tuple(str(engine) for engine in item.get("engines") or []),
                category=str(item.get("category")) if item.get("category") is not None else None,
                score=float(item["score"]) if item.get("score") is not None else None,
            )
        )

    normalized_results.sort(
        key=lambda item: (
            not include_domains_lower
            or not any(domain in item.host for domain in include_domains_lower),
            item.host,
            item.title,
        )
    )
    return {
        "query": payload.get("query"),
        "results": normalized_results[:limit],
    }


def _map_raw_searxng_results(*, payload: dict[str, Any], limit: int) -> dict[str, Any]:
    """Map raw SearXNG results without price-research-specific filtering."""
    normalized_results: list[NormalizedSearxngResult] = []

    for item in payload.get("results", []):
        url = str(item.get("url") or "").strip()
        if not url:
            continue
        parsed_url = urllib.parse.urlparse(url)
        normalized_results.append(
            NormalizedSearxngResult(
                title=str(item.get("title") or "").strip(),
                url=url,
                host=parsed_url.netloc.lower(),
                snippet=str(item.get("content") or "").strip(),
                engines=tuple(str(engine) for engine in item.get("engines") or []),
                category=str(item.get("category")) if item.get("category") is not None else None,
                score=float(item["score"]) if item.get("score") is not None else None,
            )
        )

    return {
        "query": payload.get("query"),
        "results": normalized_results[:limit],
    }


def _should_exclude_searxng_result(
    *,
    host: str,
    path: str,
    category: str,
    title: str,
    snippet: str,
) -> bool:
    """Exclude obvious news / social / media noise without overfiltering product pages."""
    if category in EXCLUDED_SEARXNG_CATEGORIES:
        return True
    if any(keyword in host for keyword in EXCLUDED_RESULT_HOST_KEYWORDS):
        return True
    if path.startswith("/watch") or "/shorts" in path or "/reel" in path or "/videos/" in path:
        return True

    lowered_text = f"{title} {snippet}".lower()
    noisy_text_markers = (
        "official music video",
        "watch now",
        "playlist",
        "listen now",
        "music video",
        "動画",
        "ミュージック",
    )
    return any(marker in lowered_text for marker in noisy_text_markers)
