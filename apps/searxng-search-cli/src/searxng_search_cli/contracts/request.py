"""Input DTOs for the SearXNG discovery CLI."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SearxngSearchRequest:
    """Discovery search conditions sent to the SearXNG adapter."""

    query: str
    limit: int
    language: str
    engines: tuple[str, ...]
    include_domains: tuple[str, ...]
    exclude_domains: tuple[str, ...]
