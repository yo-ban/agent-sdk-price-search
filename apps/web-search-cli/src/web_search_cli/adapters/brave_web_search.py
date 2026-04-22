"""Brave Web Search adapter for discovery CLI.

Layer: Infrastructure
"""

from __future__ import annotations

import json
import urllib.error
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

BRAVE_TIMEOUT_SECONDS = 30
BRAVE_FETCH_MULTIPLIER = 3
BRAVE_MAX_COUNT = 20
BRAVE_RESULT_CATEGORY = "web"
SEARCH_LANG_ALIASES = {
    "ja": "jp",
    "ja-jp": "jp",
    "jp": "jp",
    "en-us": "en",
    "en": "en",
    "en-gb": "en-gb",
    "pt": "pt-pt",
    "pt-pt": "pt-pt",
    "pt-br": "pt-br",
    "zh-cn": "zh-hans",
    "zh-hans": "zh-hans",
    "zh-tw": "zh-hant",
    "zh-hant": "zh-hant",
}


@dataclass(frozen=True)
class BraveWebSearchHttpResponse:
    """Decoded Brave response body with selected response headers."""

    body: dict[str, Any]
    headers: dict[str, str]


class BraveWebSearchAdapter(WebSearchPort):
    """Concrete adapter for Brave Web Search."""

    def __init__(self, config: AppConfig) -> None:
        """Store environment-derived connection settings."""
        self._config = config

    def search(self, request: WebSearchRequest) -> WebSearchResponse:
        """Call the Brave Web Search API and normalize the returned results."""
        if self._config.brave_api_key is None:
            raise ValueError(
                "BRAVE_API_KEY or PRICE_SEARCH_BRAVE_API_KEY must be set when "
                "PRICE_SEARCH_SEARCH_PROVIDER=brave"
            )
        http_response = _call_brave_web_search(
            endpoint=self._config.brave_endpoint,
            api_key=self._config.brave_api_key,
            query=request.query,
            include_domains=request.include_domains,
            count=_desired_brave_result_count(limit=request.limit),
            country=self._config.brave_country,
            search_lang=request.language,
            ui_lang=self._config.brave_ui_lang,
            result_filter=self._config.brave_result_filter,
            extra_snippets=self._config.brave_extra_snippets,
        )
        normalized = _normalize_brave_results(
            payload=http_response.body,
            limit=request.limit,
            include_domains=request.include_domains,
            exclude_domains=request.exclude_domains,
            enable_price_research_normalize=self._config.enable_price_research_normalize,
        )
        normalized_results = cast(tuple[DiscoverySearchCandidate, ...], normalized["results"])
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


def _call_brave_web_search(
    *,
    endpoint: str,
    api_key: str,
    query: str,
    include_domains: tuple[str, ...],
    count: int,
    country: str,
    search_lang: str,
    ui_lang: str,
    result_filter: tuple[str, ...],
    extra_snippets: bool,
) -> BraveWebSearchHttpResponse:
    """Call Brave Web Search and return the decoded JSON payload."""
    effective_query = build_query_with_include_domains(
        query=query,
        include_domains=include_domains,
    )
    params = {
        "q": effective_query,
        "count": str(count),
        "country": country,
        "search_lang": normalize_brave_search_lang(search_lang),
        "ui_lang": ui_lang,
        "result_filter": ",".join(result_filter),
        "extra_snippets": "true" if extra_snippets else "false",
    }
    url = f"{endpoint}?{urllib.parse.urlencode(params)}"
    headers = {
        "Accept": "application/json",
        "X-Subscription-Token": api_key,
    }
    http_request = urllib.request.Request(url=url, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(http_request, timeout=BRAVE_TIMEOUT_SECONDS) as response:
            return BraveWebSearchHttpResponse(
                body=json.load(response),
                headers={key: value for key, value in response.headers.items()},
            )
    except urllib.error.HTTPError as error:
        error_body = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(
            f"Brave Web Search request failed with status={error.code}: {error_body}"
        ) from error


def _desired_brave_result_count(*, limit: int) -> int:
    """Compute a capped Brave fetch count before local filtering."""
    return min(BRAVE_MAX_COUNT, max(limit * BRAVE_FETCH_MULTIPLIER, limit))


def _normalize_brave_results(
    *,
    payload: dict[str, Any],
    limit: int,
    include_domains: tuple[str, ...],
    exclude_domains: tuple[str, ...],
    enable_price_research_normalize: bool,
) -> dict[str, object]:
    """Project Brave results onto the current discovery response contract."""
    query_payload = payload.get("query") or {}
    web_payload = payload.get("web") or {}
    candidates: list[DiscoverySearchCandidate] = []

    for item in web_payload.get("results") or ():
        url = str(item.get("url") or "").strip()
        if not url:
            continue
        parsed_url = urllib.parse.urlparse(url)
        description = str(item.get("description") or "").strip()
        extra_snippets = tuple(
            str(extra_snippet).strip()
            for extra_snippet in item.get("extra_snippets") or ()
            if str(extra_snippet).strip()
        )
        snippet = description
        if extra_snippets:
            snippet = " ".join((description, *extra_snippets)).strip()
        candidates.append(
            DiscoverySearchCandidate(
                title=str(item.get("title") or "").strip(),
                url=url,
                host=parsed_url.netloc.lower(),
                snippet=snippet,
                engines=("brave",),
                category=BRAVE_RESULT_CATEGORY,
                score=None,
                path=parsed_url.path.lower(),
            )
        )

    final_query = str(query_payload.get("original") or "")
    return normalize_discovery_results(
        query=final_query,
        candidates=tuple(candidates),
        limit=limit,
        include_domains=include_domains,
        exclude_domains=exclude_domains,
        enable_price_research_normalize=enable_price_research_normalize,
    )


def normalize_brave_search_lang(raw_value: str) -> str:
    """Normalize a user-friendly language value to Brave's accepted enum."""
    normalized = raw_value.strip().lower()
    if not normalized:
        raise ValueError("Brave search_lang must not be blank.")
    return SEARCH_LANG_ALIASES.get(normalized, normalized)
