"""価格調査ドメインのエンティティと値オブジェクト。"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class ProductResearchQuery:
    """価格調査の検索条件を表す値オブジェクト。"""

    product_name: str
    market: str  # 対象市場コード (例: "JP")
    currency: str  # 対象通貨コード (例: "JPY")
    max_offers: int  # 返却するオファーの最大件数


@dataclass(frozen=True)
class IdentifiedProduct:
    """エージェントが特定した調査対象の製品情報。"""

    name: str  # 正式製品名
    model_number: str  # 型番 (不明なら空文字列)
    manufacturer: str  # メーカー (不明なら空文字列)
    product_url: str  # 製造元または販売元の製品ページ URL (不明なら空文字列)
    release_date: str  # 発売日 (不明なら空文字列)
    is_substitute: bool  # 要求品そのものではなく代替対象を返したかどうか
    substitution_reason: str  # 代替理由 (is_substitute=False なら空文字列)


@dataclass(frozen=True)
class PriceOffer:
    """調査で取得した 1 件の価格オファーを表すエンティティ。"""

    merchant_name: str
    merchant_product_name: str  # 販売店の商品ページ上の掲載名
    merchant_product_url: str  # 販売店自身の商品ページ URL
    currency: str
    item_price: Decimal
    availability: str
    evidence: str  # 販売ページから読み取った根拠の要約 (1 文)


@dataclass(frozen=True)
class PriceResearchReport:
    """重複排除・ランキング済みの調査結果を束ねる集約。"""

    query: ProductResearchQuery
    identified_product: IdentifiedProduct
    summary: str
    offers: tuple[PriceOffer, ...]
