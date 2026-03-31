"""Port: isolated workspace の作成と破棄。"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from price_search_launcher.contracts.prepared_workspace import PreparedWorkspace


class WorkspacePort(Protocol):
    """workspace lifecycle を扱うポート。"""

    def prepare_workspace(self, *, launch_directory: Path) -> PreparedWorkspace:
        """実行用 workspace を作成する。"""
        ...

    def cleanup_workspace(self, *, workspace_root: Path) -> None:
        """実行後 workspace を削除する。"""
        ...
