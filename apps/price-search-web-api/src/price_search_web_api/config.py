"""Web API runtime configuration."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class WebApiConfig:
    """Web API process configuration."""

    host: str
    port: int
    run_root: Path


def load_config() -> WebApiConfig:
    """Load Web API configuration from environment variables."""
    return WebApiConfig(
        host=os.environ.get("PRICE_SEARCH_WEB_API_HOST", "127.0.0.1"),
        port=int(os.environ.get("PRICE_SEARCH_WEB_API_PORT", "8000")),
        run_root=Path(
            os.environ.get("PRICE_SEARCH_WEB_API_RUN_ROOT", ".price-search-web-api/runs")
        ).resolve(),
    )

