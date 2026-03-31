"""Application service for soft-deleting launcher-backed runs."""

from __future__ import annotations

from price_search_web_api.ports.run_control_port import RunControlPort


class DeleteRunUseCase:
    """Hide one completed run from the visible history."""

    def __init__(self, run_control: RunControlPort) -> None:
        """Store the run control port."""
        self._run_control = run_control

    def execute(self, run_id: str) -> bool:
        """Soft-delete one run and report whether it was accepted."""
        return self._run_control.delete_run(run_id)
