"""Port definitions for provider-backed web discovery."""

from __future__ import annotations

from typing import Protocol

from web_search_cli.contracts.request import WebSearchRequest
from web_search_cli.contracts.response import WebSearchResponse


class WebSearchPort(Protocol):
    """Abstract port for a discovery search implementation."""

    def search(self, request: WebSearchRequest) -> WebSearchResponse:
        """Return normalized candidate URLs for the given query."""
        ...
