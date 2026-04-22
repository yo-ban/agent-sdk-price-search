"""Factory for discovery search adapters.

Layer: Infrastructure
"""

from __future__ import annotations

from web_search_cli.adapters.brave_web_search import BraveWebSearchAdapter
from web_search_cli.adapters.self_hosted_search import SelfHostedSearchAdapter
from web_search_cli.config import AppConfig
from web_search_cli.ports.search_port import WebSearchPort


def build_search_adapter(*, config: AppConfig) -> WebSearchPort:
    """Build the concrete search adapter selected by runtime configuration."""
    if config.search_provider == "brave":
        return BraveWebSearchAdapter(config=config)
    return SelfHostedSearchAdapter(config=config)
