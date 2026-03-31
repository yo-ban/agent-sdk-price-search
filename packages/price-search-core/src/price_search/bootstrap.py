"""価格調査アプリケーションのコンポジションルート。"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from price_search.adapters.claude_sdk.price_research_agent import (
    ClaudeCodePriceResearchAgent,
)
from price_search.adapters.filesystem.jsonl_agent_activity_logger import (
    JsonlAgentActivityLogger,
)
from price_search.application.run_price_research import RunPriceResearchUseCase
from price_search.config import load_config


def build_use_case(*, product_name: str) -> RunPriceResearchUseCase:
    """具象アダプターを組み立ててアプリケーションサービスを返す。"""
    config = load_config()
    run_id = uuid4().hex
    activity_logger = JsonlAgentActivityLogger(
        log_path=_resolve_activity_log_path(
            configured_log_dir=config.agent_activity_log_dir,
            product_name=product_name,
            run_id=run_id,
        ),
        run_id=run_id,
    )
    agent_adapter = ClaudeCodePriceResearchAgent(
        config=config,
        activity_logger=activity_logger,
    )
    return RunPriceResearchUseCase(agent_port=agent_adapter)


def _resolve_activity_log_path(
    *,
    configured_log_dir: str,
    product_name: str,
    run_id: str,
    now: datetime | None = None,
) -> Path:
    """実行ごとの JSONL ログファイルパスを設定ディレクトリ配下に生成する。"""
    timestamp = (now or datetime.now(UTC)).strftime("%Y%m%dT%H%M%SZ")
    slug = _slugify_product_name(product_name=product_name)
    configured_path = Path(configured_log_dir)

    if configured_path.suffix:
        log_dir = configured_path.parent
        file_prefix = configured_path.stem
        suffix = configured_path.suffix
    else:
        log_dir = configured_path
        file_prefix = "price_search_agent_activity"
        suffix = ".jsonl"

    filename = f"{file_prefix}-{timestamp}-{slug}-{run_id[:8]}{suffix}"
    return (log_dir / filename).resolve()


def _slugify_product_name(*, product_name: str) -> str:
    """商品名からファイルシステム安全なスラッグを生成する。"""
    normalized = re.sub(r"[^0-9A-Za-z_-]+", "-", product_name)
    normalized = normalized.strip("-").lower()
    return normalized or "price-search-run"
