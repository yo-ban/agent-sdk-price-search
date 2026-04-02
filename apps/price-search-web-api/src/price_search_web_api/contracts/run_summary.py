"""Run summary contract returned by the history-list endpoint."""

from __future__ import annotations

from dataclasses import dataclass

from price_search_web_api.contracts.run_snapshot import RunStatus


@dataclass(frozen=True)
class RunSummary:
    """Lightweight history-list view of one launcher-backed run."""

    run_id: str
    product_name: str
    market: str
    currency: str
    max_offers: int
    model: str
    status: RunStatus
    started_at: str
    finished_at: str | None
    duration_ms: int
    total_cost_usd: float | None
    num_turns: int | None
