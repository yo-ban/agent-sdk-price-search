"""価格調査ユースケースの出力 DTO。"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class IdentifiedProductResponse:
    """特定された製品情報のレスポンス DTO。"""

    name: str
    model_number: str
    manufacturer: str
    product_url: str
    release_date: str
    is_substitute: bool
    substitution_reason: str


@dataclass(frozen=True)
class OfferResponse:
    """ユースケースが返すシリアライズ済みオファー。

    金額フィールドは JSON 出力での精度維持のため文字列で保持する。
    """

    merchant_name: str
    merchant_product_name: str
    merchant_product_url: str
    currency: str
    item_price: str
    availability: str
    evidence: str


@dataclass(frozen=True)
class PriceResearchResponse:
    """価格調査ユースケースからの出力データ。"""

    product_name: str
    identified_product: IdentifiedProductResponse
    summary: str
    offers: tuple[OfferResponse, ...]
