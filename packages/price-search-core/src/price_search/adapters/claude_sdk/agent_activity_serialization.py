"""Infrastructure layer: Claude SDK ストリームメッセージの監査ログ変換。"""

from __future__ import annotations

from typing import Any

from claude_agent_sdk import (
    AssistantMessage,
    ResultMessage,
    SystemMessage,
    TaskNotificationMessage,
    TaskProgressMessage,
    TaskStartedMessage,
    TextBlock,
    ThinkingBlock,
    ToolResultBlock,
    ToolUseBlock,
    UserMessage,
)

from price_search.ports.agent_activity_log_port import AgentActivityLogEvent


def stream_message_to_log_event(message: Any) -> AgentActivityLogEvent | None:
    """SDK からのストリームメッセージを監査ログイベントに変換する。"""
    if isinstance(message, AssistantMessage):
        return AgentActivityLogEvent(
            event_type="assistant_message",
            payload={
                "model": message.model,
                "parent_tool_use_id": message.parent_tool_use_id,
                "error": message.error,
                "usage": _to_jsonable(message.usage),
                "content": [_content_block_to_jsonable(block) for block in message.content],
            },
        )
    if isinstance(message, UserMessage):
        return AgentActivityLogEvent(
            event_type="user_message",
            payload={
                "uuid": message.uuid,
                "parent_tool_use_id": message.parent_tool_use_id,
                "tool_use_result": _to_jsonable(message.tool_use_result),
                "content": _user_content_to_jsonable(message.content),
            },
        )
    if isinstance(message, ResultMessage):
        return AgentActivityLogEvent(
            event_type="result_message",
            payload={
                "subtype": message.subtype,
                "duration_ms": message.duration_ms,
                "duration_api_ms": message.duration_api_ms,
                "is_error": message.is_error,
                "num_turns": message.num_turns,
                "session_id": message.session_id,
                "stop_reason": message.stop_reason,
                "total_cost_usd": message.total_cost_usd,
                "usage": _to_jsonable(message.usage),
                "result": message.result,
                "structured_output": _to_jsonable(message.structured_output),
            },
        )
    if isinstance(message, TaskStartedMessage):
        return AgentActivityLogEvent(
            event_type="task_started_message",
            payload={
                "task_id": message.task_id,
                "description": message.description,
                "uuid": message.uuid,
                "session_id": message.session_id,
                "tool_use_id": message.tool_use_id,
                "task_type": message.task_type,
            },
        )
    if isinstance(message, TaskProgressMessage):
        return AgentActivityLogEvent(
            event_type="task_progress_message",
            payload={
                "task_id": message.task_id,
                "description": message.description,
                "usage": _to_jsonable(message.usage),
                "uuid": message.uuid,
                "session_id": message.session_id,
                "tool_use_id": message.tool_use_id,
                "last_tool_name": message.last_tool_name,
            },
        )
    if isinstance(message, TaskNotificationMessage):
        return AgentActivityLogEvent(
            event_type="task_notification_message",
            payload={
                "subtype": message.subtype,
                "task_id": message.task_id,
                "status": message.status,
                "output_file": message.output_file,
                "summary": message.summary,
                "uuid": message.uuid,
                "session_id": message.session_id,
                "tool_use_id": message.tool_use_id,
                "usage": _to_jsonable(message.usage),
            },
        )
    if isinstance(message, SystemMessage):
        return AgentActivityLogEvent(
            event_type="system_message",
            payload={
                "subtype": message.subtype,
                "data": _to_jsonable(message.data),
            },
        )
    return None


def _content_block_to_jsonable(block: Any) -> dict[str, Any]:
    """アシスタントのコンテンツブロックを監査ログ用にシリアライズする。"""
    if isinstance(block, TextBlock):
        return {"type": "text", "text": block.text}
    if isinstance(block, ThinkingBlock):
        return {
            "type": "thinking",
            "thinking": block.thinking,
            "signature": block.signature,
        }
    if isinstance(block, ToolUseBlock):
        return {
            "type": "tool_use",
            "id": block.id,
            "name": block.name,
            "input": _to_jsonable(block.input),
        }
    if isinstance(block, ToolResultBlock):
        return {
            "type": "tool_result",
            "tool_use_id": block.tool_use_id,
            "content": _to_jsonable(block.content),
            "is_error": block.is_error,
        }
    return {"type": block.__class__.__name__}


def _user_content_to_jsonable(content: Any) -> Any:
    """ユーザーメッセージのコンテンツブロックを監査ログ用にシリアライズする。"""
    if isinstance(content, str):
        return content
    return [_content_block_to_jsonable(block) for block in content]


def _to_jsonable(value: Any) -> Any:
    """SDK の値を JSON シリアライズ可能な構造に変換する。"""
    if value is None or isinstance(value, str | int | float | bool):
        return value
    if isinstance(value, dict):
        return {str(key): _to_jsonable(item) for key, item in value.items()}
    if isinstance(value, list | tuple):
        return [_to_jsonable(item) for item in value]
    return str(value)
