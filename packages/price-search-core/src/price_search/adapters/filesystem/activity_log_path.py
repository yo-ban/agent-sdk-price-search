"""Infrastructure helper for per-run activity log file path generation."""

from __future__ import annotations

import re
from datetime import UTC, datetime
from pathlib import Path


def build_activity_log_path(
    *,
    configured_log_dir: str,
    product_name: str,
    run_id: str,
    now: datetime | None = None,
) -> Path:
    """Build the JSONL activity log path for one price-search run."""
    timestamp = (now or datetime.now(UTC)).strftime("%Y%m%dT%H%M%SZ")
    slug = _slugify_product_name(product_name=product_name)
    configured_path = Path(configured_log_dir)

    if configured_path.suffix:
        log_dir = configured_path.parent
        file_prefix = configured_path.stem
        suffix = configured_path.suffix
    else:
        log_dir = configured_path
        file_prefix = "price_search_agent_activity"
        suffix = ".jsonl"

    filename = f"{file_prefix}-{timestamp}-{slug}-{run_id[:8]}{suffix}"
    return (log_dir / filename).resolve()


def _slugify_product_name(*, product_name: str) -> str:
    """Create a filesystem-safe slug from the product name."""
    normalized = re.sub(r"[^0-9A-Za-z_-]+", "-", product_name)
    normalized = normalized.strip("-").lower()
    return normalized or "price-search-run"
