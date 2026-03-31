"""Port definitions for SearXNG-backed discovery."""

from __future__ import annotations

from typing import Protocol

from searxng_search_cli.contracts.request import SearxngSearchRequest
from searxng_search_cli.contracts.response import SearxngSearchResponse


class SearxngSearchPort(Protocol):
    """Abstract port for a discovery search implementation."""

    def search(self, request: SearxngSearchRequest) -> SearxngSearchResponse:
        """Return normalized candidate URLs for the given query."""
        ...
