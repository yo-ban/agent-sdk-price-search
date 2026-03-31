"""Local launcher-backed run management adapter."""

from __future__ import annotations

import json
import os
import signal
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from threading import Lock, Thread
from typing import Any, TypedDict
from uuid import uuid4

from price_search_web_api.contracts.create_run_request import CreateRunRequest
from price_search_web_api.contracts.run_snapshot import (
    RunSnapshot,
    RunStatus,
    TimelineEntry,
    TimelineKind,
)


class _UserMessageClassification(TypedDict):
    """Typed classification result for user-side timeline events."""

    kind: TimelineKind
    label: str


class LocalRunBackend:
    """Start launcher runs locally and read their current snapshots."""

    def __init__(self, *, run_root: Path, python_executable: str) -> None:
        """Store filesystem root and Python executable for child processes."""
        self._run_root = run_root
        self._python_executable = python_executable
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
            "started_at": _iso_now(),
            "finished_at": None,
            "cancel_requested_at": None,
            "deleted_at": None,
            "pid": None,
            "exit_code": None,
        }
        _write_json(run_directory / "run.json", metadata)

        stdout_handle = (run_directory / "launcher.stdout.log").open("w", encoding="utf-8")
        stderr_handle = (run_directory / "launcher.stderr.log").open("w", encoding="utf-8")
        command = [
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
        process = subprocess.Popen(
            command,
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
        log_events = _read_log_events(log_path) if log_path is not None else ()
        return _build_snapshot(
            metadata=metadata,
            log_events=log_events,
            result_payload=result_payload,
        )

    def list_runs(self) -> tuple[RunSnapshot, ...]:
        """Return all known runs sorted by started_at descending."""
        if not self._run_root.exists():
            return ()

        snapshots: list[RunSnapshot] = []
        for run_directory in self._run_root.iterdir():
            if not run_directory.is_dir():
                continue
            snapshot = self.get_run(run_directory.name)
            if snapshot is not None:
                snapshots.append(snapshot)

        snapshots.sort(key=lambda snapshot: snapshot.started_at, reverse=True)
        return tuple(snapshots)

    def cancel_run(self, run_id: str) -> RunSnapshot | None:
        """Request cancellation for one running run."""
        run_directory = self._run_root / run_id
        metadata_path = run_directory / "run.json"
        if not metadata_path.exists():
            return None

        metadata = _read_json(metadata_path)
        if _is_deleted(metadata):
            return None
        if _derive_status(
            result_event=None,
            exit_code=metadata.get("exit_code"),
            has_result=_latest_file(run_directory / "out", "*.json") is not None,
        ) != "researching":
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
                metadata = _read_json(metadata_path)
                metadata["finished_at"] = _iso_now()
                metadata["exit_code"] = exit_code
                _write_json(metadata_path, metadata)
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

        metadata = _read_json(metadata_path)
        metadata["finished_at"] = metadata.get("finished_at") or _iso_now()
        metadata["exit_code"] = exit_code
        _write_json(metadata_path, metadata)


def _build_snapshot(
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

    tool_use_name_by_id = _build_tool_use_name_index(log_events)
    timeline = tuple(
        entry
        for event in log_events
        for entry in _event_to_timeline_entries(
            event=event,
            started_at_ms=started_at_ms,
            tool_use_name_by_id=tool_use_name_by_id,
        )
    )

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
        timeline=timeline,
    )


def _generate_run_id() -> str:
    """Create a run identifier that stays sortable in directory listings."""
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return f"{timestamp}-{uuid4().hex}"


def _derive_status(
    *,
    result_event: dict[str, Any] | None,
    exit_code: Any,
    has_result: bool,
) -> RunStatus:
    """Derive the current run status from log/result/exit information."""
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


def _event_to_timeline_entries(
    *,
    event: dict[str, Any],
    started_at_ms: int,
    tool_use_name_by_id: dict[str, str],
) -> tuple[TimelineEntry, ...]:
    """Translate a single JSONL event into one or more timeline entries."""
    t = max(_to_epoch_ms(str(event.get("logged_at") or "")) - started_at_ms, 0)
    event_type = str(event.get("event_type") or "")
    payload = event.get("payload")
    if not isinstance(payload, dict):
        payload = {}

    if event_type == "research_started":
        return (
            TimelineEntry(
                t=t,
                kind="system",
                label="調査を開始しました",
                detail=" / ".join(
                    (
                        f"商品: {_string_field(payload, 'product_name')}",
                        f"市場: {_string_field(payload, 'market')}",
                        f"通貨: {_string_field(payload, 'currency')}",
                        f"最大比較件数: {_int_field(payload, 'max_offers') or 0}件",
                    )
                ),
            ),
        )

    if event_type == "system_message":
        return (
            TimelineEntry(
                t=t,
                kind="system",
                label=f"System: {_string_field(payload, 'subtype') or 'message'}",
                detail=json.dumps(payload.get("data", payload), ensure_ascii=False, indent=2),
            ),
        )

    if event_type == "assistant_message":
        content = payload.get("content")
        if not isinstance(content, list):
            return ()
        return tuple(_assistant_block_to_entry(block=block, t=t) for block in content if isinstance(block, dict))

    if event_type == "user_message":
        classification = _classify_user_message(
            content=payload.get("content"),
            tool_use_name_by_id=tool_use_name_by_id,
        )
        detail = _extract_user_message_text(payload.get("content"))
        if not detail:
            detail = json.dumps(payload, ensure_ascii=False, indent=2)
        kind = classification["kind"]
        label = classification["label"]
        is_error = _user_message_is_error(payload.get("content"), detail=detail)
        if is_error:
            kind = "error"
            label = f"{label} (Error)"
        return (
            TimelineEntry(
                t=t,
                kind=kind,
                label=label,
                detail=detail,
            ),
        )

    if event_type == "result_message":
        is_error = _bool_field(payload, "is_error")
        return (
            TimelineEntry(
                t=t,
                kind="error" if is_error else "result",
                label="調査失敗" if is_error else "調査完了",
                detail=_string_field(payload, "result") or _string_field(payload, "stop_reason"),
            ),
        )

    return ()


def _assistant_block_to_entry(*, block: dict[str, Any], t: int) -> TimelineEntry:
    """Convert one assistant content block to a timeline entry."""
    block_type = str(block.get("type") or "")
    if block_type == "thinking":
        return TimelineEntry(
            t=t,
            kind="thinking",
            label="Thinking",
            detail=_string_field(block, "thinking"),
        )
    if block_type == "text":
        text = _string_field(block, "text")
        return TimelineEntry(
            t=t,
            kind="text",
            label=_assistant_text_label(text),
            detail=text,
        )
    if block_type == "tool_use":
        return TimelineEntry(
            t=t,
            kind="tool",
            label=f"Tool: {_string_field(block, 'name')}",
            detail=json.dumps(block.get("input", {}), ensure_ascii=False, indent=2),
        )
    return TimelineEntry(
        t=t,
        kind="system",
        label=block_type or "assistant_block",
        detail=json.dumps(block, ensure_ascii=False, indent=2),
    )


def _extract_user_message_text(content: Any) -> str:
    """Extract human-readable text from user/tool result blocks."""
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return ""

    parts: list[str] = []
    for block in content:
        if not isinstance(block, dict):
            continue
        if block.get("type") == "text":
            parts.append(_string_field(block, "text"))
            continue
        if block.get("type") != "tool_result":
            continue

        block_content = block.get("content")
        if isinstance(block_content, str):
            parts.append(block_content)
            continue
        if isinstance(block_content, list):
            for inner in block_content:
                if not isinstance(inner, dict):
                    continue
                if inner.get("type") == "text":
                    parts.append(_string_field(inner, "text"))
                else:
                    parts.append(json.dumps(inner, ensure_ascii=False))
            continue
        if block_content is not None:
            parts.append(json.dumps(block_content, ensure_ascii=False, indent=2))

    return "\n".join(part for part in parts if part).strip()


def _build_tool_use_name_index(events: tuple[dict[str, Any], ...]) -> dict[str, str]:
    """Index tool_use block ids to tool names for later tool_result labeling."""
    mapping: dict[str, str] = {}
    for event in events:
        if event.get("event_type") != "assistant_message":
            continue
        payload = event.get("payload")
        if not isinstance(payload, dict):
            continue
        content = payload.get("content")
        if not isinstance(content, list):
            continue
        for block in content:
            if not isinstance(block, dict) or block.get("type") != "tool_use":
                continue
            tool_use_id = str(block.get("id") or "").strip()
            tool_name = str(block.get("name") or "").strip()
            if tool_use_id and tool_name:
                mapping[tool_use_id] = tool_name
    return mapping


def _classify_user_message(
    *, content: Any, tool_use_name_by_id: dict[str, str]
) -> _UserMessageClassification:
    """Classify a user-side event into timeline kind and label."""
    tool_result = _first_tool_result_block(content)
    if tool_result is not None:
        tool_use_id = _string_field(tool_result, "tool_use_id")
        tool_name = tool_use_name_by_id.get(tool_use_id, "")
        if tool_name:
            return {"kind": "result", "label": f"Tool Result: {tool_name}"}
        return {"kind": "result", "label": "Tool Result"}

    text_block = _first_text_block(content)
    if text_block is not None:
        skill_name = _skill_name_from_instruction_text(_string_field(text_block, "text"))
        if skill_name:
            return {"kind": "system", "label": f"Skill Instructions: {skill_name}"}

    return {
        "kind": "result",
        "label": _summarize_timeline_label(
            text=_extract_user_message_text(content),
            fallback="User message",
        ),
    }


def _first_tool_result_block(content: Any) -> dict[str, Any] | None:
    """Return the first tool_result block in a message content list."""
    if not isinstance(content, list):
        return None
    for block in content:
        if isinstance(block, dict) and block.get("type") == "tool_result":
            return block
    return None


def _first_text_block(content: Any) -> dict[str, Any] | None:
    """Return the first text block in a message content list."""
    if not isinstance(content, list):
        return None
    for block in content:
        if isinstance(block, dict) and block.get("type") == "text":
            return block
    return None


def _user_message_is_error(content: Any, *, detail: str) -> bool:
    """Determine whether a user/tool-result message represents an error."""
    tool_result = _first_tool_result_block(content)
    if isinstance(tool_result, dict) and tool_result.get("is_error") is True:
        return True
    return '"is_error": true' in detail


def _skill_name_from_instruction_text(text: str) -> str:
    """Extract the skill directory name from a skill bootstrap text block."""
    first_line = _first_line(text)
    prefix = "Base directory for this skill:"
    if not first_line.startswith(prefix):
        return ""
    base_directory = first_line.removeprefix(prefix).strip()
    if not base_directory:
        return ""
    return Path(base_directory).name


def _read_log_events(log_path: Path) -> tuple[dict[str, Any], ...]:
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
    """Find the initial system message event."""
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
    """Return a payload field from an event if present."""
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


def _first_line(text: str) -> str:
    """Return the first non-empty line in a block of text."""
    for line in text.splitlines():
        stripped = line.strip()
        if stripped:
            return stripped
    return ""


def _summarize_timeline_label(*, text: str, fallback: str) -> str:
    """Build a compact label from raw timeline detail."""
    stripped = text.strip()
    if not stripped:
        return fallback

    parsed = _try_parse_json(stripped)
    if isinstance(parsed, dict):
        query = parsed.get("query")
        if isinstance(query, str) and query.strip():
            return f"Query: {query.strip()}"
        if isinstance(parsed.get("results"), list):
            return f"JSON result ({len(parsed['results'])} results)"
        return _summarize_json_object(parsed)
    if isinstance(parsed, list):
        return f"JSON array ({len(parsed)} items)"

    return _first_line(stripped) or fallback


def _assistant_text_label(text: str) -> str:
    """Return a stable title for assistant text blocks."""
    heading = _markdown_heading(text)
    if heading:
        return heading
    return "Assistant Message"


def _try_parse_json(text: str) -> Any:
    """Parse a JSON document when the detail text is JSON."""
    if not text.startswith(("{", "[")):
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def _summarize_json_object(payload: dict[str, Any]) -> str:
    """Build a short label from top-level JSON keys."""
    keys = [str(key) for key in payload.keys()][:3]
    if not keys:
        return "JSON result"
    return f"JSON result ({', '.join(keys)})"


def _markdown_heading(text: str) -> str:
    """Extract the first Markdown heading title from a text block."""
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if not stripped.startswith("#"):
            return ""
        return stripped.lstrip("#").strip()
    return ""


def _latest_file(directory: Path, pattern: str) -> Path | None:
    """Return the latest file matching a glob pattern."""
    if not directory.exists():
        return None
    candidates = sorted(directory.glob(pattern))
    return candidates[-1] if candidates else None


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
