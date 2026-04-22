"""Application support: TOML 設定ファイルの読み込みと検証。"""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

CONFIG_FILE_ENV = "PRICE_SEARCH_CONFIG_FILE"
LOCAL_CONFIG_FILE_ENV = "PRICE_SEARCH_LOCAL_CONFIG_FILE"
DEFAULT_CONFIG_FILE_PATH = "config/price_search.toml"
DEFAULT_LOCAL_CONFIG_FILE_PATH = "config/price_search.local.toml"
CLAUDE_SECRET_KEYS = {"anthropic_api_key", "openrouter_api_key"}
BRAVE_SECRET_KEYS = {"api_key"}


@dataclass(frozen=True)
class ClaudeFileConfig:
    """ファイル上の Claude provider 設定。"""

    provider: str | None = None
    anthropic_api_key: str | None = None
    openrouter_api_key: str | None = None
    primary_model: str | None = None
    small_model: str | None = None
    primary_model_capabilities: str | None = None
    small_model_capabilities: str | None = None


@dataclass(frozen=True)
class AwsFileConfig:
    """ファイル上の AWS 設定。"""

    region: str | None = None
    profile: str | None = None


@dataclass(frozen=True)
class AgentFileConfig:
    """ファイル上のエージェント動作設定。"""

    thinking_type: str | None = None
    thinking_budget_tokens: int | None = None
    effort: str | None = None
    max_turns: int | None = None
    max_offers: int | None = None


@dataclass(frozen=True)
class MarketFileConfig:
    """ファイル上の市場設定。"""

    code: str | None = None
    currency: str | None = None


@dataclass(frozen=True)
class OutputFileConfig:
    """ファイル上の出力設定。"""

    agent_activity_log_dir: str | None = None
    result_output_dir: str | None = None


@dataclass(frozen=True)
class DiscoveryFileConfig:
    """ファイル上の検索プロバイダ設定。"""

    provider: str | None = None


@dataclass(frozen=True)
class SearxngFileConfig:
    """ファイル上の SearXNG 設定。"""

    search_url: str | None = None
    engines: tuple[str, ...] | None = None
    language: str | None = None
    result_limit: int | None = None


@dataclass(frozen=True)
class BraveFileConfig:
    """ファイル上の Brave Web Search 設定。"""

    endpoint: str | None = None
    api_key: str | None = None
    country: str | None = None
    search_lang: str | None = None
    ui_lang: str | None = None
    result_filter: tuple[str, ...] | None = None
    extra_snippets: bool | None = None


@dataclass(frozen=True)
class WorkspaceFileConfig:
    """ファイル上の workspace 設定。"""

    root: str | None = None


@dataclass(frozen=True)
class FileConfig:
    """TOML から読み込んだ型付き設定。"""

    claude: ClaudeFileConfig = field(default_factory=ClaudeFileConfig)
    aws: AwsFileConfig = field(default_factory=AwsFileConfig)
    agent: AgentFileConfig = field(default_factory=AgentFileConfig)
    market: MarketFileConfig = field(default_factory=MarketFileConfig)
    output: OutputFileConfig = field(default_factory=OutputFileConfig)
    discovery: DiscoveryFileConfig = field(default_factory=DiscoveryFileConfig)
    searxng: SearxngFileConfig = field(default_factory=SearxngFileConfig)
    brave: BraveFileConfig = field(default_factory=BraveFileConfig)
    workspace: WorkspaceFileConfig = field(default_factory=WorkspaceFileConfig)


def load_file_config() -> FileConfig:
    """共有 TOML と local TOML を読み込み、deep merge して返す。"""
    shared_path = _config_path_for_env(
        env_name=CONFIG_FILE_ENV,
        default_path=DEFAULT_CONFIG_FILE_PATH,
    )
    local_path = _config_path_for_env(
        env_name=LOCAL_CONFIG_FILE_ENV,
        default_path=DEFAULT_LOCAL_CONFIG_FILE_PATH,
    )
    shared_raw = _load_toml_file(shared_path)
    _validate_no_shared_claude_secrets(raw=shared_raw, path=shared_path)
    merged = _merge_mappings(
        base=shared_raw,
        overrides=_load_toml_file(local_path),
    )
    return _parse_file_config(merged)


def _config_path_for_env(*, env_name: str, default_path: str) -> Path:
    """設定ファイルのパスを環境変数または既定値から解決する。"""
    configured = _optional_env(env_name)
    if configured is None:
        return Path(default_path)
    return Path(configured)


def _load_toml_file(path: Path) -> dict[str, Any]:
    """存在する TOML ファイルを読み込む。存在しなければ空辞書を返す。"""
    if not path.exists():
        return {}
    with path.open("rb") as file:
        loaded = tomllib.load(file)
    if not isinstance(loaded, dict):
        raise ValueError(f"Config file must decode to a table: {path}")
    return loaded


def _merge_mappings(base: dict[str, Any], overrides: dict[str, Any]) -> dict[str, Any]:
    """ネストした辞書を override 優先でマージする。"""
    merged = dict(base)
    for key, override_value in overrides.items():
        base_value = merged.get(key)
        if isinstance(base_value, dict) and isinstance(override_value, dict):
            merged[key] = _merge_mappings(base_value, override_value)
            continue
        merged[key] = override_value
    return merged


def _parse_file_config(raw: dict[str, Any]) -> FileConfig:
    """TOML 辞書を型付き FileConfig に変換する。"""
    allowed_sections = {
        "claude",
        "aws",
        "agent",
        "market",
        "output",
        "discovery",
        "searxng",
        "brave",
        "workspace",
    }
    unknown_sections = set(raw) - allowed_sections
    if unknown_sections:
        raise ValueError(
            f"Unknown config sections: {', '.join(sorted(unknown_sections))}"
        )

    claude_table = _get_table(raw, "claude")
    aws_table = _get_table(raw, "aws")
    agent_table = _get_table(raw, "agent")
    market_table = _get_table(raw, "market")
    output_table = _get_table(raw, "output")
    discovery_table = _get_table(raw, "discovery")
    searxng_table = _get_table(raw, "searxng")
    brave_table = _get_table(raw, "brave")
    workspace_table = _get_table(raw, "workspace")
    _validate_keys(
        claude_table,
        "claude",
        {
            "provider",
            "anthropic_api_key",
            "openrouter_api_key",
            "primary_model",
            "small_model",
            "primary_model_capabilities",
            "small_model_capabilities",
        },
    )
    _validate_keys(aws_table, "aws", {"region", "profile"})
    _validate_keys(
        agent_table,
        "agent",
        {"thinking_type", "thinking_budget_tokens", "effort", "max_turns", "max_offers"},
    )
    _validate_keys(market_table, "market", {"code", "currency"})
    _validate_keys(output_table, "output", {"agent_activity_log_dir", "result_output_dir"})
    _validate_keys(discovery_table, "discovery", {"provider"})
    _validate_keys(
        searxng_table,
        "searxng",
        {"search_url", "engines", "language", "result_limit"},
    )
    _validate_keys(
        brave_table,
        "brave",
        {"endpoint", "api_key", "country", "search_lang", "ui_lang", "result_filter", "extra_snippets"},
    )
    _validate_keys(workspace_table, "workspace", {"root"})

    return FileConfig(
        claude=ClaudeFileConfig(
            provider=_read_optional_str(claude_table, "provider"),
            anthropic_api_key=_read_optional_str(claude_table, "anthropic_api_key"),
            openrouter_api_key=_read_optional_str(claude_table, "openrouter_api_key"),
            primary_model=_read_optional_str(claude_table, "primary_model"),
            small_model=_read_optional_str(claude_table, "small_model"),
            primary_model_capabilities=_read_optional_str(
                claude_table, "primary_model_capabilities"
            ),
            small_model_capabilities=_read_optional_str(
                claude_table, "small_model_capabilities"
            ),
        ),
        aws=AwsFileConfig(
            region=_read_optional_str(aws_table, "region"),
            profile=_read_optional_str(aws_table, "profile"),
        ),
        agent=AgentFileConfig(
            thinking_type=_read_optional_str(agent_table, "thinking_type"),
            thinking_budget_tokens=_read_optional_int(agent_table, "thinking_budget_tokens"),
            effort=_read_optional_str(agent_table, "effort"),
            max_turns=_read_optional_int(agent_table, "max_turns"),
            max_offers=_read_optional_int(agent_table, "max_offers"),
        ),
        market=MarketFileConfig(
            code=_read_optional_str(market_table, "code"),
            currency=_read_optional_str(market_table, "currency"),
        ),
        output=OutputFileConfig(
            agent_activity_log_dir=_read_optional_str(output_table, "agent_activity_log_dir"),
            result_output_dir=_read_optional_str(output_table, "result_output_dir"),
        ),
        discovery=DiscoveryFileConfig(
            provider=_read_optional_str(discovery_table, "provider"),
        ),
        searxng=SearxngFileConfig(
            search_url=_read_optional_str(searxng_table, "search_url"),
            engines=_read_optional_str_tuple(searxng_table, "engines"),
            language=_read_optional_str(searxng_table, "language"),
            result_limit=_read_optional_int(searxng_table, "result_limit"),
        ),
        brave=BraveFileConfig(
            endpoint=_read_optional_str(brave_table, "endpoint"),
            api_key=_read_optional_str(brave_table, "api_key"),
            country=_read_optional_str(brave_table, "country"),
            search_lang=_read_optional_str(brave_table, "search_lang"),
            ui_lang=_read_optional_str(brave_table, "ui_lang"),
            result_filter=_read_optional_str_tuple(brave_table, "result_filter"),
            extra_snippets=_read_optional_bool(brave_table, "extra_snippets"),
        ),
        workspace=WorkspaceFileConfig(
            root=_read_optional_str(workspace_table, "root"),
        ),
    )


def _get_table(raw: dict[str, Any], section: str) -> dict[str, Any]:
    """指定 section が table なら返し、無ければ空辞書を返す。"""
    value = raw.get(section)
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ValueError(f"Config section '{section}' must be a table")
    return value


def _validate_keys(raw: dict[str, Any], section: str, allowed_keys: set[str]) -> None:
    """各 section の未知キーを検出する。"""
    unknown_keys = set(raw) - allowed_keys
    if unknown_keys:
        raise ValueError(
            f"Unknown keys in [{section}]: {', '.join(sorted(unknown_keys))}"
        )


def _validate_no_shared_claude_secrets(*, raw: dict[str, Any], path: Path) -> None:
    """shared config に認証 secret を置かない契約を検証する。"""
    claude_table = _get_table(raw, "claude")
    shared_secret_keys = sorted(set(claude_table) & CLAUDE_SECRET_KEYS)
    if shared_secret_keys:
        raise ValueError(
            "Shared config must not include Claude API secrets in [claude]: "
            f"{', '.join(shared_secret_keys)} ({path})"
        )
    brave_table = _get_table(raw, "brave")
    brave_secret_keys = sorted(set(brave_table) & BRAVE_SECRET_KEYS)
    if brave_secret_keys:
        raise ValueError(
            "Shared config must not include Brave API secrets in [brave]: "
            f"{', '.join(brave_secret_keys)} ({path})"
        )


def _read_optional_str(raw: dict[str, Any], key: str) -> str | None:
    """TOML table から任意文字列を読む。"""
    value = raw.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(f"Config key '{key}' must be a string")
    normalized = value.strip()
    return normalized or None


def _read_optional_int(raw: dict[str, Any], key: str) -> int | None:
    """TOML table から任意整数を読む。"""
    value = raw.get(key)
    if value is None:
        return None
    if not isinstance(value, int):
        raise ValueError(f"Config key '{key}' must be an integer")
    return value


def _read_optional_bool(raw: dict[str, Any], key: str) -> bool | None:
    """TOML table から任意真偽値を読む。"""
    value = raw.get(key)
    if value is None:
        return None
    if not isinstance(value, bool):
        raise ValueError(f"Config key '{key}' must be a boolean")
    return value


def _read_optional_str_tuple(raw: dict[str, Any], key: str) -> tuple[str, ...] | None:
    """TOML table から文字列配列または CSV 文字列を読む。"""
    value = raw.get(key)
    if value is None:
        return None
    if isinstance(value, str):
        return _split_csv(value)
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ValueError(f"Config key '{key}' must be an array of strings or CSV string")
    return tuple(item.strip() for item in value if item.strip())


def _optional_env(name: str) -> str | None:
    """空文字列を None として扱う環境変数を返す。"""
    value = os.getenv(name)
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None


def _split_csv(value: str) -> tuple[str, ...]:
    """カンマ区切りの文字列をタプルに分割する。"""
    return tuple(item.strip() for item in value.split(",") if item.strip())
