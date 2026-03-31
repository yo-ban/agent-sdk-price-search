"""Command-line handler for the self-hosted SearXNG discovery tool."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict

from searxng_search_cli.adapters.self_hosted_search import SelfHostedSearxngSearchAdapter
from searxng_search_cli.application.run_search import RunSearxngSearchUseCase
from searxng_search_cli.config import load_config
from searxng_search_cli.contracts.request import SearxngSearchRequest


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI argument parser for the discovery command."""
    config = load_config()
    parser = argparse.ArgumentParser(
        prog="searxng-search",
        description="Self-hosted SearXNG で商品 discovery 検索を実行します。",
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
        default=config.searxng_language,
        help="SearXNG に渡す言語ヒント",
    )
    parser.add_argument(
        "--engine",
        action="append",
        dest="engines",
        default=None,
        help="利用する SearXNG engine。複数指定可。",
    )
    parser.add_argument(
        "--include-domain",
        action="append",
        dest="include_domains",
        default=None,
        help="優先したいドメイン。複数指定可。",
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
    use_case = RunSearxngSearchUseCase(
        search_port=SelfHostedSearxngSearchAdapter(config=config),
    )
    response = use_case.execute(
        request=SearxngSearchRequest(
            query=args.query,
            limit=args.limit,
            language=args.language,
            engines=tuple(args.engines or config.searxng_engines),
            include_domains=tuple(args.include_domains or ()),
            exclude_domains=tuple(args.exclude_domains or ()),
        )
    )
    print(json.dumps(asdict(response), ensure_ascii=False, indent=2))
    return 0


def main() -> None:
    """Run the synchronous CLI entry point."""
    raise SystemExit(run_cli())


if __name__ == "__main__":
    main()
