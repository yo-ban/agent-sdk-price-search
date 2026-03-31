"""Output DTOs for the SearXNG discovery CLI."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SearxngSearchResultResponse:
    """One normalized discovery result."""

    title: str
    url: str
    host: str
    snippet: str
    engines: tuple[str, ...]
    category: str | None
    score: float | None


@dataclass(frozen=True)
class SearxngSearchResponse:
    """The full discovery response returned to the CLI."""

    query: str
    results: tuple[SearxngSearchResultResponse, ...]
