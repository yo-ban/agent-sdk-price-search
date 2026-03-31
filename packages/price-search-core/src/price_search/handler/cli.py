"""価格調査ユースケースの CLI ハンドラー。"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

from price_search.bootstrap import build_use_case
from price_search.config import load_config
from price_search.contracts.price_research_request import PriceResearchRequest


def build_parser() -> argparse.ArgumentParser:
    """アプリケーションのコマンドライン引数パーサーを構築する。"""
    config = load_config()
    parser = argparse.ArgumentParser(
        prog="price-search",
        description="Claude で商品の価格調査を行います。",
    )
    parser.add_argument("product_name", help="調査したい商品名")
    parser.add_argument(
        "--max-offers",
        type=int,
        default=config.max_offers,
        help="返却する価格候補の最大件数",
    )
    parser.add_argument("--market", default=config.market, help="対象市場コード")
    parser.add_argument("--currency", default=config.currency, help="対象通貨コード")
    parser.add_argument("--json", action="store_true", help="JSON 形式で出力する")
    parser.add_argument(
        "--output-file",
        default=None,
        help="結果 JSON の保存先。未指定時は out/ 配下へ自動保存する",
    )
    return parser


async def run_cli() -> int:
    """CLI 引数を解析し、ユースケースを実行して結果を出力する。"""
    config = load_config()
    parser = build_parser()
    args = parser.parse_args()
    use_case = build_use_case(product_name=args.product_name)
    request = PriceResearchRequest(
        product_name=args.product_name,
        max_offers=args.max_offers,
        market=args.market,
        currency=args.currency,
    )
    response = await use_case.execute(request=request)
    output_file = _resolve_output_file(
        configured_output_dir=config.result_output_dir,
        explicit_output_file=args.output_file,
        product_name=response.product_name,
    )
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(
        json.dumps(asdict(response), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    if args.json:
        print(output_file.read_text(encoding="utf-8"))
        return 0

    product = response.identified_product
    print(f"検索語: {response.product_name}")
    print(f"特定製品: {product.name}")
    if product.model_number:
        print(f"型番: {product.model_number}")
    if product.manufacturer:
        print(f"メーカー: {product.manufacturer}")
    if product.release_date:
        print(f"発売日: {product.release_date}")
    if product.is_substitute:
        print(f"代替理由: {product.substitution_reason}")
    print(f"結果JSON: {output_file}")
    print("")
    print(response.summary)
    print("")
    for index, offer in enumerate(response.offers, start=1):
        print(f"[{index}] {offer.merchant_name}")
        print(f"  商品名: {offer.merchant_product_name}")
        print(f"  価格: {offer.item_price} {offer.currency}")
        print(f"  在庫: {offer.availability}")
        print(f"  URL: {offer.merchant_product_url}")
        print(f"  根拠: {offer.evidence}")
        print("")
    return 0


def main() -> None:
    """非同期 CLI エントリポイントを実行する。"""
    raise SystemExit(asyncio.run(run_cli()))


def _resolve_output_file(
    *,
    configured_output_dir: str,
    explicit_output_file: str | None,
    product_name: str,
) -> Path:
    """結果 JSON の出力パスを解決する。"""
    if explicit_output_file:
        return Path(explicit_output_file).resolve()
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    slug = _slugify_product_name(product_name=product_name)
    return (Path(configured_output_dir) / f"{timestamp}-{slug}.json").resolve()


def _slugify_product_name(*, product_name: str) -> str:
    """商品名からファイルシステム安全なスラッグを生成する。"""
    normalized = re.sub(r"[^0-9A-Za-z_-]+", "-", product_name)
    normalized = normalized.strip("-").lower()
    return normalized or "price-search-result"


if __name__ == "__main__":
    main()
