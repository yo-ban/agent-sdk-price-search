"""Handler tests for the SearXNG discovery CLI."""

from __future__ import annotations

import json
import sys

from searxng_search_cli.config import AppConfig
from searxng_search_cli.contracts.request import SearxngSearchRequest
from searxng_search_cli.contracts.response import (
    SearxngSearchResponse,
    SearxngSearchResultResponse,
)
from searxng_search_cli.handler import cli


class FakeSearchAdapter:
    """Minimal adapter stub for CLI behavior tests."""

    instances: list[FakeSearchAdapter] = []

    def __init__(self, config: AppConfig) -> None:
        """Store the received config and expose one deterministic response."""
        self.config = config
        self.received_request: SearxngSearchRequest | None = None
        self.response = SearxngSearchResponse(
            query="全自動コーヒーメーカー ABC-1234",
            results=(
                SearxngSearchResultResponse(
                    title="比較結果",
                    url="https://example.com/item",
                    host="example.com",
                    snippet="価格比較",
                    engines=("google",),
                    category="general",
                    score=0.5,
                ),
            ),
        )
        self.__class__.instances.append(self)

    def search(self, request: SearxngSearchRequest) -> SearxngSearchResponse:
        """Record the request and return the configured response."""
        self.received_request = request
        return self.response


def test_build_parser_uses_loaded_defaults(monkeypatch) -> None:
    """Parser defaults should reflect the loaded runtime config."""
    expected_config = _build_config()
    monkeypatch.setattr(cli, "load_config", lambda: expected_config)

    parser = cli.build_parser()
    args = parser.parse_args(["全自動コーヒーメーカー ABC-1234"])

    assert args.limit == expected_config.searxng_result_limit
    assert args.language == expected_config.searxng_language


def test_run_cli_builds_search_request_and_prints_json(monkeypatch, capsys) -> None:
    """CLI execution should call the adapter with the normalized request."""
    FakeSearchAdapter.instances.clear()
    config = _build_config()
    monkeypatch.setattr(cli, "load_config", lambda: config)
    monkeypatch.setattr(cli, "SelfHostedSearxngSearchAdapter", FakeSearchAdapter)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "searxng-search",
            "全自動コーヒーメーカー ABC-1234",
            "--include-domain",
            "kakaku.com",
        ],
    )

    exit_code = cli.run_cli()

    assert exit_code == 0
    adapter = FakeSearchAdapter.instances[-1]
    assert adapter.received_request == SearxngSearchRequest(
        query="全自動コーヒーメーカー ABC-1234",
        limit=config.searxng_result_limit,
        language=config.searxng_language,
        engines=config.searxng_engines,
        include_domains=("kakaku.com",),
        exclude_domains=(),
    )
    printed = json.loads(capsys.readouterr().out)
    assert printed["query"] == adapter.response.query
    assert printed["results"][0]["url"] == adapter.response.results[0].url


def _build_config() -> AppConfig:
    """Create a representative AppConfig for CLI tests."""
    return AppConfig(
        searxng_search_url="http://127.0.0.1:18888/search",
        searxng_engines=("google", "brave"),
        searxng_language="ja-JP",
        searxng_result_limit=8,
        enable_price_research_normalize=True,
    )
