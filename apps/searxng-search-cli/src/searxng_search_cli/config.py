"""SearXNG discovery CLI settings."""

from __future__ import annotations

import os
from dataclasses import dataclass

DEFAULT_SEARXNG_SEARCH_URL = "http://127.0.0.1:18888/search"
DEFAULT_SEARXNG_ENGINES = "brave,google,duckduckgo"
DEFAULT_SEARXNG_LANGUAGE = "ja-JP"
DEFAULT_SEARXNG_RESULT_LIMIT = 8
DEFAULT_ENABLE_PRICE_RESEARCH_NORMALIZE = True


@dataclass(frozen=True)
class AppConfig:
    """Environment-driven runtime settings for the SearXNG CLI."""

    searxng_search_url: str
    searxng_engines: tuple[str, ...]
    searxng_language: str
    searxng_result_limit: int
    enable_price_research_normalize: bool


def load_config() -> AppConfig:
    """Load runtime settings from environment variables."""
    return AppConfig(
        searxng_search_url=os.getenv(
            "PRICE_SEARCH_SEARXNG_SEARCH_URL",
            DEFAULT_SEARXNG_SEARCH_URL,
        ),
        searxng_engines=_split_csv(
            os.getenv("PRICE_SEARCH_SEARXNG_ENGINES", DEFAULT_SEARXNG_ENGINES)
        ),
        searxng_language=os.getenv(
            "PRICE_SEARCH_SEARXNG_LANGUAGE",
            DEFAULT_SEARXNG_LANGUAGE,
        ),
        searxng_result_limit=int(
            os.getenv(
                "PRICE_SEARCH_SEARXNG_RESULT_LIMIT",
                str(DEFAULT_SEARXNG_RESULT_LIMIT),
            )
        ),
        enable_price_research_normalize=_parse_bool(
            os.getenv(
                "PRICE_SEARCH_SEARXNG_ENABLE_PRICE_RESEARCH_NORMALIZE",
                str(DEFAULT_ENABLE_PRICE_RESEARCH_NORMALIZE),
            )
        ),
    )


def _split_csv(value: str) -> tuple[str, ...]:
    """Split a comma-separated configuration value into a tuple."""
    return tuple(item.strip() for item in value.split(",") if item.strip())


def _parse_bool(value: str) -> bool:
    """Parse a flexible boolean environment variable value."""
    return value.strip().lower() not in {"0", "false", "no", "off"}
