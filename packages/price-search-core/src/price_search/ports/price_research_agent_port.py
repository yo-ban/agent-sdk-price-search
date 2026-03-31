"""価格調査エージェント実装のためのポート定義。"""

from __future__ import annotations

from abc import abstractmethod
from dataclasses import dataclass
from typing import Protocol

from price_search.domain.models import ProductResearchQuery


@dataclass(frozen=True)
class RawIdentifiedProduct:
    """エージェントが特定した製品情報の未加工ペイロード。"""

    name: str
    model_number: str
    manufacturer: str
    product_url: str
    release_date: str
    is_substitute: bool
    substitution_reason: str


@dataclass(frozen=True)
class RawOfferResult:
    """エージェントアダプターが返す未加工のオファーペイロード。

    ドメインモデル (PriceOffer) への変換はユースケース層で行う。
    """

    merchant_name: str
    merchant_product_name: str
    merchant_product_url: str
    currency: str
    item_price: float  # ドメイン層で Decimal に変換される
    availability: str
    evidence: str


@dataclass(frozen=True)
class RawResearchResult:
    """エージェントアダプターが返す未加工の調査結果。"""

    identified_product: RawIdentifiedProduct
    summary: str
    offers: tuple[RawOfferResult, ...]


class PriceResearchAgentPort(Protocol):
    """価格調査エージェントの抽象ポート。"""

    @abstractmethod
    async def research(self, query: ProductResearchQuery) -> RawResearchResult:
        """指定された商品の価格調査を実行し、未加工の結果を返す。"""
