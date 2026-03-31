"""オファーのランキングと正規化を行うドメインサービス。"""

from __future__ import annotations

from decimal import Decimal

from price_search.domain.models import (
    IdentifiedProduct,
    PriceOffer,
    PriceResearchReport,
    ProductResearchQuery,
)


def deduplicate_and_rank_offers(
    query: ProductResearchQuery,
    offers: list[PriceOffer],
) -> tuple[PriceOffer, ...]:
    """オファーを重複排除し、対象通貨一致 → 商品価格昇順でランキングする。"""
    # (販売店名, 販売ページURL) をキーにして、同一出品は安い方だけ残す
    unique_offers: dict[tuple[str, str], PriceOffer] = {}
    for offer in offers:
        dedupe_key = (
            offer.merchant_name.strip().lower(),
            offer.merchant_product_url.strip(),
        )
        existing_offer = unique_offers.get(dedupe_key)
        if existing_offer is None or offer.item_price < existing_offer.item_price:
            unique_offers[dedupe_key] = offer

    # 対象通貨に一致するオファーを優先し、商品価格の昇順でソート
    ranked_offers = sorted(
        unique_offers.values(),
        key=lambda offer: (
            offer.currency != query.currency,
            offer.item_price,
            offer.merchant_name.lower(),
            offer.merchant_product_name.lower(),
        ),
    )
    return tuple(ranked_offers[: query.max_offers])


def build_report(
    query: ProductResearchQuery,
    identified_product: IdentifiedProduct,
    summary: str,
    offers: list[PriceOffer],
) -> PriceResearchReport:
    """生のオファー一覧を正規化し、調査レポート集約を構築する。"""
    normalized_summary = summary.strip()
    if not normalized_summary:
        normalized_summary = "要約は生成されませんでした。"

    return PriceResearchReport(
        query=query,
        identified_product=identified_product,
        summary=normalized_summary,
        offers=deduplicate_and_rank_offers(query=query, offers=offers),
    )


def decimal_from_number(value: float | int | str) -> Decimal:
    """アダプター由来の数値を安全に Decimal へ変換する。"""
    return Decimal(str(value))
