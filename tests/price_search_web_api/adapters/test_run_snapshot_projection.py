"""Projection tests for launcher-backed run snapshots."""

from __future__ import annotations

from price_search_web_api.adapters.run_snapshot_projection import build_run_snapshot


def test_build_run_snapshot_uses_metadata_terminal_fields_for_consistent_display() -> None:
    """Snapshots should use persisted terminal timing so detail matches history."""
    snapshot = build_run_snapshot(
        metadata={
            "run_id": "run-1",
            "product_name": "metadata product",
            "market": "US",
            "currency": "USD",
            "max_offers": 1,
            "started_at": "2026-03-29T00:00:00+00:00",
            "finished_at": "2026-03-29T00:03:00+00:00",
            "exit_code": 1,
        },
        log_events=(
            {
                "logged_at": "2026-03-29T00:00:01+00:00",
                "run_id": "run-1",
                "event_type": "research_started",
                "payload": {
                    "product_name": "logged product",
                    "market": "JP",
                    "currency": "JPY",
                    "max_offers": 3,
                },
            },
            {
                "logged_at": "2026-03-29T00:00:02+00:00",
                "run_id": "run-1",
                "event_type": "system_message",
                "payload": {
                    "subtype": "init",
                    "data": {"model": "claude-sonnet-4-6"},
                },
            },
            {
                "logged_at": "2026-03-29T00:02:00+00:00",
                "run_id": "run-1",
                "event_type": "result_message",
                "payload": {
                    "is_error": True,
                    "result": "failed",
                    "total_cost_usd": 1.25,
                    "num_turns": 7,
                },
            },
        ),
        result_payload=None,
    )

    assert snapshot.product_name == "logged product"
    assert snapshot.market == "JP"
    assert snapshot.currency == "JPY"
    assert snapshot.max_offers == 3
    assert snapshot.model == "claude-sonnet-4-6"
    assert snapshot.status == "failed"
    assert snapshot.finished_at == "2026-03-29T00:03:00+00:00"
    assert snapshot.duration_ms == 180000
    assert snapshot.total_cost_usd == 1.25
    assert snapshot.num_turns == 7


def test_build_run_snapshot_derives_status_and_duration_from_metadata_without_result_event() -> None:
    """Metadata should drive fallback status and duration when no result event exists."""
    snapshot = build_run_snapshot(
        metadata={
            "run_id": "run-2",
            "product_name": "metadata product",
            "market": "JP",
            "currency": "JPY",
            "max_offers": 2,
            "started_at": "2026-03-29T00:00:00+00:00",
            "finished_at": "2026-03-29T00:00:05+00:00",
            "exit_code": 23,
        },
        log_events=(),
        result_payload=None,
    )

    assert snapshot.status == "failed"
    assert snapshot.finished_at == "2026-03-29T00:00:05+00:00"
    assert snapshot.duration_ms == 5000
    assert snapshot.product_name == "metadata product"
    assert snapshot.model == ""
