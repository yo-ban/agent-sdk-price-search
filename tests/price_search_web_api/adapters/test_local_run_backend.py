"""Adapter tests for the local launcher-backed run backend."""

from __future__ import annotations

import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path

from price_search_web_api.adapters.local_run_backend import LocalRunBackend
from price_search_web_api.contracts.create_run_request import CreateRunRequest


def test_get_run_returns_finished_snapshot_from_launcher_outputs(tmp_path: Path) -> None:
    """A run directory with log and result files becomes a finished snapshot."""
    backend = LocalRunBackend(run_root=tmp_path, python_executable=sys.executable)
    run_directory = tmp_path / "finished-run"
    _write_inline_run(
        run_directory=run_directory,
        metadata={
            "run_id": "finished-run",
            "product_name": "全自動コーヒーメーカー ABC-1234",
            "market": "JP",
            "currency": "JPY",
            "max_offers": 1,
            "started_at": "2026-03-29T05:16:14+00:00",
            "finished_at": "2026-03-29T05:17:22+00:00",
            "pid": 12345,
            "exit_code": 0,
        },
        log_lines=(
            {
                "logged_at": "2026-03-29T05:16:14+00:00",
                "run_id": "finished-run",
                "event_type": "research_started",
                "payload": {
                    "product_name": "全自動コーヒーメーカー ABC-1234",
                    "market": "JP",
                    "currency": "JPY",
                    "max_offers": 1,
                    "claude_provider": "subscription",
                },
            },
            {
                "logged_at": "2026-03-29T05:16:15+00:00",
                "run_id": "finished-run",
                "event_type": "assistant_message",
                "payload": {
                    "model": "claude-haiku-4-5",
                    "parent_tool_use_id": None,
                    "error": None,
                    "usage": {"input_tokens": 10, "output_tokens": 5},
                    "content": [{"type": "text", "text": "調査を開始します。"}],
                },
            },
        ),
    )
    (run_directory / "out" / "result.json").write_text(
        json.dumps(
            {
                "product_name": "全自動コーヒーメーカー ABC-1234",
                "identified_product": {
                    "name": "全自動コーヒーメーカー ABC-1234",
                    "model_number": "ABC-1234",
                    "manufacturer": "ExampleMaker",
                    "product_url": "https://example.com/products/abc-1234",
                    "release_date": "2025-01-01",
                    "is_substitute": False,
                    "substitution_reason": "",
                },
                "summary": "価格調査の結果です。",
                "offers": [
                    {
                        "merchant_name": "ExampleShop",
                        "listing_title": "全自動コーヒーメーカー ABC-1234",
                        "listing_url": "https://example.com/item/abc-1234",
                        "source_urls": [],
                        "currency": "JPY",
                        "item_price": "29800.0",
                        "availability": "in_stock",
                        "evidence": "商品ページに価格が表示されている。",
                        "observed_at": "2026-03-29",
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    snapshot = backend.get_run("finished-run")

    assert snapshot is not None
    assert snapshot.status == "finished"
    assert snapshot.result is not None
    assert snapshot.timeline


def test_get_run_returns_interrupted_snapshot_when_run_exits_without_result(
    tmp_path: Path,
) -> None:
    """A run directory without result JSON but with interrupted logs is interrupted."""
    backend = LocalRunBackend(run_root=tmp_path, python_executable=sys.executable)
    run_directory = tmp_path / "interrupted-run"
    _write_inline_run(
        run_directory=run_directory,
        metadata={
            "run_id": "interrupted-run",
            "product_name": "全自動コーヒーメーカー ABC-1234",
            "market": "JP",
            "currency": "JPY",
            "max_offers": 3,
            "started_at": "2026-03-28T15:09:04+00:00",
            "finished_at": "2026-03-28T15:11:01+00:00",
            "pid": 54321,
            "exit_code": -15,
        },
        log_lines=(
            {
                "logged_at": "2026-03-28T15:09:04+00:00",
                "run_id": "interrupted-run",
                "event_type": "research_started",
                "payload": {
                    "product_name": "全自動コーヒーメーカー ABC-1234",
                    "market": "JP",
                    "currency": "JPY",
                    "max_offers": 3,
                    "claude_provider": "subscription",
                },
            },
            {
                "logged_at": "2026-03-28T15:09:05+00:00",
                "run_id": "interrupted-run",
                "event_type": "assistant_message",
                "payload": {
                    "model": "claude-haiku-4-5",
                    "parent_tool_use_id": None,
                    "error": None,
                    "usage": {"input_tokens": 10, "output_tokens": 5},
                    "content": [{"type": "text", "text": "調査を開始します。"}],
                },
            },
        ),
    )

    snapshot = backend.get_run("interrupted-run")

    assert snapshot is not None
    assert snapshot.status == "interrupted"
    assert snapshot.result is None
    assert snapshot.timeline


def test_delete_run_hides_terminal_run_from_future_queries(tmp_path: Path) -> None:
    """Soft-deleting a completed run removes it from visible snapshots only."""
    backend = LocalRunBackend(run_root=tmp_path, python_executable=sys.executable)
    run_directory = tmp_path / "delete-run"
    _write_inline_run(
        run_directory=run_directory,
        metadata={
            "run_id": "delete-run",
            "product_name": "delete me",
            "market": "JP",
            "currency": "JPY",
            "max_offers": 1,
            "started_at": "2026-03-29T00:00:00+00:00",
            "finished_at": "2026-03-29T00:00:05+00:00",
            "cancel_requested_at": None,
            "deleted_at": None,
            "pid": 1,
            "exit_code": 0,
        },
        log_lines=(),
    )

    deleted = backend.delete_run("delete-run")

    assert deleted is True
    assert backend.get_run("delete-run") is None
    assert backend.list_runs() == ()
    metadata = json.loads((run_directory / "run.json").read_text(encoding="utf-8"))
    assert metadata["deleted_at"]


def test_list_runs_returns_metadata_only_summaries(tmp_path: Path) -> None:
    """The history list should come from run metadata without requiring logs or results."""
    backend = LocalRunBackend(run_root=tmp_path, python_executable=sys.executable)
    _write_inline_run(
        run_directory=tmp_path / "history-run",
        metadata={
            "run_id": "history-run",
            "product_name": "history item",
            "market": "JP",
            "currency": "JPY",
            "max_offers": 2,
            "model": "claude-sonnet-4-6",
            "started_at": "2026-03-29T00:00:00+00:00",
            "finished_at": "2026-03-29T00:00:08+00:00",
            "cancel_requested_at": None,
            "deleted_at": None,
            "pid": 1,
            "exit_code": 0,
            "total_cost_usd": 0.123,
            "num_turns": 7,
        },
        log_lines=(),
    )

    summaries = backend.list_runs()

    assert len(summaries) == 1
    summary = summaries[0]
    assert summary.run_id == "history-run"
    assert summary.status == "finished"
    assert summary.model == "claude-sonnet-4-6"
    assert summary.total_cost_usd == 0.123
    assert summary.num_turns == 7


def test_delete_run_rejects_researching_run(tmp_path: Path) -> None:
    """A still-running run cannot be soft-deleted."""
    backend = LocalRunBackend(run_root=tmp_path, python_executable=sys.executable)
    _write_inline_run(
        run_directory=tmp_path / "researching-run",
        metadata={
            "run_id": "researching-run",
            "product_name": "keep me",
            "market": "JP",
            "currency": "JPY",
            "max_offers": 1,
            "started_at": "2026-03-29T00:00:00+00:00",
            "finished_at": None,
            "cancel_requested_at": None,
            "deleted_at": None,
            "pid": 1,
            "exit_code": None,
        },
        log_lines=(),
    )

    deleted = backend.delete_run("researching-run")

    assert deleted is False
    assert backend.get_run("researching-run") is not None


def test_cancel_run_sends_sigterm_to_process_group(tmp_path: Path, monkeypatch) -> None:
    """Canceling a running run targets the launcher process group and records the request."""
    backend = LocalRunBackend(run_root=tmp_path, python_executable=sys.executable)
    run_directory = tmp_path / "cancel-run"
    _write_inline_run(
        run_directory=run_directory,
        metadata={
            "run_id": "cancel-run",
            "product_name": "cancel me",
            "market": "JP",
            "currency": "JPY",
            "max_offers": 1,
            "started_at": "2026-03-29T00:00:00+00:00",
            "finished_at": None,
            "cancel_requested_at": None,
            "deleted_at": None,
            "pid": 43210,
            "exit_code": None,
        },
        log_lines=(),
    )
    kill_calls: list[tuple[int, int]] = []
    monkeypatch.setattr(os, "killpg", lambda pgid, sig: kill_calls.append((pgid, sig)))

    snapshot = backend.cancel_run("cancel-run")

    assert snapshot is not None
    assert snapshot.run_id == "cancel-run"
    assert kill_calls == [(43210, 15)]
    metadata = json.loads((run_directory / "run.json").read_text(encoding="utf-8"))
    assert metadata["cancel_requested_at"]


def test_start_run_uses_timestamp_prefixed_run_id(tmp_path: Path, monkeypatch) -> None:
    """Starting a run should create a sortable timestamp-prefixed run directory."""
    backend = LocalRunBackend(run_root=tmp_path, python_executable=sys.executable)
    monkeypatch.setattr(
        "price_search_web_api.adapters.local_run_backend.subprocess.Popen",
        _fake_popen,
    )
    monkeypatch.setattr(
        "price_search_web_api.adapters.local_run_backend.Thread",
        _NoOpThread,
    )
    monkeypatch.setattr(
        backend,
        "_refresh_process_state",
        lambda *, run_id, metadata_path: None,
    )

    snapshot = backend.start_run(
        CreateRunRequest(
            product_name="timestamped run",
            market="JP",
            currency="JPY",
            max_offers=3,
        )
    )

    run_id_parts = snapshot.run_id.split("-", maxsplit=1)
    assert len(run_id_parts) == 2
    assert re.fullmatch(r"\d{8}T\d{6}Z", run_id_parts[0]) is not None
    datetime.strptime(run_id_parts[0], "%Y%m%dT%H%M%SZ")
    assert (tmp_path / snapshot.run_id).is_dir()
    metadata = json.loads((tmp_path / snapshot.run_id / "run.json").read_text(encoding="utf-8"))
    assert metadata["run_id"] == snapshot.run_id
    assert metadata["model"]


def _write_inline_run(
    *,
    run_directory: Path,
    metadata: dict[str, object],
    log_lines: tuple[dict[str, object], ...],
) -> None:
    """Populate a temporary run directory with inline JSONL records."""
    (run_directory / "logs").mkdir(parents=True)
    (run_directory / "out").mkdir(parents=True)
    (run_directory / "run.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (run_directory / "logs" / "activity.jsonl").write_text(
        "\n".join(json.dumps(line, ensure_ascii=False) for line in log_lines) + "\n",
        encoding="utf-8",
    )


class _NoOpThread:
    """Thread stub that suppresses background watcher execution."""

    def __init__(self, *, target, args, daemon) -> None:
        """Accept the same keyword arguments as threading.Thread."""
        self._target = target
        self._args = args
        self._daemon = daemon

    def start(self) -> None:
        """Do nothing during tests."""


class _FakeProcess:
    """Minimal subprocess stub for start_run tests."""

    def __init__(self) -> None:
        """Expose a stable pid and keep the process in running state."""
        self.pid = 43210

    def poll(self) -> None:
        """Return None to indicate that the process is still running."""
        return None


def _fake_popen(*args, **kwargs) -> _FakeProcess:
    """Return a stable fake process for start_run tests."""
    return _FakeProcess()
