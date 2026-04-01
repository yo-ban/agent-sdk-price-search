"""Infrastructure projection from persisted run artifacts to frontend snapshots."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from price_search_web_api.adapters.run_timeline_projection import build_run_timeline
from price_search_web_api.contracts.run_snapshot import RunSnapshot, RunStatus


def build_run_snapshot(
    *,
    metadata: dict[str, Any],
    log_events: tuple[dict[str, Any], ...],
    result_payload: dict[str, Any] | None,
) -> RunSnapshot:
    """Convert run metadata, JSONL events, and result JSON into a snapshot."""
    started_at = str(metadata.get("started_at") or _first_logged_at(log_events) or _iso_now())
    started_at_ms = _to_epoch_ms(started_at)
    result_event = _reverse_find(log_events, "result_message")
    research_started = _find(log_events, "research_started")
    system_init = _find_system_init(log_events)

    finished_at = str(
        (result_event or {}).get("logged_at")
        or metadata.get("finished_at")
        or _last_logged_at(log_events)
        or ""
    )
    finished_at_value = finished_at or None
    finished_at_ms = _to_epoch_ms(finished_at) if finished_at else started_at_ms

    duration_ms = _number_field((result_event or {}).get("payload"), "duration_ms")
    if duration_ms is None:
        duration_ms = max(finished_at_ms - started_at_ms, 0)

    return RunSnapshot(
        run_id=str(metadata.get("run_id") or _first_run_id(log_events) or ""),
        product_name=_coalesce_string(
            _payload_field(research_started, "product_name"),
            metadata.get("product_name"),
        ),
        market=_coalesce_string(
            _payload_field(research_started, "market"),
            metadata.get("market"),
        ),
        currency=_coalesce_string(
            _payload_field(research_started, "currency"),
            metadata.get("currency"),
        ),
        max_offers=_coalesce_int(
            _number_field((research_started or {}).get("payload"), "max_offers"),
            metadata.get("max_offers"),
        ),
        model=_coalesce_string(_system_model(system_init), ""),
        status=_derive_status(
            result_event=result_event,
            exit_code=metadata.get("exit_code"),
            has_result=result_payload is not None,
        ),
        started_at=started_at,
        finished_at=finished_at_value,
        duration_ms=int(duration_ms),
        total_cost_usd=_number_field((result_event or {}).get("payload"), "total_cost_usd"),
        num_turns=_int_field((result_event or {}).get("payload"), "num_turns"),
        result=result_payload,
        timeline=build_run_timeline(log_events=log_events, started_at_ms=started_at_ms),
    )


def read_log_events(log_path: Path) -> tuple[dict[str, Any], ...]:
    """Read JSONL events from disk."""
    events: list[dict[str, Any]] = []
    for raw_line in log_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        parsed = json.loads(line)
        if isinstance(parsed, dict):
            events.append(parsed)
    return tuple(events)


def _derive_status(
    *,
    result_event: dict[str, Any] | None,
    exit_code: Any,
    has_result: bool,
) -> RunStatus:
    """Derive the current run status from log, result, and exit information."""
    if result_event is not None:
        if _bool_field(result_event.get("payload"), "is_error"):
            return "failed"
        return "finished"

    if exit_code is None:
        return "researching"
    if has_result and exit_code == 0:
        return "finished"
    if isinstance(exit_code, int) and exit_code < 0:
        return "interrupted"
    if exit_code == 0:
        return "interrupted"
    return "failed"


def _find(events: tuple[dict[str, Any], ...], event_type: str) -> dict[str, Any] | None:
    """Find the first event of a given type."""
    for event in events:
        if event.get("event_type") == event_type:
            return event
    return None


def _reverse_find(
    events: tuple[dict[str, Any], ...], event_type: str
) -> dict[str, Any] | None:
    """Find the last event of a given type."""
    for event in reversed(events):
        if event.get("event_type") == event_type:
            return event
    return None


def _find_system_init(events: tuple[dict[str, Any], ...]) -> dict[str, Any] | None:
    """Find the initial system init event."""
    for event in events:
        if event.get("event_type") != "system_message":
            continue
        payload = event.get("payload")
        if isinstance(payload, dict) and payload.get("subtype") == "init":
            return event
    return None


def _system_model(event: dict[str, Any] | None) -> str:
    """Extract the configured model name from the init event."""
    if event is None:
        return ""
    payload = event.get("payload")
    if not isinstance(payload, dict):
        return ""
    data = payload.get("data")
    if not isinstance(data, dict):
        return ""
    return _string_field(data, "model")


def _payload_field(event: dict[str, Any] | None, key: str) -> Any:
    """Return one payload field from an event when available."""
    if event is None:
        return None
    payload = event.get("payload")
    if not isinstance(payload, dict):
        return None
    return payload.get(key)


def _string_field(payload: Any, key: str) -> str:
    """Read a string field from a dict-like payload."""
    if isinstance(payload, dict):
        return str(payload.get(key) or "")
    return ""


def _bool_field(payload: Any, key: str) -> bool:
    """Read a boolean field from a dict-like payload."""
    return isinstance(payload, dict) and payload.get(key) is True


def _number_field(payload: Any, key: str) -> float | None:
    """Read a numeric field from a dict-like payload."""
    if not isinstance(payload, dict):
        return None
    value = payload.get(key)
    return float(value) if isinstance(value, int | float) else None


def _int_field(payload: Any, key: str) -> int | None:
    """Read an integer field from a dict-like payload."""
    value = _number_field(payload, key)
    return int(value) if value is not None else None


def _coalesce_string(*values: Any) -> str:
    """Return the first non-empty stringified value."""
    for value in values:
        if value is None:
            continue
        text = str(value)
        if text:
            return text
    return ""


def _coalesce_int(*values: Any) -> int:
    """Return the first integer-like value."""
    for value in values:
        if isinstance(value, bool):
            continue
        if isinstance(value, int):
            return value
        if isinstance(value, float):
            return int(value)
    return 0


def _to_epoch_ms(iso_timestamp: str) -> int:
    """Convert an ISO timestamp to epoch milliseconds."""
    if not iso_timestamp:
        return 0
    normalized = iso_timestamp.replace("Z", "+00:00")
    return int(datetime.fromisoformat(normalized).timestamp() * 1000)


def _iso_now() -> str:
    """Return the current UTC timestamp."""
    return datetime.now(UTC).isoformat()


def _first_logged_at(events: tuple[dict[str, Any], ...]) -> str | None:
    """Return the first logged_at value if present."""
    return str(events[0].get("logged_at")) if events else None


def _last_logged_at(events: tuple[dict[str, Any], ...]) -> str | None:
    """Return the last logged_at value if present."""
    return str(events[-1].get("logged_at")) if events else None


def _first_run_id(events: tuple[dict[str, Any], ...]) -> str | None:
    """Return the first run_id value if present."""
    return str(events[0].get("run_id")) if events else None
