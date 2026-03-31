"""Workspace preparation contract。"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class PreparedWorkspace:
    """launcher が subprocess 実行へ渡す workspace 情報。"""

    workspace_root: Path
    config_file: Path
    local_config_file: Path | None
