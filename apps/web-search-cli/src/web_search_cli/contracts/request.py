"""Input DTOs for the web discovery CLI."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class WebSearchRequest:
    """Discovery search conditions sent to the selected search adapter."""

    query: str
    limit: int
    language: str
    engines: tuple[str, ...]
    include_domains: tuple[str, ...]
    exclude_domains: tuple[str, ...]
