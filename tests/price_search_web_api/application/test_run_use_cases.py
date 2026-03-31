"""Application tests for the launcher-backed Web API."""

from __future__ import annotations

from price_search_web_api.application.cancel_run import CancelRunUseCase
from price_search_web_api.application.delete_run import DeleteRunUseCase
from price_search_web_api.application.get_run import GetRunUseCase
from price_search_web_api.application.list_runs import ListRunsUseCase
from price_search_web_api.application.start_run import StartRunUseCase
from price_search_web_api.contracts.create_run_request import CreateRunRequest
from price_search_web_api.contracts.run_snapshot import RunSnapshot


class FakeRunBackend:
    """In-memory fake implementing both launcher and query behaviors."""

    def __init__(self, snapshots: tuple[RunSnapshot, ...]) -> None:
        """Store snapshots for deterministic responses."""
        self._snapshots = {snapshot.run_id: snapshot for snapshot in snapshots}
        self.started_requests: list[CreateRunRequest] = []
        self.cancelled_run_ids: list[str] = []
        self.deleted_run_ids: list[str] = []

    def start_run(self, request: CreateRunRequest) -> RunSnapshot:
        """Record the request and return the first snapshot."""
        self.started_requests.append(request)
        return next(iter(self._snapshots.values()))

    def get_run(self, run_id: str) -> RunSnapshot | None:
        """Return one snapshot by run ID."""
        return self._snapshots.get(run_id)

    def list_runs(self) -> tuple[RunSnapshot, ...]:
        """Return all snapshots."""
        return tuple(self._snapshots.values())

    def cancel_run(self, run_id: str) -> RunSnapshot | None:
        """Record the cancelled run ID and return the matching snapshot."""
        self.cancelled_run_ids.append(run_id)
        return self._snapshots.get(run_id)

    def delete_run(self, run_id: str) -> bool:
        """Record the deleted run ID and report success when present."""
        self.deleted_run_ids.append(run_id)
        return run_id in self._snapshots


def test_start_run_use_case_returns_created_snapshot() -> None:
    """Starting a run delegates to the launcher port."""
    snapshot = _build_snapshot(run_id="run-1")
    backend = FakeRunBackend((snapshot,))
    request = CreateRunRequest(
        product_name="全自動コーヒーメーカー ABC-1234",
        market="JP",
        currency="JPY",
        max_offers=3,
    )

    created = StartRunUseCase(run_launcher=backend).execute(request)

    assert created == snapshot
    assert backend.started_requests == [request]


def test_get_run_use_case_returns_matching_snapshot() -> None:
    """Fetching one run delegates to the query port."""
    snapshot = _build_snapshot(run_id="run-2")
    backend = FakeRunBackend((snapshot,))

    loaded = GetRunUseCase(run_query=backend).execute("run-2")

    assert loaded == snapshot


def test_list_runs_use_case_returns_available_snapshots() -> None:
    """Listing runs delegates to the query port."""
    snapshots = (_build_snapshot(run_id="run-a"), _build_snapshot(run_id="run-b"))
    backend = FakeRunBackend(snapshots)

    listed = ListRunsUseCase(run_query=backend).execute()

    assert listed == snapshots


def test_cancel_run_use_case_returns_matching_snapshot() -> None:
    """Canceling a run delegates to the control port."""
    snapshot = _build_snapshot(run_id="run-cancel")
    backend = FakeRunBackend((snapshot,))

    cancelled = CancelRunUseCase(run_control=backend).execute("run-cancel")

    assert cancelled == snapshot
    assert backend.cancelled_run_ids == ["run-cancel"]


def test_delete_run_use_case_reports_soft_delete_result() -> None:
    """Soft-deleting a run delegates to the control port."""
    snapshot = _build_snapshot(run_id="run-delete")
    backend = FakeRunBackend((snapshot,))

    deleted = DeleteRunUseCase(run_control=backend).execute("run-delete")

    assert deleted is True
    assert backend.deleted_run_ids == ["run-delete"]


def _build_snapshot(run_id: str) -> RunSnapshot:
    """Create a minimal snapshot for application tests."""
    return RunSnapshot(
        run_id=run_id,
        product_name="全自動コーヒーメーカー ABC-1234",
        market="JP",
        currency="JPY",
        max_offers=3,
        model="claude-sonnet-4-6",
        status="researching",
        started_at="2026-03-29T00:00:00+00:00",
        finished_at=None,
        duration_ms=0,
        total_cost_usd=None,
        num_turns=None,
        result=None,
        timeline=(),
    )
