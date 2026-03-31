"""Use case for starting a launcher-backed run."""

from __future__ import annotations

from price_search_web_api.contracts.create_run_request import CreateRunRequest
from price_search_web_api.contracts.run_snapshot import RunSnapshot
from price_search_web_api.ports.run_launcher_port import RunLauncherPort


class StartRunUseCase:
    """Application service for creating a run."""

    def __init__(self, run_launcher: RunLauncherPort) -> None:
        """Store the launcher port dependency."""
        self._run_launcher = run_launcher

    def execute(self, request: CreateRunRequest) -> RunSnapshot:
        """Start a run through the launcher port."""
        return self._run_launcher.start_run(request)

