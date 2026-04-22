"""Helpers to express domain filters in provider query strings.

Layer: Infrastructure
"""

from __future__ import annotations


def build_query_with_include_domains(
    *,
    query: str,
    include_domains: tuple[str, ...],
) -> str:
    """Append provider-side `site:` filters when include domains are specified."""
    normalized_domains = tuple(
        domain.strip().lower().lstrip(".")
        for domain in include_domains
        if domain.strip()
    )
    if not normalized_domains:
        return query
    if len(normalized_domains) == 1:
        return f"{query} site:{normalized_domains[0]}"
    site_clause = " OR ".join(f"site:{domain}" for domain in normalized_domains)
    return f"{query} ({site_clause})"
