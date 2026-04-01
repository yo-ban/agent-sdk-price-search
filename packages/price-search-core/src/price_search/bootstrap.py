"""価格調査アプリケーションのコンポジションルート。"""

from __future__ import annotations

from uuid import uuid4

from price_search.adapters.claude_sdk.price_research_agent import (
    ClaudeCodePriceResearchAgent,
)
from price_search.adapters.filesystem.activity_log_path import build_activity_log_path
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
        log_path=build_activity_log_path(
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
