"""価格調査ユースケースの入力 DTO。"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PriceResearchRequest:
    """価格調査ユースケースへの入力データ。"""

    product_name: str
    max_offers: int
    market: str
    currency: str
