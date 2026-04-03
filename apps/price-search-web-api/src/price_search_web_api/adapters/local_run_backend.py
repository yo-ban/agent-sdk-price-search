"""Infrastructure adapter for local launcher-backed run lifecycle management."""

from __future__ import annotations

import json
import os
import signal
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from threading import Lock, Thread
from typing import Any
from uuid import uuid4

from price_search.config import load_config as load_price_search_config

from price_search_web_api.adapters.run_snapshot_projection import (
    build_run_snapshot,
    read_log_events,
)
from price_search_web_api.adapters.run_summary_projection import build_run_summary
from price_search_web_api.contracts.create_run_request import CreateRunRequest
from price_search_web_api.contracts.run_snapshot import RunSnapshot
from price_search_web_api.contracts.run_summary import RunSummary
from price_search_web_api.ports.run_backend_port import RunBackendPort


class LocalRunBackend(RunBackendPort):
    """Start launcher runs locally and read their current snapshots."""

    def __init__(self, *, run_root: Path, python_executable: str) -> None:
        """Store filesystem root and Python executable for child processes."""
        self._run_root = run_root
        self._python_executable = python_executable
        self._default_model = load_price_search_config().primary_model
        self._lock = Lock()
        self._active_processes: dict[str, subprocess.Popen[str]] = {}

    def start_run(self, request: CreateRunRequest) -> RunSnapshot:
        """Create a run directory, start the launcher, and return its snapshot."""
        run_id = _generate_run_id()
        run_directory = self._run_root / run_id
        run_directory.mkdir(parents=True, exist_ok=False)

        metadata = {
            "run_id": run_id,
            "product_name": request.product_name,
            "market": request.market,
            "currency": request.currency,
            "max_offers": request.max_offers,
            "model": self._default_model,
            "started_at": _iso_now(),
            "finished_at": None,
            "cancel_requested_at": None,
            "deleted_at": None,
            "pid": None,
            "exit_code": None,
            "total_cost_usd": None,
            "num_turns": None,
        }
        _write_json(run_directory / "run.json", metadata)

        stdout_handle = (run_directory / "launcher.stdout.log").open("w", encoding="utf-8")
        stderr_handle = (run_directory / "launcher.stderr.log").open("w", encoding="utf-8")
        process = subprocess.Popen(
            self._build_launch_command(request=request),
            cwd=run_directory,
            env=os.environ.copy(),
            stdout=stdout_handle,
            stderr=stderr_handle,
            text=True,
            start_new_session=True,
        )

        metadata["pid"] = process.pid
        _write_json(run_directory / "run.json", metadata)

        with self._lock:
            self._active_processes[run_id] = process

        watcher = Thread(
            target=self._watch_process,
            args=(run_id, process, stdout_handle, stderr_handle),
            daemon=True,
        )
        watcher.start()
        snapshot = self.get_run(run_id)
        if snapshot is None:
            raise RuntimeError("Started run is missing immediately after launch")
        return snapshot

    def get_run(self, run_id: str) -> RunSnapshot | None:
        """Return the current snapshot for a single run directory."""
        run_directory = self._run_root / run_id
        metadata_path = run_directory / "run.json"
        if not metadata_path.exists():
            return None

        metadata = _read_json(metadata_path)
        if _is_deleted(metadata):
            return None

        self._refresh_process_state(run_id=run_id, metadata_path=metadata_path)
        metadata = _read_json(metadata_path)
        log_path = _latest_file(run_directory / "logs", "*.jsonl")
        result_path = _latest_file(run_directory / "out", "*.json")
        result_payload = _read_json(result_path) if result_path is not None else None
        log_events = read_log_events(log_path) if log_path is not None else ()
        return build_run_snapshot(
            metadata=metadata,
            log_events=log_events,
            result_payload=result_payload,
        )

    def list_runs(self) -> tuple[RunSummary, ...]:
        """Return all known runs as lightweight summaries."""
        if not self._run_root.exists():
            return ()

        summaries: list[RunSummary] = []
        for run_directory in self._run_root.iterdir():
            if not run_directory.is_dir():
                continue
            metadata_path = run_directory / "run.json"
            if not metadata_path.exists():
                continue
            metadata = _read_json(metadata_path)
            if _is_deleted(metadata):
                continue
            self._refresh_process_state(run_id=run_directory.name, metadata_path=metadata_path)
            metadata = _read_json(metadata_path)
            summaries.append(build_run_summary(metadata=metadata))

        summaries.sort(key=lambda summary: summary.started_at, reverse=True)
        return tuple(summaries)

    def cancel_run(self, run_id: str) -> RunSnapshot | None:
        """Request cancellation for one running run."""
        run_directory = self._run_root / run_id
        metadata_path = run_directory / "run.json"
        if not metadata_path.exists():
            return None

        metadata = _read_json(metadata_path)
        if _is_deleted(metadata):
            return None
        if metadata.get("exit_code") is not None:
            return self.get_run(run_id)

        process_group_id = _int_from_metadata(metadata.get("pid"))
        if process_group_id is None:
            return self.get_run(run_id)

        try:
            os.killpg(process_group_id, signal.SIGTERM)
        except ProcessLookupError:
            pass

        metadata["cancel_requested_at"] = metadata.get("cancel_requested_at") or _iso_now()
        _write_json(metadata_path, metadata)
        return self.get_run(run_id)

    def delete_run(self, run_id: str) -> bool:
        """Soft-delete one completed run from visible history."""
        run_directory = self._run_root / run_id
        metadata_path = run_directory / "run.json"
        if not metadata_path.exists():
            return False

        metadata = _read_json(metadata_path)
        if _is_deleted(metadata):
            return False

        snapshot = self.get_run(run_id)
        if snapshot is None or snapshot.status == "researching":
            return False

        metadata = _read_json(metadata_path)
        metadata["deleted_at"] = metadata.get("deleted_at") or _iso_now()
        _write_json(metadata_path, metadata)
        return True

    def _build_launch_command(self, *, request: CreateRunRequest) -> list[str]:
        """Build the launcher subprocess command for one run request."""
        return [
            self._python_executable,
            "-m",
            "price_search_launcher.handler.launcher",
            request.product_name,
            "--",
            "--max-offers",
            str(request.max_offers),
            "--market",
            request.market,
            "--currency",
            request.currency,
        ]

    def _watch_process(
        self,
        run_id: str,
        process: subprocess.Popen[str],
        stdout_handle: Any,
        stderr_handle: Any,
    ) -> None:
        """Persist completion metadata when the launcher subprocess exits."""
        try:
            exit_code = process.wait()
            run_directory = self._run_root / run_id
            metadata_path = run_directory / "run.json"
            if metadata_path.exists():
                self._persist_completion_metadata(
                    run_directory=run_directory,
                    metadata_path=metadata_path,
                    exit_code=exit_code,
                )
        finally:
            with self._lock:
                self._active_processes.pop(run_id, None)
            stdout_handle.close()
            stderr_handle.close()

    def _refresh_process_state(self, *, run_id: str, metadata_path: Path) -> None:
        """Persist exit_code once a tracked process has already finished."""
        with self._lock:
            process = self._active_processes.get(run_id)

        if process is None:
            return

        exit_code = process.poll()
        if exit_code is None:
            return

        self._persist_completion_metadata(
            run_directory=metadata_path.parent,
            metadata_path=metadata_path,
            exit_code=exit_code,
        )

    def _persist_completion_metadata(
        self,
        *,
        run_directory: Path,
        metadata_path: Path,
        exit_code: int,
    ) -> None:
        """Persist terminal metadata that history summaries can read without logs."""
        metadata = _read_json(metadata_path)
        metadata["exit_code"] = exit_code

        log_path = _latest_file(run_directory / "logs", "*.jsonl")
        if log_path is not None:
            result_event = _read_latest_result_event(log_path)
            if result_event is not None:
                metadata["finished_at"] = _coalesce_string(
                    result_event.get("logged_at"),
                    metadata.get("finished_at"),
                )
                payload = result_event.get("payload")
                if isinstance(payload, dict):
                    metadata["total_cost_usd"] = _coalesce_number(
                        payload.get("total_cost_usd"),
                        metadata.get("total_cost_usd"),
                    )
                    metadata["num_turns"] = _coalesce_optional_int(
                        payload.get("num_turns"),
                        metadata.get("num_turns"),
                    )
        metadata["finished_at"] = _coalesce_string(metadata.get("finished_at"), _iso_now())
        _write_json(metadata_path, metadata)


def _generate_run_id() -> str:
    """Create a run identifier that stays sortable in directory listings."""
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return f"{timestamp}-{uuid4().hex}"


def _latest_file(directory: Path, pattern: str) -> Path | None:
    """Return the latest file matching a glob pattern."""
    if not directory.exists():
        return None
    candidates = sorted(directory.glob(pattern))
    return candidates[-1] if candidates else None


def _read_latest_result_event(log_path: Path) -> dict[str, Any] | None:
    """Return the last result_message event from one JSONL log file."""
    latest_event: dict[str, Any] | None = None
    for raw_line in log_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        parsed = json.loads(line)
        if isinstance(parsed, dict) and parsed.get("event_type") == "result_message":
            latest_event = parsed
    return latest_event


def _read_json(path: Path) -> dict[str, Any]:
    """Read a JSON object from disk."""
    parsed = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(parsed, dict):
        raise ValueError(f"Expected JSON object in {path}")
    return parsed


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    """Write a JSON object to disk."""
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _is_deleted(metadata: dict[str, Any]) -> bool:
    """Return whether the run metadata marks the run as deleted."""
    return bool(metadata.get("deleted_at"))


def _int_from_metadata(value: Any) -> int | None:
    """Convert JSON metadata values to int when possible."""
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str) and value.strip().isdigit():
        return int(value)
    return None


def _coalesce_number(*values: Any) -> float | None:
    """Return the first numeric value from metadata-like inputs."""
    for value in values:
        if isinstance(value, bool):
            continue
        if isinstance(value, int | float):
            return float(value)
    return None


def _coalesce_optional_int(*values: Any) -> int | None:
    """Return the first integer-like value from metadata-like inputs."""
    for value in values:
        if isinstance(value, bool):
            continue
        if isinstance(value, int):
            return value
        if isinstance(value, float):
            return int(value)
    return None


def _coalesce_string(*values: Any) -> str:
    """Return the first non-empty string from metadata-like inputs."""
    for value in values:
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return ""


def _iso_now() -> str:
    """Return the current UTC timestamp."""
    return datetime.now(UTC).isoformat()
