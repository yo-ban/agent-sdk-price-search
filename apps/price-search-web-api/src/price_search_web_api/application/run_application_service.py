"""Application layer service for launcher-backed run management."""

from __future__ import annotations

from price_search_web_api.contracts.create_run_request import CreateRunRequest
from price_search_web_api.contracts.run_snapshot import RunSnapshot
from price_search_web_api.ports.run_backend_port import RunBackendPort


class RunApplicationService:
    """Coordinate Web API requests against the launcher-backed run backend."""

    def __init__(self, backend: RunBackendPort) -> None:
        """Store the backend port used by HTTP handlers."""
        self._backend = backend

    def start_run(self, request: CreateRunRequest) -> RunSnapshot:
        """Start a new run and return its initial snapshot."""
        return self._backend.start_run(request)

    def get_run(self, run_id: str) -> RunSnapshot | None:
        """Return the current snapshot for a single run."""
        return self._backend.get_run(run_id)

    def list_runs(self) -> tuple[RunSnapshot, ...]:
        """Return the current run list."""
        return self._backend.list_runs()

    def cancel_run(self, run_id: str) -> RunSnapshot | None:
        """Request cancellation for an in-flight run."""
        return self._backend.cancel_run(run_id)

    def delete_run(self, run_id: str) -> bool:
        """Soft-delete a completed run."""
        return self._backend.delete_run(run_id)
