"""Command-line handler for the provider-backed web discovery tool."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict

from web_search_cli.adapters.search_adapter_factory import build_search_adapter
from web_search_cli.config import AppConfig, load_config
from web_search_cli.contracts.request import WebSearchRequest


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI argument parser for the discovery command."""
    config = load_config()
    parser = argparse.ArgumentParser(
        prog="web-search",
        description="商品 discovery 用の Web 検索を実行します。",
    )
    parser.add_argument("query", help="検索クエリ")
    parser.add_argument(
        "--limit",
        type=int,
        default=config.searxng_result_limit,
        help="返却する検索候補の最大件数",
    )
    parser.add_argument(
        "--language",
        default=_default_query_language(config),
        help="検索プロバイダに渡す言語ヒント",
    )
    parser.add_argument(
        "--engine",
        action="append",
        dest="engines",
        default=None,
        help="利用する SearXNG engine。複数指定可。Brave では無視されます。",
    )
    parser.add_argument(
        "--include-domain",
        action="append",
        dest="include_domains",
        default=None,
        help="対象をこのドメイン群に限定します。複数指定可。",
    )
    parser.add_argument(
        "--exclude-domain",
        action="append",
        dest="exclude_domains",
        default=None,
        help="除外したいドメイン。複数指定可。",
    )
    return parser


def run_cli() -> int:
    """Parse CLI arguments and print the normalized JSON response."""
    config = load_config()
    args = build_parser().parse_args()
    search_adapter = build_search_adapter(config=config)
    response = search_adapter.search(
        WebSearchRequest(
            query=args.query,
            limit=args.limit,
            language=args.language,
            engines=tuple(args.engines or config.searxng_engines),
            include_domains=tuple(args.include_domains or ()),
            exclude_domains=tuple(args.exclude_domains or ()),
        ),
    )
    print(json.dumps(asdict(response), ensure_ascii=False, indent=2))
    return 0


def _default_query_language(config: AppConfig) -> str:
    """Return the provider-appropriate default request language."""
    if config.search_provider == "brave":
        return config.brave_search_lang
    return config.searxng_language


def main() -> None:
    """Run the synchronous CLI entry point."""
    raise SystemExit(run_cli())


if __name__ == "__main__":
    main()
