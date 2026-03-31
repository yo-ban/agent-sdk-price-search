"""エージェント実行ログを永続化するためのポート定義。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(frozen=True)
class AgentActivityLogEvent:
    """エージェント実行中に記録される 1 件の監査イベント。"""

    event_type: str
    payload: dict[str, Any]


class AgentActivityLogPort(Protocol):
    """エージェント監査イベントの書き込み先を抽象化するポート。"""

    def log_event(self, event: AgentActivityLogEvent) -> None:
        """監査イベントを 1 件永続化する。"""
