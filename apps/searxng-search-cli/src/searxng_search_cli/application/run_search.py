"""Application service for self-hosted SearXNG discovery."""

from __future__ import annotations

from searxng_search_cli.contracts.request import SearxngSearchRequest
from searxng_search_cli.contracts.response import SearxngSearchResponse
from searxng_search_cli.ports.search_port import SearxngSearchPort


class RunSearxngSearchUseCase:
    """Thin orchestration layer around the search port."""

    def __init__(self, search_port: SearxngSearchPort) -> None:
        """Store the injected search adapter."""
        self._search_port = search_port

    def execute(self, request: SearxngSearchRequest) -> SearxngSearchResponse:
        """Execute one discovery search and return its normalized result."""
        return self._search_port.search(request=request)
