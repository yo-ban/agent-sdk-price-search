"""Application tests for the price research use case."""

from __future__ import annotations

import asyncio

from price_search.application.run_price_research import RunPriceResearchUseCase
from price_search.contracts.price_research_request import PriceResearchRequest
from price_search.ports.price_research_agent_port import (
    PriceResearchAgentPort,
    RawIdentifiedProduct,
    RawOfferResult,
    RawResearchResult,
)


class FakePriceResearchAgent(PriceResearchAgentPort):
    """In-memory fake port for use case tests."""

    def __init__(self, raw_result: RawResearchResult) -> None:
        """Store one raw result fixture and capture the received query."""
        self.raw_result = raw_result
        self.received_query = None

    async def research(self, query):  # type: ignore[override]
        """Return the configured result while recording the request query."""
        self.received_query = query
        return self.raw_result


def test_run_price_research_returns_serialized_offer_fields() -> None:
    """The use case should serialize the contract fields required by the handler layer."""
    request = PriceResearchRequest(
        product_name="Meta Quest 4",
        max_offers=3,
        market="JP",
        currency="JPY",
    )
    raw_result = _build_raw_result(product_name=request.product_name, currency=request.currency)
    fake_agent = FakePriceResearchAgent(raw_result=raw_result)
    use_case = RunPriceResearchUseCase(agent_port=fake_agent)

    response = asyncio.run(use_case.execute(request=request))

    assert fake_agent.received_query is not None
    assert fake_agent.received_query.product_name == request.product_name
    assert response.product_name == request.product_name
    assert response.identified_product.name == raw_result.identified_product.name
    assert response.identified_product.model_number == raw_result.identified_product.model_number
    assert response.identified_product.manufacturer == raw_result.identified_product.manufacturer
    assert response.identified_product.release_date == raw_result.identified_product.release_date
    assert response.identified_product.is_substitute is False
    assert response.offers[0].item_price == str(raw_result.offers[0].item_price)
    assert (
        response.offers[0].merchant_product_url
        == raw_result.offers[0].merchant_product_url
    )
    assert response.summary == raw_result.summary


def _build_raw_result(*, product_name: str, currency: str) -> RawResearchResult:
    """Create one raw research result fixture for use-case serialization tests."""
    return RawResearchResult(
        identified_product=RawIdentifiedProduct(
            name=product_name,
            model_number="MQ4-128",
            manufacturer="Meta",
            product_url="https://example.com/product",
            release_date="2026-03-26",
            is_substitute=False,
            substitution_reason="",
        ),
        summary=f"{product_name} は価格差があります。",
        offers=(
            RawOfferResult(
                merchant_name="Yodobashi",
                merchant_product_name=product_name,
                merchant_product_url="https://example.com/item",
                currency=currency,
                item_price=99800.0,
                availability="在庫あり",
                evidence="販売ページに税込価格と在庫あり表記がある。",
            ),
        ),
    )
