"""HTTP server entrypoint for the launcher-backed Web API."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import TYPE_CHECKING, Any, cast
from urllib.parse import urlparse

from price_search_web_api.application.run_application_service import RunApplicationService
from price_search_web_api.bootstrap import build_application
from price_search_web_api.config import load_config
from price_search_web_api.contracts.create_run_request import CreateRunRequest

if TYPE_CHECKING:
    from price_search_web_api.handler.http_server import PriceSearchApiServer


class PriceSearchApiServer(ThreadingHTTPServer):
    """Threading HTTP server with injected application services."""

    def __init__(
        self,
        server_address: tuple[str, int],
        request_handler_class: type[BaseHTTPRequestHandler],
        *,
        run_service: RunApplicationService,
    ) -> None:
        """Store application service dependencies on the server instance."""
        super().__init__(server_address, request_handler_class)
        self.run_service = run_service


class PriceSearchApiHandler(BaseHTTPRequestHandler):
    """Minimal JSON API exposing launcher-backed runs."""

    def do_GET(self) -> None:  # noqa: N802
        """Handle read-only API requests."""
        server = cast("PriceSearchApiServer", self.server)
        parsed = urlparse(self.path)
        if parsed.path == "/api/health":
            self._write_json(HTTPStatus.OK, {"ok": True})
            return
        if parsed.path == "/api/runs":
            payload = [asdict(run) for run in server.run_service.list_runs()]
            self._write_json(HTTPStatus.OK, payload)
            return
        if parsed.path.startswith("/api/runs/"):
            run_id = parsed.path.removeprefix("/api/runs/")
            snapshot = server.run_service.get_run(run_id)
            if snapshot is None:
                self._write_json(HTTPStatus.NOT_FOUND, {"error": "run_not_found"})
                return
            self._write_json(HTTPStatus.OK, asdict(snapshot))
            return
        self._write_json(HTTPStatus.NOT_FOUND, {"error": "not_found"})

    def do_POST(self) -> None:  # noqa: N802
        """Handle run creation requests."""
        server = cast("PriceSearchApiServer", self.server)
        parsed = urlparse(self.path)
        if parsed.path.startswith("/api/runs/") and parsed.path.endswith("/cancel"):
            run_id = parsed.path.removesuffix("/cancel").removeprefix("/api/runs/")
            snapshot = server.run_service.cancel_run(run_id)
            if snapshot is None:
                self._write_json(HTTPStatus.NOT_FOUND, {"error": "run_not_found"})
                return
            self._write_json(HTTPStatus.OK, asdict(snapshot))
            return
        if parsed.path != "/api/runs":
            self._write_json(HTTPStatus.NOT_FOUND, {"error": "not_found"})
            return

        content_length = int(self.headers.get("Content-Length", "0"))
        raw_body = self.rfile.read(content_length) if content_length > 0 else b"{}"
        payload = json.loads(raw_body.decode("utf-8"))
        if not isinstance(payload, dict):
            self._write_json(HTTPStatus.BAD_REQUEST, {"error": "invalid_json"})
            return

        request = CreateRunRequest(
            product_name=str(payload.get("product", "")),
            market=str(payload.get("market", "")),
            currency=str(payload.get("currency", "")),
            max_offers=int(payload.get("maxOffers", 0)),
        )
        snapshot = server.run_service.start_run(request)
        self._write_json(HTTPStatus.CREATED, asdict(snapshot))

    def do_DELETE(self) -> None:  # noqa: N802
        """Handle soft-delete requests for completed runs."""
        server = cast("PriceSearchApiServer", self.server)
        parsed = urlparse(self.path)
        if not parsed.path.startswith("/api/runs/"):
            self._write_json(HTTPStatus.NOT_FOUND, {"error": "not_found"})
            return

        run_id = parsed.path.removeprefix("/api/runs/")
        deleted = server.run_service.delete_run(run_id)
        if not deleted:
            snapshot = server.run_service.get_run(run_id)
            if snapshot is None:
                self._write_json(HTTPStatus.NOT_FOUND, {"error": "run_not_found"})
                return
            self._write_json(HTTPStatus.CONFLICT, {"error": "run_not_deletable"})
            return
        self._write_json(HTTPStatus.OK, {"ok": True})

    def log_message(self, format: str, *args: Any) -> None:
        """Silence default access logging."""
        return

    def _write_json(self, status: HTTPStatus, payload: Any) -> None:
        """Serialize a JSON response with utf-8 headers."""
        encoded = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)


def build_parser() -> argparse.ArgumentParser:
    """Create the CLI parser for the Web API process."""
    config = load_config()
    parser = argparse.ArgumentParser(
        prog="price-search-web-api",
        description="Frontend 向けに launcher-backed run API を提供します。",
    )
    parser.add_argument("--host", default=config.host, help="待受ホスト")
    parser.add_argument("--port", default=config.port, type=int, help="待受ポート")
    return parser


def run_server() -> None:
    """Start the HTTP server and block forever."""
    parser = build_parser()
    args = parser.parse_args()
    run_service = build_application()
    server = PriceSearchApiServer(
        (args.host, args.port),
        PriceSearchApiHandler,
        run_service=run_service,
    )
    server.serve_forever()


def main() -> None:
    """CLI entrypoint for the Web API process."""
    run_server()
