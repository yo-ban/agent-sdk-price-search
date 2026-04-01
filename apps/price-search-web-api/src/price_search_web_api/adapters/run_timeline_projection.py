"""Infrastructure projection from Claude activity logs to frontend timeline entries."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, TypedDict

from price_search_web_api.contracts.run_snapshot import TimelineEntry, TimelineKind


class _UserMessageClassification(TypedDict):
    """Typed classification result for user-side timeline events."""

    kind: TimelineKind
    label: str


def build_run_timeline(
    *,
    log_events: tuple[dict[str, Any], ...],
    started_at_ms: int,
) -> tuple[TimelineEntry, ...]:
    """Translate JSONL activity events into frontend timeline entries."""
    tool_use_name_by_id = _build_tool_use_name_index(log_events)
    return tuple(
        entry
        for event in log_events
        for entry in _event_to_timeline_entries(
            event=event,
            started_at_ms=started_at_ms,
            tool_use_name_by_id=tool_use_name_by_id,
        )
    )


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
        return tuple(
            _assistant_block_to_entry(block=block, t=t)
            for block in content
            if isinstance(block, dict)
        )

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
        if _user_message_is_error(payload.get("content"), detail=detail):
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
    """Extract human-readable text from user and tool-result blocks."""
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
    """Determine whether a user or tool-result message represents an error."""
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


def _to_epoch_ms(iso_timestamp: str) -> int:
    """Convert an ISO timestamp to epoch milliseconds."""
    if not iso_timestamp:
        return 0
    normalized = iso_timestamp.replace("Z", "+00:00")
    return int(datetime.fromisoformat(normalized).timestamp() * 1000)


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
