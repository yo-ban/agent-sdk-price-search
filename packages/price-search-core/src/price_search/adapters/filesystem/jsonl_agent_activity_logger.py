"""エージェント実行ログを JSONL ファイルへ書き出すアダプター。"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from threading import Lock

from price_search.ports.agent_activity_log_port import (
    AgentActivityLogEvent,
    AgentActivityLogPort,
)


class JsonlAgentActivityLogger(AgentActivityLogPort):
    """監査イベントを JSONL ファイルへ追記するロガー。"""

    def __init__(self, log_path: str | Path, run_id: str) -> None:
        """ログファイルのパスと実行 ID を保持する。"""
        self._log_path = Path(log_path)
        self._run_id = run_id
        self._lock = Lock()  # 複数スレッドからの同時書き込みを排他制御

    @property
    def log_path(self) -> Path:
        """このロガーが使用する JSONL ファイルのパスを返す。"""
        return self._log_path

    def log_event(self, event: AgentActivityLogEvent) -> None:
        """1 件のイベントを JSON 行として追記する。"""
        record = {
            "logged_at": datetime.now(UTC).isoformat(),
            "run_id": self._run_id,
            "event_type": event.event_type,
            "payload": event.payload,
        }
        self._log_path.parent.mkdir(parents=True, exist_ok=True)
        with self._lock:
            with self._log_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(record, ensure_ascii=False))
                handle.write("\n")
