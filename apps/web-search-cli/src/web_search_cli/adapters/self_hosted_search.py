"""Self-hosted SearXNG JSON API adapter."""

from __future__ import annotations

import json
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any, cast

from web_search_cli.adapters.query_domain_filters import (
    build_query_with_include_domains,
)
from web_search_cli.adapters.result_normalization import (
    DiscoverySearchCandidate,
    normalize_discovery_results,
)
from web_search_cli.config import AppConfig
from web_search_cli.contracts.request import WebSearchRequest
from web_search_cli.contracts.response import (
    WebSearchResponse,
    WebSearchResultResponse,
)
from web_search_cli.ports.search_port import WebSearchPort

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


class SelfHostedSearchAdapter(WebSearchPort):
    """Concrete adapter for a local self-hosted SearXNG instance."""

    def __init__(self, config: AppConfig) -> None:
        """Store environment-derived connection settings."""
        self._config = config

    def search(self, request: WebSearchRequest) -> WebSearchResponse:
        """Call the SearXNG API and normalize the returned results."""
        payload = _call_searxng(
            search_url=self._config.searxng_search_url,
            query=request.query,
            include_domains=request.include_domains,
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
        normalized_results = cast(tuple[NormalizedSearxngResult, ...], normalized["results"])
        return WebSearchResponse(
            query=request.query,
            results=tuple(
                WebSearchResultResponse(
                    title=item.title,
                    url=item.url,
                    host=item.host,
                    snippet=item.snippet,
                    engines=item.engines,
                    category=item.category,
                    score=item.score,
                )
                for item in normalized_results
            ),
        )


def _call_searxng(
    *,
    search_url: str,
    query: str,
    include_domains: tuple[str, ...],
    engines: tuple[str, ...],
    language: str,
    desired_result_count: int,
) -> dict[str, Any]:
    """Call the SearXNG JSON API and merge paginated results."""
    effective_query = build_query_with_include_domains(
        query=query,
        include_domains=include_domains,
    )
    merged_payload: dict[str, Any] | None = None
    merged_results: list[dict[str, Any]] = []
    seen_urls: set[str] = set()

    for page_no in range(1, SEARXNG_MAX_FETCH_PAGES + 1):
        params = {
            "q": effective_query,
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
) -> dict[str, object]:
    """Filter and rank raw SearXNG results for price research discovery."""
    candidates: list[DiscoverySearchCandidate] = []

    for item in payload.get("results", []):
        url = str(item.get("url") or "").strip()
        if not url:
            continue
        parsed_url = urllib.parse.urlparse(url)
        candidates.append(
            DiscoverySearchCandidate(
                title=str(item.get("title") or "").strip(),
                url=url,
                host=parsed_url.netloc.lower(),
                snippet=str(item.get("content") or "").strip(),
                engines=tuple(str(engine) for engine in item.get("engines") or []),
                category=str(item.get("category")) if item.get("category") is not None else None,
                score=float(item["score"]) if item.get("score") is not None else None,
                path=parsed_url.path.lower(),
            )
        )

    normalized = normalize_discovery_results(
        query=str(payload.get("query") or ""),
        candidates=tuple(candidates),
        limit=limit,
        include_domains=include_domains,
        exclude_domains=exclude_domains,
        enable_price_research_normalize=enable_price_research_normalize,
    )
    return {
        "query": normalized["query"],
        "results": tuple(
            NormalizedSearxngResult(
                title=item.title,
                url=item.url,
                host=item.host,
                snippet=item.snippet,
                engines=item.engines,
                category=item.category,
                score=item.score,
            )
            for item in cast(tuple[DiscoverySearchCandidate, ...], normalized["results"])
        ),
    }
