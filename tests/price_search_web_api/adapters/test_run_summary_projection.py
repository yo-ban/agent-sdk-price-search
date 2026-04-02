"""Projection tests for history-list run summaries."""

from __future__ import annotations

from datetime import UTC, datetime

from price_search_web_api.adapters.run_summary_projection import build_run_summary


def test_build_run_summary_marks_completed_runs_from_metadata() -> None:
    """Stored timestamps and exit code should produce a finished summary without log reads."""
    summary = build_run_summary(
        metadata={
            "run_id": "run-1",
            "product_name": "Nintendo Switch 2",
            "market": "JP",
            "currency": "JPY",
            "max_offers": 3,
            "model": "claude-sonnet-4-6",
            "started_at": "2026-04-02T09:00:00+00:00",
            "finished_at": "2026-04-02T09:00:12+00:00",
            "total_cost_usd": 0.12,
            "num_turns": 8,
            "exit_code": 0,
        }
    )

    assert summary.status == "finished"
    assert summary.duration_ms == 12000
    assert summary.total_cost_usd == 0.12
    assert summary.num_turns == 8


def test_build_run_summary_marks_zero_exit_as_finished_for_legacy_runs() -> None:
    """A zero exit should keep older completed runs visible as finished summaries."""
    summary = build_run_summary(
        metadata={
            "run_id": "run-2",
            "product_name": "Nintendo Switch 2",
            "market": "JP",
            "currency": "JPY",
            "max_offers": 3,
            "model": "claude-sonnet-4-6",
            "started_at": "2026-04-02T09:00:00+00:00",
            "finished_at": "2026-04-02T09:00:12+00:00",
            "exit_code": 0,
        }
    )

    assert summary.status == "finished"


def test_build_run_summary_uses_current_time_for_researching_runs(monkeypatch) -> None:
    """An in-flight run summary should show elapsed time from started_at to now."""
    monkeypatch.setattr(
        "price_search_web_api.adapters.run_summary_projection._now_epoch_ms",
        lambda: int(datetime(2026, 4, 2, 9, 0, 15, tzinfo=UTC).timestamp() * 1000),
    )

    summary = build_run_summary(
        metadata={
            "run_id": "run-3",
            "product_name": "Nintendo Switch 2",
            "market": "JP",
            "currency": "JPY",
            "max_offers": 3,
            "model": "claude-sonnet-4-6",
            "started_at": "2026-04-02T09:00:00+00:00",
            "finished_at": None,
            "exit_code": None,
        }
    )

    assert summary.status == "researching"
    assert summary.duration_ms == 15000
