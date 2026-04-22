"""Handler tests for the web discovery CLI."""

from __future__ import annotations

import json
import sys

from web_search_cli.config import AppConfig
from web_search_cli.contracts.request import WebSearchRequest
from web_search_cli.contracts.response import (
    WebSearchResponse,
    WebSearchResultResponse,
)
from web_search_cli.handler import cli


class FakeSearchAdapter:
    """Minimal adapter stub for CLI behavior tests."""

    instances: list[FakeSearchAdapter] = []

    def __init__(self, config: AppConfig) -> None:
        """Store the received config and expose one deterministic response."""
        self.config = config
        self.received_request: WebSearchRequest | None = None
        self.response = WebSearchResponse(
            query="全自動コーヒーメーカー ABC-1234",
            results=(
                WebSearchResultResponse(
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

    def search(self, request: WebSearchRequest) -> WebSearchResponse:
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


def test_build_parser_uses_brave_language_default_when_provider_is_brave(monkeypatch) -> None:
    """Brave provider should expose the Brave-specific language default."""
    expected_config = AppConfig(
        searxng_search_url="http://127.0.0.1:18888/search",
        searxng_engines=("google", "brave"),
        searxng_language="ja-JP",
        searxng_result_limit=8,
        enable_price_research_normalize=True,
        search_provider="brave",
        brave_search_lang="jp",
    )
    monkeypatch.setattr(cli, "load_config", lambda: expected_config)

    parser = cli.build_parser()
    args = parser.parse_args(["全自動コーヒーメーカー ABC-1234"])

    assert args.language == "jp"


def test_run_cli_builds_search_request_and_prints_json(monkeypatch, capsys) -> None:
    """CLI execution should call the adapter with the normalized request."""
    FakeSearchAdapter.instances.clear()
    config = _build_config()
    monkeypatch.setattr(cli, "load_config", lambda: config)
    monkeypatch.setattr(cli, "build_search_adapter", lambda *, config: FakeSearchAdapter(config))
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "web-search",
            "全自動コーヒーメーカー ABC-1234",
            "--include-domain",
            "kakaku.com",
        ],
    )

    exit_code = cli.run_cli()

    assert exit_code == 0
    adapter = FakeSearchAdapter.instances[-1]
    assert adapter.received_request == WebSearchRequest(
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
