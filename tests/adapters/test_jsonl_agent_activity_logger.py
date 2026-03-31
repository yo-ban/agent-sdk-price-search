"""Adapter tests for the JSONL activity logger."""

from __future__ import annotations

import json

from price_search.adapters.filesystem.jsonl_agent_activity_logger import (
    JsonlAgentActivityLogger,
)
from price_search.ports.agent_activity_log_port import AgentActivityLogEvent


def test_jsonl_agent_activity_logger_appends_run_scoped_event(tmp_path) -> None:
    """Each logged event should be persisted with run metadata."""
    log_path = tmp_path / "activity.jsonl"
    run_id = "run-123"
    event = AgentActivityLogEvent(
        event_type="hook_pretooluse",
        payload={"tool_name": "WebSearch"},
    )
    logger = JsonlAgentActivityLogger(log_path=log_path, run_id=run_id)

    logger.log_event(event)

    records = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines()]
    assert len(records) == 1
    assert records[0]["run_id"] == run_id
    assert records[0]["event_type"] == event.event_type
    assert records[0]["payload"] == event.payload
