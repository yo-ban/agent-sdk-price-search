"""HTTP handler tests for the launcher-backed Web API."""

from __future__ import annotations

import http.client
import json
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import asdict
from threading import Thread
from typing import Any, cast

from price_search_web_api.application.run_application_service import RunApplicationService
from price_search_web_api.contracts.create_run_request import CreateRunRequest
from price_search_web_api.contracts.run_snapshot import RunSnapshot, RunStatus
from price_search_web_api.handler.http_server import PriceSearchApiHandler, PriceSearchApiServer


class FakeRunService:
    """In-memory run service for HTTP handler behavior tests."""

    def __init__(self, snapshots: tuple[RunSnapshot, ...]) -> None:
        """Store snapshots and capture incoming mutations."""
        self._snapshots = {snapshot.run_id: snapshot for snapshot in snapshots}
        self.started_requests: list[CreateRunRequest] = []
        self.cancelled_run_ids: list[str] = []
        self.deleted_run_ids: list[str] = []

    def start_run(self, request: CreateRunRequest) -> RunSnapshot:
        """Record the request and return the first configured snapshot."""
        self.started_requests.append(request)
        return next(iter(self._snapshots.values()))

    def get_run(self, run_id: str) -> RunSnapshot | None:
        """Return one configured snapshot by ID."""
        return self._snapshots.get(run_id)

    def list_runs(self) -> tuple[RunSnapshot, ...]:
        """Return all configured snapshots."""
        return tuple(self._snapshots.values())

    def cancel_run(self, run_id: str) -> RunSnapshot | None:
        """Record the cancellation request and return the matching snapshot."""
        self.cancelled_run_ids.append(run_id)
        return self._snapshots.get(run_id)

    def delete_run(self, run_id: str) -> bool:
        """Record the delete request and report whether the run is deletable."""
        self.deleted_run_ids.append(run_id)
        return False


@contextmanager
def _running_server(run_service: FakeRunService) -> Iterator[PriceSearchApiServer]:
    """Start a test HTTP server and shut it down after the assertion scope."""
    server = PriceSearchApiServer(
        ("127.0.0.1", 0),
        PriceSearchApiHandler,
        run_service=cast(RunApplicationService, run_service),
    )
    thread = Thread(target=server.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True)
    thread.start()
    try:
        yield server
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()


def test_get_runs_returns_service_snapshots() -> None:
    """GET /api/runs should serialize the application service snapshots."""
    snapshot = _build_snapshot(run_id="run-1")
    run_service = FakeRunService((snapshot,))

    with _running_server(run_service) as server:
        status, payload = _request_json(server, "GET", "/api/runs")

    assert status == 200
    assert payload == [_snapshot_response(snapshot)]


def test_post_runs_builds_create_run_request_from_json_payload() -> None:
    """POST /api/runs should convert request JSON into the create-run contract."""
    snapshot = _build_snapshot(run_id="run-2")
    run_service = FakeRunService((snapshot,))

    with _running_server(run_service) as server:
        status, payload = _request_json(
            server,
            "POST",
            "/api/runs",
            body={
                "product": "全自動コーヒーメーカー ABC-1234",
                "market": "JP",
                "currency": "JPY",
                "maxOffers": 3,
            },
        )

    assert status == 201
    assert payload == _snapshot_response(snapshot)
    assert run_service.started_requests == [
        CreateRunRequest(
            product_name="全自動コーヒーメーカー ABC-1234",
            market="JP",
            currency="JPY",
            max_offers=3,
        )
    ]


def test_post_cancel_returns_not_found_for_missing_run() -> None:
    """POST /api/runs/<id>/cancel should report missing runs through the API."""
    run_service = FakeRunService(())

    with _running_server(run_service) as server:
        status, payload = _request_json(server, "POST", "/api/runs/missing-run/cancel")

    assert status == 404
    assert payload == {"error": "run_not_found"}
    assert run_service.cancelled_run_ids == ["missing-run"]


def test_delete_returns_conflict_when_service_rejects_terminal_delete() -> None:
    """DELETE /api/runs/<id> should map a rejected delete to the conflict response."""
    snapshot = _build_snapshot(run_id="run-3", status="finished")
    run_service = FakeRunService((snapshot,))

    with _running_server(run_service) as server:
        status, payload = _request_json(server, "DELETE", "/api/runs/run-3")

    assert status == 409
    assert payload == {"error": "run_not_deletable"}
    assert run_service.deleted_run_ids == ["run-3"]


def _request_json(
    server: PriceSearchApiServer,
    method: str,
    path: str,
    body: dict[str, Any] | None = None,
) -> tuple[int, Any]:
    """Send one JSON request to the test server and decode the response body."""
    connection = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=5)
    encoded_body = None
    headers: dict[str, str] = {}
    if body is not None:
        encoded_body = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
        headers["Content-Length"] = str(len(encoded_body))
    connection.request(method, path, body=encoded_body, headers=headers)
    response = connection.getresponse()
    payload = json.loads(response.read().decode("utf-8"))
    connection.close()
    return response.status, payload


def _build_snapshot(run_id: str, status: RunStatus = "researching") -> RunSnapshot:
    """Create a minimal snapshot for HTTP handler tests."""
    return RunSnapshot(
        run_id=run_id,
        product_name="全自動コーヒーメーカー ABC-1234",
        market="JP",
        currency="JPY",
        max_offers=3,
        model="claude-sonnet-4-6",
        status=status,
        started_at="2026-03-29T00:00:00+00:00",
        finished_at=None if status == "researching" else "2026-03-29T00:01:00+00:00",
        duration_ms=0,
        total_cost_usd=None,
        num_turns=None,
        result=None,
        timeline=(),
    )


def _snapshot_response(snapshot: RunSnapshot) -> dict[str, Any]:
    """Normalize dataclass output to the JSON shape returned by the handler."""
    payload = asdict(snapshot)
    payload["timeline"] = list(payload["timeline"])
    return payload
