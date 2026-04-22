"""Output DTOs for the web discovery CLI."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class WebSearchResultResponse:
    """One normalized discovery result."""

    title: str
    url: str
    host: str
    snippet: str
    engines: tuple[str, ...]
    category: str | None
    score: float | None


@dataclass(frozen=True)
class WebSearchResponse:
    """The full discovery response returned to the CLI."""

    query: str
    results: tuple[WebSearchResultResponse, ...]
