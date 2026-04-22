"""Shared discovery result normalization for search-provider adapters.

Layer: Infrastructure
"""

from __future__ import annotations

from dataclasses import dataclass

EXCLUDED_SEARCH_CATEGORIES = frozenset({"videos", "video", "music"})
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


@dataclass(frozen=True)
class DiscoverySearchCandidate:
    """Provider-neutral candidate result before CLI response projection."""

    title: str
    url: str
    host: str
    snippet: str
    engines: tuple[str, ...]
    category: str | None
    score: float | None
    path: str


def normalize_discovery_results(
    *,
    query: str,
    candidates: tuple[DiscoverySearchCandidate, ...],
    limit: int,
    include_domains: tuple[str, ...],
    exclude_domains: tuple[str, ...],
    enable_price_research_normalize: bool,
) -> dict[str, object]:
    """Filter provider-neutral results for price research discovery without reordering."""
    include_domains_lower = tuple(domain.lower() for domain in include_domains)
    exclude_domains_lower = tuple(domain.lower() for domain in exclude_domains)
    filtered_candidates: list[DiscoverySearchCandidate] = []

    if not enable_price_research_normalize:
        for candidate in candidates:
            if include_domains_lower and not any(
                _host_matches_domain(host=candidate.host, domain=domain)
                for domain in include_domains_lower
            ):
                continue
            if exclude_domains_lower and any(
                _host_matches_domain(host=candidate.host, domain=domain)
                for domain in exclude_domains_lower
            ):
                continue
            filtered_candidates.append(candidate)
        return {
            "query": query,
            "results": tuple(filtered_candidates[:limit]),
        }

    for candidate in candidates:
        category = (candidate.category or "").strip().lower()
        if include_domains_lower and not any(
            _host_matches_domain(host=candidate.host, domain=domain)
            for domain in include_domains_lower
        ):
            continue
        if exclude_domains_lower and any(
            _host_matches_domain(host=candidate.host, domain=domain)
            for domain in exclude_domains_lower
        ):
            continue
        if _should_exclude_discovery_result(
            host=candidate.host,
            path=candidate.path,
            category=category,
            title=candidate.title,
            snippet=candidate.snippet,
        ):
            continue
        filtered_candidates.append(candidate)
    return {
        "query": query,
        "results": tuple(filtered_candidates[:limit]),
    }


def _host_matches_domain(*, host: str, domain: str) -> bool:
    """Return whether a host is the given domain or one of its subdomains."""
    normalized_host = host.strip().lower()
    normalized_domain = domain.strip().lower().lstrip(".")
    if not normalized_host or not normalized_domain:
        return False
    return normalized_host == normalized_domain or normalized_host.endswith(
        f".{normalized_domain}"
    )


def _should_exclude_discovery_result(
    *,
    host: str,
    path: str,
    category: str,
    title: str,
    snippet: str,
) -> bool:
    """Exclude obvious news / social / media noise without overfiltering product pages."""
    if category in EXCLUDED_SEARCH_CATEGORIES:
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
