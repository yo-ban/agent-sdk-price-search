"""Discovery CLI settings for web search providers."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Literal, cast

SearchProvider = Literal["searxng", "brave"]

DEFAULT_SEARCH_PROVIDER: SearchProvider = "brave"
DEFAULT_SEARXNG_SEARCH_URL = "http://127.0.0.1:18888/search"
DEFAULT_SEARXNG_ENGINES = "brave,google,duckduckgo"
DEFAULT_SEARXNG_LANGUAGE = "ja-JP"
DEFAULT_SEARXNG_RESULT_LIMIT = 8
DEFAULT_ENABLE_PRICE_RESEARCH_NORMALIZE = True
DEFAULT_BRAVE_ENDPOINT = "https://api.search.brave.com/res/v1/web/search"
DEFAULT_BRAVE_COUNTRY = "JP"
DEFAULT_BRAVE_SEARCH_LANG = "jp"
DEFAULT_BRAVE_UI_LANG = "ja-JP"
DEFAULT_BRAVE_RESULT_FILTER = "web"
DEFAULT_BRAVE_EXTRA_SNIPPETS = True


@dataclass(frozen=True)
class AppConfig:
    """Environment-driven runtime settings for the discovery CLI."""

    searxng_search_url: str
    searxng_engines: tuple[str, ...]
    searxng_language: str
    searxng_result_limit: int
    enable_price_research_normalize: bool
    search_provider: SearchProvider = DEFAULT_SEARCH_PROVIDER
    brave_endpoint: str = DEFAULT_BRAVE_ENDPOINT
    brave_api_key: str | None = None
    brave_country: str = DEFAULT_BRAVE_COUNTRY
    brave_search_lang: str = DEFAULT_BRAVE_SEARCH_LANG
    brave_ui_lang: str = DEFAULT_BRAVE_UI_LANG
    brave_result_filter: tuple[str, ...] = (DEFAULT_BRAVE_RESULT_FILTER,)
    brave_extra_snippets: bool = DEFAULT_BRAVE_EXTRA_SNIPPETS


def load_config() -> AppConfig:
    """Load runtime settings from environment variables."""
    return AppConfig(
        search_provider=_parse_search_provider(
            os.getenv("PRICE_SEARCH_SEARCH_PROVIDER", DEFAULT_SEARCH_PROVIDER)
        ),
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
        brave_endpoint=_optional_env("PRICE_SEARCH_BRAVE_ENDPOINT")
        or _optional_env("BRAVE_ENDPOINT")
        or DEFAULT_BRAVE_ENDPOINT,
        brave_api_key=_optional_env("PRICE_SEARCH_BRAVE_API_KEY")
        or _optional_env("BRAVE_API_KEY"),
        brave_country=os.getenv("PRICE_SEARCH_BRAVE_COUNTRY", DEFAULT_BRAVE_COUNTRY),
        brave_search_lang=os.getenv(
            "PRICE_SEARCH_BRAVE_SEARCH_LANG",
            DEFAULT_BRAVE_SEARCH_LANG,
        ),
        brave_ui_lang=os.getenv(
            "PRICE_SEARCH_BRAVE_UI_LANG",
            DEFAULT_BRAVE_UI_LANG,
        ),
        brave_result_filter=_split_csv(
            os.getenv("PRICE_SEARCH_BRAVE_RESULT_FILTER", DEFAULT_BRAVE_RESULT_FILTER)
        ),
        brave_extra_snippets=_parse_bool(
            os.getenv(
                "PRICE_SEARCH_BRAVE_EXTRA_SNIPPETS",
                str(DEFAULT_BRAVE_EXTRA_SNIPPETS),
            )
        ),
    )


def _parse_search_provider(value: str) -> SearchProvider:
    """Parse the configured discovery search provider."""
    normalized = value.strip().lower()
    if normalized not in {"searxng", "brave"}:
        raise ValueError(
            "PRICE_SEARCH_SEARCH_PROVIDER must be one of: searxng, brave"
        )
    return cast(SearchProvider, normalized)


def _split_csv(value: str) -> tuple[str, ...]:
    """Split a comma-separated configuration value into a tuple."""
    return tuple(item.strip() for item in value.split(",") if item.strip())


def _parse_bool(value: str) -> bool:
    """Parse a flexible boolean environment variable value."""
    return value.strip().lower() not in {"0", "false", "no", "off"}


def _optional_env(name: str) -> str | None:
    """Return a stripped environment variable, treating blank as None."""
    value = os.getenv(name)
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None
