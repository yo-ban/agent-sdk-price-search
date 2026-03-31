"""価格調査のオーケストレーションを行うユースケース。"""

from __future__ import annotations

from price_search.contracts.price_research_request import PriceResearchRequest
from price_search.contracts.price_research_response import (
    IdentifiedProductResponse,
    OfferResponse,
    PriceResearchResponse,
)
from price_search.domain.models import IdentifiedProduct, PriceOffer, ProductResearchQuery
from price_search.domain.services import build_report, decimal_from_number
from price_search.ports.price_research_agent_port import PriceResearchAgentPort


class RunPriceResearchUseCase:
    """価格調査のアプリケーションサービス。

    リクエスト DTO → ドメインモデル → エージェント呼び出し → レポート構築 →
    レスポンス DTO の一連の流れを統括する。
    """

    def __init__(self, agent_port: PriceResearchAgentPort) -> None:
        """コンポジションルートから注入された依存を保持する。"""
        self._agent_port = agent_port

    async def execute(self, request: PriceResearchRequest) -> PriceResearchResponse:
        """価格調査フローを実行し、レスポンス DTO を返す。"""
        query = ProductResearchQuery(
            product_name=request.product_name,
            market=request.market,
            currency=request.currency,
            max_offers=request.max_offers,
        )
        raw_result = await self._agent_port.research(query=query)

        raw_product = raw_result.identified_product
        identified_product = IdentifiedProduct(
            name=raw_product.name,
            model_number=raw_product.model_number,
            manufacturer=raw_product.manufacturer,
            product_url=raw_product.product_url,
            release_date=raw_product.release_date,
            is_substitute=raw_product.is_substitute,
            substitution_reason=raw_product.substitution_reason,
        )

        offers = [
            PriceOffer(
                merchant_name=offer.merchant_name,
                merchant_product_name=offer.merchant_product_name,
                merchant_product_url=offer.merchant_product_url,
                currency=offer.currency,
                item_price=decimal_from_number(offer.item_price),
                availability=offer.availability,
                evidence=offer.evidence,
            )
            for offer in raw_result.offers
        ]
        report = build_report(
            query=query,
            identified_product=identified_product,
            summary=raw_result.summary,
            offers=offers,
        )
        return PriceResearchResponse(
            product_name=report.query.product_name,
            identified_product=IdentifiedProductResponse(
                name=report.identified_product.name,
                model_number=report.identified_product.model_number,
                manufacturer=report.identified_product.manufacturer,
                product_url=report.identified_product.product_url,
                release_date=report.identified_product.release_date,
                is_substitute=report.identified_product.is_substitute,
                substitution_reason=report.identified_product.substitution_reason,
            ),
            summary=report.summary,
            offers=tuple(
                OfferResponse(
                    merchant_name=offer.merchant_name,
                    merchant_product_name=offer.merchant_product_name,
                    merchant_product_url=offer.merchant_product_url,
                    currency=offer.currency,
                    item_price=str(offer.item_price),
                    availability=offer.availability,
                    evidence=offer.evidence,
                )
                for offer in report.offers
            ),
        )
