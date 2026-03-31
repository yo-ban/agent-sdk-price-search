"""Port: launcher 前提 runtime の準備と確認。"""

from __future__ import annotations

from typing import Protocol


class RuntimeServicePort(Protocol):
    """検索・ブラウザ runtime の準備ポート。"""

    def ensure_ready(self) -> None:
        """launcher 実行前に必要な runtime を ready にする。"""
