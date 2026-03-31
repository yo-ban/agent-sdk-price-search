"""隔離 workspace launcher の CLI ハンドラー。"""

from __future__ import annotations

import argparse
from pathlib import Path

from price_search_launcher.bootstrap import build_use_case
from price_search_launcher.contracts.isolated_price_search_request import (
    IsolatedPriceSearchRequest,
)


def build_parser() -> argparse.ArgumentParser:
    """launcher 用の引数パーサーを構築する。"""
    parser = argparse.ArgumentParser(
        prog="price-search-run",
        description="隔離 workspace で price-search を起動します。",
    )
    parser.add_argument("product_name", help="調査したい商品名")
    parser.add_argument(
        "price_search_args",
        nargs=argparse.REMAINDER,
        help="`--` 以降は price-search CLI へそのまま渡す",
    )
    return parser


def run_cli() -> int:
    """launcher request を作り、use case を呼ぶ。"""
    parser = build_parser()
    args = parser.parse_args()
    forwarded_args = tuple(_normalize_forwarded_args(args))
    use_case = build_use_case()
    return use_case.execute(
        IsolatedPriceSearchRequest(
            cli_args=(args.product_name, *forwarded_args),
            launch_directory=Path.cwd(),
        )
    )


def main() -> None:
    """同期 launcher エントリポイント。"""
    raise SystemExit(run_cli())


def _normalize_forwarded_args(args: argparse.Namespace) -> tuple[str, ...]:
    """argparse の remainder 先頭に入る `--` を取り除く。"""
    raw_args = tuple(args.price_search_args)
    if raw_args[:1] == ("--",):
        return raw_args[1:]
    return raw_args


if __name__ == "__main__":
    main()
