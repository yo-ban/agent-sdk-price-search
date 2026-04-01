"""Tests for the public activity log path helper."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from price_search.adapters.filesystem.activity_log_path import build_activity_log_path


def test_build_activity_log_path_uses_configured_file_as_prefix() -> None:
    """A configured file path should become a per-run file in the same directory."""
    resolved = build_activity_log_path(
        configured_log_dir="logs/price_search_agent_activity.jsonl",
        product_name="全自動コーヒーメーカー ABC-1234",
        run_id="abcdef1234567890",
        now=datetime(2026, 3, 26, 14, 0, tzinfo=UTC),
    )

    assert resolved == Path(
        "logs/price_search_agent_activity-20260326T140000Z-abc-1234-abcdef12.jsonl"
    ).resolve()


def test_build_activity_log_path_supports_directory_config() -> None:
    """A configured directory should receive a default per-run log filename."""
    resolved = build_activity_log_path(
        configured_log_dir="logs",
        product_name="全自動コーヒーメーカー ABC-1234",
        run_id="abcdef1234567890",
        now=datetime(2026, 3, 26, 14, 0, tzinfo=UTC),
    )

    assert resolved == Path(
        "logs/price_search_agent_activity-20260326T140000Z-abc-1234-abcdef12.jsonl"
    ).resolve()
