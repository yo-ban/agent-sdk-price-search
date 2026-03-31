"""Run snapshot contract returned to the frontend."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

RunStatus = Literal["researching", "finished", "failed", "interrupted"]
TimelineKind = Literal["system", "thinking", "tool", "text", "result", "error"]


@dataclass(frozen=True)
class TimelineEntry:
    """A timeline entry derived from the current JSONL log."""

    t: int
    kind: TimelineKind
    label: str
    detail: str


@dataclass(frozen=True)
class RunSnapshot:
    """Frontend-facing snapshot of a launcher-backed run."""

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
    result: dict[str, Any] | None
    timeline: tuple[TimelineEntry, ...]
