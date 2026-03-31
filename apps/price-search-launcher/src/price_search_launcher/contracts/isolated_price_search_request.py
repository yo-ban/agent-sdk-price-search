"""Launcher request contract。"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class IsolatedPriceSearchRequest:
    """隔離 workspace 実行に必要な launcher 入力。"""

    cli_args: tuple[str, ...]
    launch_directory: Path
