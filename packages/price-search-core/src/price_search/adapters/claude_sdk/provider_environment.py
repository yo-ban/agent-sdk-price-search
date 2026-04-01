"""Infrastructure layer: Claude Code 実行環境の provider 別設定。"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

from price_search.config import AppConfig

_PROVIDER_RESET_ENV_NAMES = (
    "ANTHROPIC_API_KEY",
    "ANTHROPIC_AUTH_TOKEN",
    "ANTHROPIC_BASE_URL",
    "ANTHROPIC_DEFAULT_SONNET_MODEL_SUPPORTED_CAPABILITIES",
    "ANTHROPIC_DEFAULT_HAIKU_MODEL_SUPPORTED_CAPABILITIES",
    "CLAUDE_CODE_USE_AZURE",
    "CLAUDE_CODE_USE_BEDROCK",
    "CLAUDE_CODE_USE_VERTEX",
    "OPENROUTER_API_KEY",
)


def build_claude_code_env(*, config: AppConfig) -> dict[str, str]:
    """Claude Code CLI に渡す環境変数を provider 非依存で組み立てる。"""
    workspace_root = Path(config.workspace_root).resolve()
    workspace_bin = workspace_root / "bin"
    current_path = os.getenv("PATH", "")
    path_value = str(workspace_bin)
    if current_path:
        path_value = f"{path_value}:{current_path}"

    shared_env = {
        "CLAUDE_CODE_DISABLE_AUTO_MEMORY": "1",
        "ANTHROPIC_MODEL": config.primary_model,
        "ANTHROPIC_DEFAULT_SONNET_MODEL": config.primary_model,
        "ANTHROPIC_DEFAULT_HAIKU_MODEL": config.small_model,
        "PATH": path_value,
        "PRICE_SEARCH_CLAUDE_REAL_CLI_PATH": _discover_claude_cli_path(),
        "PRICE_SEARCH_CLAUDE_UNSET_ENV": ",".join(_provider_reset_env_names(config=config)),
        "PRICE_SEARCH_SEARXNG_SEARCH_URL": config.searxng_search_url,
        "PRICE_SEARCH_SEARXNG_ENGINES": ",".join(config.searxng_engines),
        "PRICE_SEARCH_SEARXNG_LANGUAGE": config.searxng_language,
        "PRICE_SEARCH_SEARXNG_RESULT_LIMIT": str(config.searxng_result_limit),
        "PRICE_SEARCH_WORKSPACE_ROOT": str(workspace_root),
    }
    return {
        **shared_env,
        **_provider_specific_env(config=config),
    }


def _provider_reset_env_names(*, config: AppConfig) -> tuple[str, ...]:
    """選択 provider に不要な認証・切替 env 名を返す。"""
    bedrock_capability_resets = _bedrock_capability_reset_env_names(config=config)
    if config.claude_provider == "bedrock":
        return (
            "ANTHROPIC_API_KEY",
            "ANTHROPIC_AUTH_TOKEN",
            "ANTHROPIC_BASE_URL",
            "CLAUDE_CODE_USE_AZURE",
            "CLAUDE_CODE_USE_VERTEX",
            "OPENROUTER_API_KEY",
            *bedrock_capability_resets,
        )
    if config.claude_provider == "anthropic":
        return (
            "ANTHROPIC_AUTH_TOKEN",
            "ANTHROPIC_BASE_URL",
            "ANTHROPIC_DEFAULT_SONNET_MODEL_SUPPORTED_CAPABILITIES",
            "ANTHROPIC_DEFAULT_HAIKU_MODEL_SUPPORTED_CAPABILITIES",
            "CLAUDE_CODE_USE_AZURE",
            "CLAUDE_CODE_USE_BEDROCK",
            "CLAUDE_CODE_USE_VERTEX",
            "OPENROUTER_API_KEY",
        )
    if config.claude_provider == "openrouter":
        return (
            "ANTHROPIC_API_KEY",
            "ANTHROPIC_DEFAULT_SONNET_MODEL_SUPPORTED_CAPABILITIES",
            "ANTHROPIC_DEFAULT_HAIKU_MODEL_SUPPORTED_CAPABILITIES",
            "CLAUDE_CODE_USE_AZURE",
            "CLAUDE_CODE_USE_BEDROCK",
            "CLAUDE_CODE_USE_VERTEX",
        )
    return _PROVIDER_RESET_ENV_NAMES


def _bedrock_capability_reset_env_names(*, config: AppConfig) -> tuple[str, ...]:
    """Bedrock で明示設定されていない capability env 名だけを返す。"""
    env_names: list[str] = []
    if config.primary_model_capabilities is None:
        env_names.append("ANTHROPIC_DEFAULT_SONNET_MODEL_SUPPORTED_CAPABILITIES")
    if config.small_model_capabilities is None:
        env_names.append("ANTHROPIC_DEFAULT_HAIKU_MODEL_SUPPORTED_CAPABILITIES")
    return tuple(env_names)


def _discover_claude_cli_path() -> str:
    """Claude Code CLI 実体の代表的な探索結果を返す。"""
    if cli_path := shutil.which("claude"):
        return cli_path

    candidate_paths = (
        Path.home() / ".npm-global/bin/claude",
        Path("/usr/local/bin/claude"),
        Path.home() / ".local/bin/claude",
        Path.home() / "node_modules/.bin/claude",
        Path.home() / ".yarn/bin/claude",
        Path.home() / ".claude/local/claude",
    )
    for candidate_path in candidate_paths:
        if candidate_path.exists() and candidate_path.is_file():
            return str(candidate_path)
    return "claude"


def _provider_specific_env(*, config: AppConfig) -> dict[str, str]:
    """選択された Claude provider に必要な認証系環境変数だけを返す。"""
    if config.claude_provider == "bedrock":
        env = {
            "CLAUDE_CODE_USE_BEDROCK": "1",
            "AWS_REGION": config.aws_region,
            "AWS_PROFILE": config.aws_profile,
        }
        if config.primary_model_capabilities is not None:
            env["ANTHROPIC_DEFAULT_SONNET_MODEL_SUPPORTED_CAPABILITIES"] = (
                config.primary_model_capabilities
            )
        if config.small_model_capabilities is not None:
            env["ANTHROPIC_DEFAULT_HAIKU_MODEL_SUPPORTED_CAPABILITIES"] = (
                config.small_model_capabilities
            )
        return env
    if config.claude_provider == "anthropic":
        if config.anthropic_api_key is None:
            raise ValueError(
                "ANTHROPIC_API_KEY must be set when PRICE_SEARCH_CLAUDE_PROVIDER=anthropic"
            )
        return {
            "ANTHROPIC_API_KEY": config.anthropic_api_key,
        }
    if config.claude_provider == "openrouter":
        if config.openrouter_api_key is None:
            raise ValueError(
                "OPENROUTER_API_KEY must be set when PRICE_SEARCH_CLAUDE_PROVIDER=openrouter"
            )
        return {
            "OPENROUTER_API_KEY": config.openrouter_api_key,
            "ANTHROPIC_BASE_URL": "https://openrouter.ai/api",
            "ANTHROPIC_AUTH_TOKEN": config.openrouter_api_key,
        }
    return {}
