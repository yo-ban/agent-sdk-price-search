"""Application service for canceling launcher-backed runs."""

from __future__ import annotations

from price_search_web_api.contracts.run_snapshot import RunSnapshot
from price_search_web_api.ports.run_control_port import RunControlPort


class CancelRunUseCase:
    """Request interruption of one active run."""

    def __init__(self, run_control: RunControlPort) -> None:
        """Store the run control port."""
        self._run_control = run_control

    def execute(self, run_id: str) -> RunSnapshot | None:
        """Cancel one run and return its latest snapshot if it exists."""
        return self._run_control.cancel_run(run_id)
