"""Infrastructure projection from persisted run metadata to history summaries."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from price_search_web_api.contracts.run_snapshot import RunStatus
from price_search_web_api.contracts.run_summary import RunSummary


def build_run_summary(*, metadata: dict[str, Any]) -> RunSummary:
    """Convert persisted run metadata into a lightweight history summary."""
    started_at = str(metadata.get("started_at") or _iso_now())
    started_at_ms = _to_epoch_ms(started_at)
    finished_at = _string_or_none(metadata.get("finished_at"))
    finished_at_ms = _to_epoch_ms(finished_at) if finished_at is not None else _now_epoch_ms()

    duration_ms = max(finished_at_ms - started_at_ms, 0)

    return RunSummary(
        run_id=str(metadata.get("run_id") or ""),
        product_name=str(metadata.get("product_name") or ""),
        market=str(metadata.get("market") or ""),
        currency=str(metadata.get("currency") or ""),
        max_offers=_coalesce_int(metadata.get("max_offers")),
        model=str(metadata.get("model") or ""),
        status=_derive_status_from_metadata(metadata=metadata),
        started_at=started_at,
        finished_at=finished_at,
        duration_ms=int(duration_ms),
        total_cost_usd=_number_field(metadata, "total_cost_usd"),
        num_turns=_int_field(metadata, "num_turns"),
    )


def _derive_status_from_metadata(*, metadata: dict[str, Any]) -> RunStatus:
    """Derive the current run status from metadata only."""
    exit_code = metadata.get("exit_code")
    if exit_code is None:
        return "researching"
    if isinstance(exit_code, int) and exit_code < 0:
        return "interrupted"
    if exit_code == 0:
        return "finished"
    return "failed"


def _number_field(payload: dict[str, Any], key: str) -> float | None:
    """Read a numeric field from metadata."""
    value = payload.get(key)
    return float(value) if isinstance(value, int | float) else None


def _int_field(payload: dict[str, Any], key: str) -> int | None:
    """Read an integer field from metadata."""
    value = _number_field(payload, key)
    return int(value) if value is not None else None


def _coalesce_int(value: Any) -> int:
    """Return an integer-like metadata value."""
    if isinstance(value, bool):
        return 0
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    return 0


def _string_or_none(value: Any) -> str | None:
    """Convert a metadata value to a non-empty string when present."""
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _to_epoch_ms(iso_timestamp: str | None) -> int:
    """Convert an ISO timestamp to epoch milliseconds."""
    if not iso_timestamp:
        return 0
    normalized = iso_timestamp.replace("Z", "+00:00")
    return int(datetime.fromisoformat(normalized).timestamp() * 1000)


def _iso_now() -> str:
    """Return the current UTC timestamp."""
    return datetime.now(UTC).isoformat()


def _now_epoch_ms() -> int:
    """Return the current UTC time as epoch milliseconds."""
    return int(datetime.now(UTC).timestamp() * 1000)
