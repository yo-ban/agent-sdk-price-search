"""Handler tests for the public CLI interface."""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

from price_search.config import AppConfig
from price_search.contracts.price_research_response import (
    IdentifiedProductResponse,
    OfferResponse,
    PriceResearchResponse,
)
from price_search.handler import cli


class FakeUseCase:
    """Minimal fake use case for CLI behavior tests."""

    def __init__(self, response: PriceResearchResponse) -> None:
        """Keep a deterministic response and capture the received request."""
        self._response = response
        self.received_request = None

    async def execute(self, request):  # type: ignore[override]
        """Return the configured response while recording the input request."""
        self.received_request = request
        return self._response


def test_build_parser_uses_loaded_defaults(monkeypatch, tmp_path: Path) -> None:
    """Parser defaults should reflect the loaded runtime config."""
    expected_config = _build_config(tmp_path)
    monkeypatch.setattr(cli, "load_config", lambda: expected_config)

    parser = cli.build_parser()
    args = parser.parse_args(["全自動コーヒーメーカー ABC-1234"])

    assert (args.max_offers, args.market, args.currency) == (
        expected_config.max_offers,
        expected_config.market,
        expected_config.currency,
    )


def test_run_cli_writes_json_to_explicit_output_path(
    monkeypatch,
    tmp_path: Path,
    capsys,
) -> None:
    """CLI execution should write the response JSON to the requested output path."""
    response = _build_response()
    fake_use_case = FakeUseCase(response=response)
    output_file = tmp_path / "result.json"

    monkeypatch.setattr(cli, "load_config", lambda: _build_config(tmp_path))
    monkeypatch.setattr(cli, "build_use_case", lambda *, product_name: fake_use_case)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "price-search",
            response.product_name,
            "--json",
            "--output-file",
            str(output_file),
        ],
    )

    exit_code = asyncio.run(cli.run_cli())

    assert exit_code == 0
    assert fake_use_case.received_request is not None
    assert fake_use_case.received_request.product_name == response.product_name
    assert output_file.exists()
    persisted = json.loads(output_file.read_text(encoding="utf-8"))
    assert persisted["product_name"] == response.product_name
    assert (
        persisted["offers"][0]["merchant_product_url"]
        == response.offers[0].merchant_product_url
    )
    stdout = capsys.readouterr().out
    assert json.loads(stdout) == persisted


def _build_config(tmp_path: Path) -> AppConfig:
    """Create a representative AppConfig for CLI tests."""
    return AppConfig(
        claude_provider="subscription",
        aws_region="ap-northeast-1",
        aws_profile="default",
        anthropic_api_key=None,
        openrouter_api_key=None,
        primary_model="claude-sonnet-4-6",
        small_model="claude-haiku-4-5",
        primary_model_capabilities=None,
        small_model_capabilities=None,
        agent_thinking_type="enabled",
        agent_thinking_budget_tokens=4096,
        agent_effort="high",
        max_turns=100,
        max_offers=4,
        market="JP",
        currency="JPY",
        agent_activity_log_dir=str(tmp_path / "logs"),
        result_output_dir=str(tmp_path / "out"),
        searxng_search_url="http://127.0.0.1:18888/search",
        searxng_engines=("google", "brave"),
        searxng_language="ja-JP",
        searxng_result_limit=8,
        workspace_root=str(tmp_path),
    )


def _build_response() -> PriceResearchResponse:
    """Create a stable response payload for CLI serialization tests."""
    return PriceResearchResponse(
        product_name="全自動コーヒーメーカー ABC-1234",
        identified_product=IdentifiedProductResponse(
            name="全自動コーヒーメーカー ABC-1234",
            model_number="BEE-001",
            manufacturer="ExampleMaker",
            product_url="https://example.com/products/abc-1234",
            release_date="2026-03-27",
            is_substitute=False,
            substitution_reason="",
        ),
        summary="価格差があります。",
        offers=(
            OfferResponse(
                merchant_name="Yodobashi",
                merchant_product_name="全自動コーヒーメーカー ABC-1234",
                merchant_product_url="https://example.com/item",
                currency="JPY",
                item_price="69980",
                availability="在庫あり",
                evidence="販売ページに在庫ありと税込価格の記載がある。",
            ),
        ),
    )
