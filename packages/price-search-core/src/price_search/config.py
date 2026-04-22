"""Application layer: 価格調査エージェントのランタイム設定。"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Literal

from price_search.config_file import load_file_config

ClaudeProvider = Literal["bedrock", "anthropic", "subscription", "openrouter"]
SearchProvider = Literal["searxng", "brave"]

# --- Claude provider / モデル設定 ---
DEFAULT_CLAUDE_PROVIDER: ClaudeProvider = "bedrock"
DEFAULT_AWS_REGION = "ap-northeast-1"
DEFAULT_AWS_PROFILE = "default"
DEFAULT_BEDROCK_PRIMARY_MODEL = "global.anthropic.claude-sonnet-4-6"
DEFAULT_BEDROCK_SMALL_MODEL = "global.anthropic.claude-haiku-4-5-20251001-v1:0"
DEFAULT_ANTHROPIC_PRIMARY_MODEL = "claude-sonnet-4-6"
DEFAULT_ANTHROPIC_SMALL_MODEL = "claude-haiku-4-5"
DEFAULT_OPENROUTER_PRIMARY_MODEL = "anthropic/claude-sonnet-4.6"
DEFAULT_OPENROUTER_SMALL_MODEL = "anthropic/claude-haiku-4.5"
DEFAULT_AGENT_THINKING_TYPE = "enabled"
DEFAULT_AGENT_THINKING_BUDGET_TOKENS = 4096
DEFAULT_AGENT_EFFORT = "high"

# --- エージェント動作設定 ---
DEFAULT_MAX_TURNS = 999
DEFAULT_MAX_OFFERS = 3
DEFAULT_MARKET = "JP"
DEFAULT_CURRENCY = "JPY"

# --- 出力先 ---
DEFAULT_AGENT_ACTIVITY_LOG_DIR = "logs"
DEFAULT_RESULT_OUTPUT_DIR = "out"

# --- 検索プロバイダ設定 ---
DEFAULT_SEARCH_PROVIDER: SearchProvider = "searxng"
DEFAULT_SEARXNG_SEARCH_URL = "http://127.0.0.1:18888/search"
DEFAULT_SEARXNG_ENGINES = "brave,google,duckduckgo"
DEFAULT_SEARXNG_LANGUAGE = "ja-JP"
DEFAULT_SEARXNG_RESULT_LIMIT = 8
DEFAULT_BRAVE_ENDPOINT = "https://api.search.brave.com/res/v1/web/search"
DEFAULT_BRAVE_COUNTRY = "JP"
DEFAULT_BRAVE_SEARCH_LANG = "jp"
DEFAULT_BRAVE_UI_LANG = "ja-JP"
DEFAULT_BRAVE_RESULT_FILTER = "web"
DEFAULT_BRAVE_EXTRA_SNIPPETS = False

# --- ワークスペース ---
DEFAULT_WORKSPACE_ROOT = "."

@dataclass(frozen=True)
class AppConfig:
    """ファイル設定と環境変数から正規化した型付きランタイム設定。"""

    claude_provider: ClaudeProvider
    aws_region: str
    aws_profile: str
    anthropic_api_key: str | None
    openrouter_api_key: str | None
    primary_model: str
    small_model: str
    primary_model_capabilities: str | None
    small_model_capabilities: str | None
    agent_thinking_type: Literal["enabled", "adaptive", "disabled"]
    agent_thinking_budget_tokens: int
    agent_effort: Literal["low", "medium", "high", "max"]
    max_turns: int
    max_offers: int
    market: str
    currency: str
    agent_activity_log_dir: str
    result_output_dir: str
    searxng_search_url: str
    searxng_engines: tuple[str, ...]
    searxng_language: str
    searxng_result_limit: int
    workspace_root: str
    search_provider: SearchProvider = DEFAULT_SEARCH_PROVIDER
    brave_endpoint: str = DEFAULT_BRAVE_ENDPOINT
    brave_api_key: str | None = None
    brave_country: str = DEFAULT_BRAVE_COUNTRY
    brave_search_lang: str = DEFAULT_BRAVE_SEARCH_LANG
    brave_ui_lang: str = DEFAULT_BRAVE_UI_LANG
    brave_result_filter: tuple[str, ...] = (DEFAULT_BRAVE_RESULT_FILTER,)
    brave_extra_snippets: bool = DEFAULT_BRAVE_EXTRA_SNIPPETS


def load_config() -> AppConfig:
    """設定ファイルと環境変数からランタイム設定を読み込む。"""
    file_config = load_file_config()
    provider = _parse_claude_provider(
        _resolve_str(
            env_name="PRICE_SEARCH_CLAUDE_PROVIDER",
            file_value=file_config.claude.provider,
            default=DEFAULT_CLAUDE_PROVIDER,
        )
    )
    primary_model_default, small_model_default = _default_models_for_provider(
        claude_provider=provider
    )
    return AppConfig(
        claude_provider=provider,
        aws_region=_resolve_str(
            env_name="PRICE_SEARCH_AWS_REGION",
            file_value=file_config.aws.region,
            default=DEFAULT_AWS_REGION,
        ),
        aws_profile=_resolve_str(
            env_name="PRICE_SEARCH_AWS_PROFILE",
            file_value=file_config.aws.profile,
            default=DEFAULT_AWS_PROFILE,
        ),
        anthropic_api_key=_resolve_optional_str(
            env_name="ANTHROPIC_API_KEY",
            file_value=file_config.claude.anthropic_api_key,
        ),
        openrouter_api_key=_resolve_optional_str(
            env_name="OPENROUTER_API_KEY",
            file_value=file_config.claude.openrouter_api_key,
        ),
        primary_model=_resolve_str(
            env_name="PRICE_SEARCH_MODEL",
            file_value=file_config.claude.primary_model,
            default=primary_model_default,
        ),
        small_model=_resolve_str(
            env_name="PRICE_SEARCH_SMALL_MODEL",
            file_value=file_config.claude.small_model,
            default=small_model_default,
        ),
        primary_model_capabilities=_resolve_optional_str(
            env_name="PRICE_SEARCH_PRIMARY_MODEL_CAPABILITIES",
            file_value=file_config.claude.primary_model_capabilities,
        ),
        small_model_capabilities=_resolve_optional_str(
            env_name="PRICE_SEARCH_SMALL_MODEL_CAPABILITIES",
            file_value=file_config.claude.small_model_capabilities,
        ),
        agent_thinking_type=_parse_thinking_type(
            _resolve_str(
                env_name="PRICE_SEARCH_AGENT_THINKING_TYPE",
                file_value=file_config.agent.thinking_type,
                default=DEFAULT_AGENT_THINKING_TYPE,
            )
        ),
        agent_thinking_budget_tokens=_resolve_int(
            env_name="PRICE_SEARCH_AGENT_THINKING_BUDGET_TOKENS",
            file_value=file_config.agent.thinking_budget_tokens,
            default=DEFAULT_AGENT_THINKING_BUDGET_TOKENS,
        ),
        agent_effort=_parse_effort(
            _resolve_str(
                env_name="PRICE_SEARCH_AGENT_EFFORT",
                file_value=file_config.agent.effort,
                default=DEFAULT_AGENT_EFFORT,
            )
        ),
        max_turns=_resolve_int(
            env_name="PRICE_SEARCH_MAX_TURNS",
            file_value=file_config.agent.max_turns,
            default=DEFAULT_MAX_TURNS,
        ),
        max_offers=_resolve_int(
            env_name="PRICE_SEARCH_MAX_OFFERS",
            file_value=file_config.agent.max_offers,
            default=DEFAULT_MAX_OFFERS,
        ),
        market=_resolve_str(
            env_name="PRICE_SEARCH_MARKET",
            file_value=file_config.market.code,
            default=DEFAULT_MARKET,
        ),
        currency=_resolve_str(
            env_name="PRICE_SEARCH_CURRENCY",
            file_value=file_config.market.currency,
            default=DEFAULT_CURRENCY,
        ),
        agent_activity_log_dir=_resolve_str(
            env_name="PRICE_SEARCH_AGENT_LOG_DIR",
            file_value=file_config.output.agent_activity_log_dir,
            default=DEFAULT_AGENT_ACTIVITY_LOG_DIR,
        ),
        result_output_dir=_resolve_str(
            env_name="PRICE_SEARCH_RESULT_OUTPUT_DIR",
            file_value=file_config.output.result_output_dir,
            default=DEFAULT_RESULT_OUTPUT_DIR,
        ),
        search_provider=_parse_search_provider(
            _resolve_str(
                env_name="PRICE_SEARCH_SEARCH_PROVIDER",
                file_value=file_config.discovery.provider,
                default=DEFAULT_SEARCH_PROVIDER,
            )
        ),
        searxng_search_url=_resolve_str(
            env_name="PRICE_SEARCH_SEARXNG_SEARCH_URL",
            file_value=file_config.searxng.search_url,
            default=DEFAULT_SEARXNG_SEARCH_URL,
        ),
        searxng_engines=_resolve_csv_setting(
            env_name="PRICE_SEARCH_SEARXNG_ENGINES",
            file_value=file_config.searxng.engines,
            default=_split_csv(DEFAULT_SEARXNG_ENGINES),
        ),
        searxng_language=_resolve_str(
            env_name="PRICE_SEARCH_SEARXNG_LANGUAGE",
            file_value=file_config.searxng.language,
            default=DEFAULT_SEARXNG_LANGUAGE,
        ),
        searxng_result_limit=_resolve_int(
            env_name="PRICE_SEARCH_SEARXNG_RESULT_LIMIT",
            file_value=file_config.searxng.result_limit,
            default=DEFAULT_SEARXNG_RESULT_LIMIT,
        ),
        workspace_root=_resolve_str(
            env_name="PRICE_SEARCH_WORKSPACE_ROOT",
            file_value=file_config.workspace.root,
            default=DEFAULT_WORKSPACE_ROOT,
        ),
        brave_endpoint=_resolve_str(
            env_name="PRICE_SEARCH_BRAVE_ENDPOINT",
            file_value=file_config.brave.endpoint,
            default=DEFAULT_BRAVE_ENDPOINT,
        ),
        brave_api_key=_resolve_optional_str(
            env_name="BRAVE_API_KEY",
            file_value=file_config.brave.api_key,
        ),
        brave_country=_resolve_str(
            env_name="PRICE_SEARCH_BRAVE_COUNTRY",
            file_value=file_config.brave.country,
            default=DEFAULT_BRAVE_COUNTRY,
        ),
        brave_search_lang=_resolve_str(
            env_name="PRICE_SEARCH_BRAVE_SEARCH_LANG",
            file_value=file_config.brave.search_lang,
            default=DEFAULT_BRAVE_SEARCH_LANG,
        ),
        brave_ui_lang=_resolve_str(
            env_name="PRICE_SEARCH_BRAVE_UI_LANG",
            file_value=file_config.brave.ui_lang,
            default=DEFAULT_BRAVE_UI_LANG,
        ),
        brave_result_filter=_resolve_csv_setting(
            env_name="PRICE_SEARCH_BRAVE_RESULT_FILTER",
            file_value=file_config.brave.result_filter,
            default=_split_csv(DEFAULT_BRAVE_RESULT_FILTER),
        ),
        brave_extra_snippets=_resolve_bool(
            env_name="PRICE_SEARCH_BRAVE_EXTRA_SNIPPETS",
            file_value=file_config.brave.extra_snippets,
            default=DEFAULT_BRAVE_EXTRA_SNIPPETS,
        ),
    )


def _resolve_str(*, env_name: str, file_value: str | None, default: str) -> str:
    """env -> file -> default の順で文字列設定を解決する。"""
    env_value = _optional_env(env_name)
    if env_value is not None:
        return env_value
    if file_value is not None:
        return file_value
    return default


def _resolve_int(*, env_name: str, file_value: int | None, default: int) -> int:
    """env -> file -> default の順で整数設定を解決する。"""
    env_value = _optional_env(env_name)
    if env_value is not None:
        return int(env_value)
    if file_value is not None:
        return file_value
    return default


def _resolve_optional_str(*, env_name: str, file_value: str | None) -> str | None:
    """env -> file の順で任意文字列設定を解決する。"""
    env_value = _optional_env(env_name)
    if env_value is not None:
        return env_value
    return file_value


def _resolve_bool(*, env_name: str, file_value: bool | None, default: bool) -> bool:
    """env -> file -> default の順で真偽値設定を解決する。"""
    env_value = _optional_env(env_name)
    if env_value is not None:
        return _parse_bool(env_value)
    if file_value is not None:
        return file_value
    return default


def _resolve_csv_setting(
    *,
    env_name: str,
    file_value: tuple[str, ...] | None,
    default: tuple[str, ...],
) -> tuple[str, ...]:
    """env -> file -> default の順で CSV/配列設定を解決する。"""
    env_value = _optional_env(env_name)
    if env_value is not None:
        return _split_csv(env_value)
    if file_value is not None:
        return file_value
    return default


def _split_csv(value: str) -> tuple[str, ...]:
    """カンマ区切りの文字列をタプルに分割する。"""
    return tuple(item.strip() for item in value.split(",") if item.strip())


def _optional_env(name: str) -> str | None:
    """空文字列を None として扱う環境変数を返す。"""
    value = os.getenv(name)
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None


def _parse_bool(value: str) -> bool:
    """柔軟な真偽値文字列を bool に変換する。"""
    return value.strip().lower() not in {"0", "false", "no", "off"}


def _default_models_for_provider(*, claude_provider: ClaudeProvider) -> tuple[str, str]:
    """Claude provider ごとの既定 primary / fallback model を返す。"""
    if claude_provider == "bedrock":
        return (
            DEFAULT_BEDROCK_PRIMARY_MODEL,
            DEFAULT_BEDROCK_SMALL_MODEL,
        )
    if claude_provider == "openrouter":
        return (
            DEFAULT_OPENROUTER_PRIMARY_MODEL,
            DEFAULT_OPENROUTER_SMALL_MODEL,
        )
    return (
        DEFAULT_ANTHROPIC_PRIMARY_MODEL,
        DEFAULT_ANTHROPIC_SMALL_MODEL,
    )


def _parse_claude_provider(value: str) -> ClaudeProvider:
    """Claude provider 用の値を検証して返す。"""
    normalized = value.strip().lower()
    if normalized not in {"bedrock", "anthropic", "subscription", "openrouter"}:
        raise ValueError(
            "PRICE_SEARCH_CLAUDE_PROVIDER must be one of: bedrock, anthropic, subscription, openrouter"
        )
    return normalized  # type: ignore[return-value]


def _parse_search_provider(value: str) -> SearchProvider:
    """検索プロバイダの値を検証して返す。"""
    normalized = value.strip().lower()
    if normalized not in {"searxng", "brave"}:
        raise ValueError(
            "PRICE_SEARCH_SEARCH_PROVIDER must be one of: searxng, brave"
        )
    return normalized  # type: ignore[return-value]


def _parse_thinking_type(value: str) -> Literal["enabled", "adaptive", "disabled"]:
    """Thinking type 用の値を検証して返す。"""
    normalized = value.strip().lower()
    if normalized not in {"enabled", "adaptive", "disabled"}:
        raise ValueError(
            "PRICE_SEARCH_AGENT_THINKING_TYPE must be one of: enabled, adaptive, disabled"
        )
    return normalized  # type: ignore[return-value]


def _parse_effort(value: str) -> Literal["low", "medium", "high", "max"]:
    """Effort 用の値を検証して返す。"""
    normalized = value.strip().lower()
    if normalized not in {"low", "medium", "high", "max"}:
        raise ValueError("PRICE_SEARCH_AGENT_EFFORT must be one of: low, medium, high, max")
    return normalized  # type: ignore[return-value]
