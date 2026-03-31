"""Tests for the SearXNG discovery use case."""

from __future__ import annotations

from searxng_search_cli.application.run_search import RunSearxngSearchUseCase
from searxng_search_cli.contracts.request import SearxngSearchRequest
from searxng_search_cli.contracts.response import (
    SearxngSearchResponse,
    SearxngSearchResultResponse,
)


class FakeSearxngSearchPort:
    """In-memory fake discovery port."""

    def __init__(self, response: SearxngSearchResponse) -> None:
        """Store one response fixture and capture the request."""
        self.response = response
        self.received_request: SearxngSearchRequest | None = None

    def search(self, request: SearxngSearchRequest) -> SearxngSearchResponse:
        """Return the configured response while recording the request."""
        self.received_request = request
        return self.response


def test_run_searxng_search_returns_port_response() -> None:
    """The use case should delegate to the port and return its response unchanged."""
    request = SearxngSearchRequest(
        query="全自動コーヒーメーカー ABC-1234",
        limit=5,
        language="ja-JP",
        engines=("google", "brave"),
        include_domains=("kakaku.com",),
        exclude_domains=(),
    )
    expected_response = SearxngSearchResponse(
        query=request.query,
        results=(
            SearxngSearchResultResponse(
                title="全自動コーヒーメーカー ABC-1234 価格比較",
                url="https://kakaku.com/item/K0000700536/",
                host="kakaku.com",
                snippet="価格比較",
                engines=(request.engines[0],),
                category="general",
                score=0.5,
            ),
        ),
    )
    fake_port = FakeSearxngSearchPort(response=expected_response)
    use_case = RunSearxngSearchUseCase(search_port=fake_port)

    response = use_case.execute(request)

    assert fake_port.received_request == request
    assert response == expected_response
