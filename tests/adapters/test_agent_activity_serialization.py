"""Tests for the public agent activity serialization interface."""

from __future__ import annotations

from claude_agent_sdk import AssistantMessage, ThinkingBlock, ToolUseBlock
from price_search.adapters.claude_sdk.agent_activity_serialization import (
    stream_message_to_log_event,
)


def test_stream_message_to_log_event_serializes_tool_use_block() -> None:
    """Assistant tool-use blocks should be visible in the audit log."""
    tool_use_block = ToolUseBlock(
        id="tool-use-1",
        name="WebSearch",
        input={"query": "全自動コーヒーメーカー ABC-1234"},
    )
    message = AssistantMessage(
        content=[tool_use_block],
        model="global.anthropic.claude-sonnet-4-6",
    )

    event = stream_message_to_log_event(message)

    assert event is not None
    assert event.payload["content"][0]["name"] == tool_use_block.name
    assert event.payload["content"][0]["input"] == tool_use_block.input


def test_stream_message_to_log_event_serializes_thinking_block() -> None:
    """Assistant thinking blocks should be visible in the audit log."""
    thinking_block = ThinkingBlock(
        thinking="compare same-product availability before suggesting a successor",
        signature="sig-1",
    )
    message = AssistantMessage(
        content=[thinking_block],
        model="global.anthropic.claude-sonnet-4-6",
    )

    event = stream_message_to_log_event(message)

    assert event is not None
    assert event.payload["content"][0]["thinking"] == thinking_block.thinking
    assert event.payload["content"][0]["signature"] == thinking_block.signature
