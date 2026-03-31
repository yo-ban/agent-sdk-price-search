"""Application layer: 隔離 workspace での price-search 実行オーケストレーション。"""

from __future__ import annotations

from price_search_launcher.contracts.isolated_price_search_request import (
    IsolatedPriceSearchRequest,
)
from price_search_launcher.ports.process_runner_port import ProcessRunnerPort
from price_search_launcher.ports.runtime_service_port import RuntimeServicePort
from price_search_launcher.ports.workspace_port import WorkspacePort


class LaunchPriceSearchUseCase:
    """runtime 準備、workspace 作成、subprocess 実行を統括する。"""

    def __init__(
        self,
        *,
        runtime_service: RuntimeServicePort,
        workspace_port: WorkspacePort,
        process_runner: ProcessRunnerPort,
    ) -> None:
        """依存ポートを保持する。"""
        self._runtime_service = runtime_service
        self._workspace_port = workspace_port
        self._process_runner = process_runner

    def execute(self, request: IsolatedPriceSearchRequest) -> int:
        """隔離 workspace で price-search を起動し、終了後に cleanup する。"""
        self._runtime_service.ensure_ready()
        prepared_workspace = self._workspace_port.prepare_workspace(
            launch_directory=request.launch_directory
        )
        try:
            return self._process_runner.run_price_search(
                cli_args=request.cli_args,
                prepared_workspace=prepared_workspace,
            )
        finally:
            self._workspace_port.cleanup_workspace(
                workspace_root=prepared_workspace.workspace_root
            )
