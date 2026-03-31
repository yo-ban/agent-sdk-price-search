"""Port: isolated workspace から price-search を起動する。"""

from __future__ import annotations

from typing import Protocol

from price_search_launcher.contracts.prepared_workspace import PreparedWorkspace


class ProcessRunnerPort(Protocol):
    """price-search subprocess 実行ポート。"""

    def run_price_search(
        self,
        *,
        cli_args: tuple[str, ...],
        prepared_workspace: PreparedWorkspace,
    ) -> int:
        """prepared workspace を使って price-search を起動する。"""
        ...
