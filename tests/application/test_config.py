"""Tests for runtime configuration precedence."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import price_search.config as runtime_config
import price_search.config_file as config_file_module
import pytest
from price_search.config import load_config
from price_search.config_file import (
    AgentFileConfig,
    BraveFileConfig,
    ClaudeFileConfig,
    DiscoveryFileConfig,
    FileConfig,
)


@dataclass(frozen=True)
class ConfigExpectation:
    """Projection of the runtime settings that these tests care about."""

    claude_provider: str
    primary_model: str
    small_model: str
    primary_model_capabilities: str | None
    small_model_capabilities: str | None
    max_turns: int
    max_offers: int


def test_load_config_uses_file_config_when_env_is_absent(monkeypatch) -> None:
    """File-backed values should surface through the public runtime config loader."""
    file_config = _build_file_config(
        claude_provider="subscription",
        primary_model="claude-sonnet-4-6",
        small_model="claude-haiku-4-5",
        primary_model_capabilities="tool-use,reasoning",
        small_model_capabilities="tool-use",
        max_turns=12,
        max_offers=2,
    )
    monkeypatch.setattr(runtime_config, "load_file_config", lambda: file_config)
    _clear_runtime_env(monkeypatch=monkeypatch)

    config = load_config()

    assert _runtime_projection(config) == _expected_projection(
        claude_provider=file_config.claude.provider,
        primary_model=file_config.claude.primary_model,
        small_model=file_config.claude.small_model,
        primary_model_capabilities=file_config.claude.primary_model_capabilities,
        small_model_capabilities=file_config.claude.small_model_capabilities,
        max_turns=file_config.agent.max_turns,
        max_offers=file_config.agent.max_offers,
    )


def test_load_file_config_prefers_local_values_over_shared_values(monkeypatch) -> None:
    """Local file values should override shared file values in the public file loader."""
    shared_path = Path("shared-config")
    local_path = Path("local-config")
    shared_raw = {
        "claude": {
            "provider": "bedrock",
            "primary_model": "global.anthropic.claude-sonnet-4-6",
            "small_model": "global.anthropic.claude-haiku-4-5-20251001-v1:0",
            "primary_model_capabilities": "tool-use,reasoning",
        }
    }
    local_raw = {
        "claude": {
            "provider": "anthropic",
            "primary_model": "claude-sonnet-4-6",
            "small_model": "claude-haiku-4-5",
            "small_model_capabilities": "tool-use",
        }
    }
    monkeypatch.setattr(
        config_file_module,
        "_config_path_for_env",
        lambda *, env_name, default_path: (
            shared_path if env_name == config_file_module.CONFIG_FILE_ENV else local_path
        ),
    )
    monkeypatch.setattr(
        config_file_module,
        "_load_toml_file",
        lambda path: shared_raw if path == shared_path else local_raw,
    )

    file_config = config_file_module.load_file_config()

    assert _file_projection(file_config) == _expected_projection(
        claude_provider=local_raw["claude"]["provider"],
        primary_model=local_raw["claude"]["primary_model"],
        small_model=local_raw["claude"]["small_model"],
        primary_model_capabilities=shared_raw["claude"]["primary_model_capabilities"],
        small_model_capabilities=local_raw["claude"]["small_model_capabilities"],
    )


def test_load_file_config_reads_local_provider_api_keys(monkeypatch) -> None:
    """Local file should surface provider API keys through the public file loader."""
    shared_path = Path("shared-config")
    local_path = Path("local-config")
    shared_raw = {
        "claude": {
            "provider": "anthropic",
        }
    }
    local_raw = {
        "claude": {
            "anthropic_api_key": "local-token",
            "openrouter_api_key": "local-openrouter-token",
        }
    }
    monkeypatch.setattr(
        config_file_module,
        "_config_path_for_env",
        lambda *, env_name, default_path: (
            shared_path if env_name == config_file_module.CONFIG_FILE_ENV else local_path
        ),
    )
    monkeypatch.setattr(
        config_file_module,
        "_load_toml_file",
        lambda path: shared_raw if path == shared_path else local_raw,
    )

    file_config = config_file_module.load_file_config()

    assert file_config.claude.anthropic_api_key == local_raw["claude"]["anthropic_api_key"]
    assert (
        file_config.claude.openrouter_api_key
        == local_raw["claude"]["openrouter_api_key"]
    )


def test_load_file_config_rejects_provider_api_keys_in_shared_file(monkeypatch) -> None:
    """Shared config should reject Claude API secrets under the public file loader."""
    shared_path = Path("shared-config")
    local_path = Path("local-config")
    shared_raw = {
        "claude": {
            "anthropic_api_key": "shared-token",
        }
    }
    monkeypatch.setattr(
        config_file_module,
        "_config_path_for_env",
        lambda *, env_name, default_path: (
            shared_path if env_name == config_file_module.CONFIG_FILE_ENV else local_path
        ),
    )
    monkeypatch.setattr(
        config_file_module,
        "_load_toml_file",
        lambda path: shared_raw if path == shared_path else {},
    )

    with pytest.raises(ValueError, match="Shared config must not include Claude API secrets"):
        config_file_module.load_file_config()


def test_load_config_prefers_environment_over_file_config(monkeypatch) -> None:
    """Environment variables should override file-backed values in the public loader."""
    file_config = _build_file_config(
        claude_provider="subscription",
        primary_model="claude-sonnet-4-6",
        small_model="claude-haiku-4-5",
    )
    env_values = {
        "PRICE_SEARCH_CLAUDE_PROVIDER": "bedrock",
        "PRICE_SEARCH_MODEL": "global.anthropic.claude-sonnet-4-6",
        "PRICE_SEARCH_SMALL_MODEL": "global.anthropic.claude-haiku-4-5-20251001-v1:0",
        "PRICE_SEARCH_PRIMARY_MODEL_CAPABILITIES": "tool-use,reasoning",
    }
    monkeypatch.setattr(runtime_config, "load_file_config", lambda: file_config)
    _clear_runtime_env(monkeypatch=monkeypatch)
    for env_name, env_value in env_values.items():
        monkeypatch.setenv(env_name, env_value)

    config = load_config()

    assert _runtime_projection(config) == _expected_projection(
        claude_provider=env_values["PRICE_SEARCH_CLAUDE_PROVIDER"],
        primary_model=env_values["PRICE_SEARCH_MODEL"],
        small_model=env_values["PRICE_SEARCH_SMALL_MODEL"],
        primary_model_capabilities=env_values["PRICE_SEARCH_PRIMARY_MODEL_CAPABILITIES"],
        small_model_capabilities=file_config.claude.small_model_capabilities,
        max_turns=file_config.agent.max_turns,
        max_offers=file_config.agent.max_offers,
    )


def test_load_config_uses_openrouter_default_models(monkeypatch) -> None:
    """OpenRouter provider should select OpenRouter-flavored default model IDs."""
    file_config = _build_file_config(
        claude_provider="openrouter",
        primary_model=None,
        small_model=None,
    )
    monkeypatch.setattr(runtime_config, "load_file_config", lambda: file_config)
    _clear_runtime_env(monkeypatch=monkeypatch)

    config = load_config()

    assert config.claude_provider == file_config.claude.provider
    assert config.primary_model
    assert "/" in config.primary_model
    assert config.small_model
    assert "/" in config.small_model
    assert config.max_turns == file_config.agent.max_turns
    assert config.max_offers == file_config.agent.max_offers


def test_load_config_uses_local_anthropic_api_key_when_env_is_absent(
    monkeypatch,
) -> None:
    """Anthropic API key should come from local/shared file when env is absent."""
    file_config = _build_file_config(
        claude_provider="anthropic",
        anthropic_api_key="local-anthropic-token",
        primary_model="claude-sonnet-4-6",
        small_model="claude-haiku-4-5",
    )
    monkeypatch.setattr(runtime_config, "load_file_config", lambda: file_config)
    _clear_runtime_env(monkeypatch=monkeypatch)

    config = load_config()

    assert config.anthropic_api_key == file_config.claude.anthropic_api_key


def test_load_config_prefers_env_openrouter_api_key_over_local_file(monkeypatch) -> None:
    """OpenRouter API key should prefer env over local/shared file content."""
    env_api_key = "env-openrouter-token"
    file_config = _build_file_config(
        claude_provider="openrouter",
        openrouter_api_key="local-openrouter-token",
        primary_model="anthropic/claude-sonnet-4.6",
        small_model="anthropic/claude-haiku-4.5",
    )
    monkeypatch.setattr(runtime_config, "load_file_config", lambda: file_config)
    _clear_runtime_env(monkeypatch=monkeypatch)
    monkeypatch.setenv("OPENROUTER_API_KEY", env_api_key)

    config = load_config()

    assert config.openrouter_api_key == env_api_key


def test_load_config_supports_brave_search_provider_and_settings(monkeypatch) -> None:
    """Brave discovery settings should surface through the public runtime config loader."""
    file_config = _build_file_config(
        claude_provider="subscription",
        primary_model="claude-sonnet-4-6",
        small_model="claude-haiku-4-5",
        discovery_provider="brave",
        brave_endpoint="https://api.search.brave.com/res/v1/web/search",
        brave_api_key="brave-token",
        brave_country="JP",
        brave_search_lang="jp",
        brave_ui_lang="ja-JP",
        brave_result_filter=("web",),
        brave_extra_snippets=True,
    )
    monkeypatch.setattr(runtime_config, "load_file_config", lambda: file_config)
    _clear_runtime_env(monkeypatch=monkeypatch)

    config = load_config()

    assert config.search_provider == "brave"
    assert config.brave_api_key == "brave-token"
    assert config.brave_result_filter == ("web",)
    assert config.brave_extra_snippets is True


def test_load_file_config_rejects_brave_api_key_in_shared_file(monkeypatch) -> None:
    """Shared config should reject Brave API secrets under the public file loader."""
    shared_path = Path("shared-config")
    local_path = Path("local-config")
    shared_raw = {
        "brave": {
            "api_key": "shared-brave-token",
        }
    }
    monkeypatch.setattr(
        config_file_module,
        "_config_path_for_env",
        lambda *, env_name, default_path: (
            shared_path if env_name == config_file_module.CONFIG_FILE_ENV else local_path
        ),
    )
    monkeypatch.setattr(
        config_file_module,
        "_load_toml_file",
        lambda path: shared_raw if path == shared_path else {},
    )

    with pytest.raises(ValueError, match="Shared config must not include Brave API secrets"):
        config_file_module.load_file_config()


def _build_file_config(
    *,
    claude_provider: str,
    anthropic_api_key: str | None = None,
    openrouter_api_key: str | None = None,
    discovery_provider: str | None = None,
    brave_endpoint: str | None = None,
    brave_api_key: str | None = None,
    brave_country: str | None = None,
    brave_search_lang: str | None = None,
    brave_ui_lang: str | None = None,
    brave_result_filter: tuple[str, ...] | None = None,
    brave_extra_snippets: bool | None = None,
    primary_model: str | None,
    small_model: str | None,
    primary_model_capabilities: str | None = None,
    small_model_capabilities: str | None = None,
    max_turns: int = 999,
    max_offers: int = 3,
) -> FileConfig:
    """Create a typed file config fixture without touching the filesystem."""
    return FileConfig(
        claude=ClaudeFileConfig(
            provider=claude_provider,
            anthropic_api_key=anthropic_api_key,
            openrouter_api_key=openrouter_api_key,
            primary_model=primary_model,
            small_model=small_model,
            primary_model_capabilities=primary_model_capabilities,
            small_model_capabilities=small_model_capabilities,
        ),
        agent=AgentFileConfig(
            max_turns=max_turns,
            max_offers=max_offers,
        ),
        discovery=DiscoveryFileConfig(
            provider=discovery_provider,
        ),
        brave=BraveFileConfig(
            endpoint=brave_endpoint,
            api_key=brave_api_key,
            country=brave_country,
            search_lang=brave_search_lang,
            ui_lang=brave_ui_lang,
            result_filter=brave_result_filter,
            extra_snippets=brave_extra_snippets,
        ),
    )


def _runtime_projection(config: runtime_config.AppConfig) -> ConfigExpectation:
    """Reduce runtime config to the behavior under test."""
    return ConfigExpectation(
        claude_provider=config.claude_provider,
        primary_model=config.primary_model,
        small_model=config.small_model,
        primary_model_capabilities=config.primary_model_capabilities,
        small_model_capabilities=config.small_model_capabilities,
        max_turns=config.max_turns,
        max_offers=config.max_offers,
    )


def _file_projection(file_config: FileConfig) -> ConfigExpectation:
    """Reduce file config to the merged values under test."""
    return _expected_projection(
        claude_provider=file_config.claude.provider,
        primary_model=file_config.claude.primary_model,
        small_model=file_config.claude.small_model,
        primary_model_capabilities=file_config.claude.primary_model_capabilities,
        small_model_capabilities=file_config.claude.small_model_capabilities,
        max_turns=file_config.agent.max_turns,
        max_offers=file_config.agent.max_offers,
    )


def _expected_projection(
    *,
    claude_provider: str | None,
    primary_model: str | None,
    small_model: str | None,
    primary_model_capabilities: str | None = None,
    small_model_capabilities: str | None = None,
    max_turns: int | None = runtime_config.DEFAULT_MAX_TURNS,
    max_offers: int | None = runtime_config.DEFAULT_MAX_OFFERS,
) -> ConfigExpectation:
    """Build one comparable expectation object from optional inputs."""
    return ConfigExpectation(
        claude_provider=claude_provider or runtime_config.DEFAULT_CLAUDE_PROVIDER,
        primary_model=primary_model or "",
        small_model=small_model or "",
        primary_model_capabilities=primary_model_capabilities,
        small_model_capabilities=small_model_capabilities,
        max_turns=max_turns if max_turns is not None else runtime_config.DEFAULT_MAX_TURNS,
        max_offers=(
            max_offers if max_offers is not None else runtime_config.DEFAULT_MAX_OFFERS
        ),
    )


def _clear_runtime_env(*, monkeypatch) -> None:
    """Remove runtime env overrides so the targeted source becomes visible."""
    for env_name in (
        "PRICE_SEARCH_CLAUDE_PROVIDER",
        "PRICE_SEARCH_MODEL",
        "PRICE_SEARCH_SMALL_MODEL",
        "PRICE_SEARCH_PRIMARY_MODEL_CAPABILITIES",
        "PRICE_SEARCH_SMALL_MODEL_CAPABILITIES",
        "PRICE_SEARCH_SEARCH_PROVIDER",
        "ANTHROPIC_API_KEY",
        "OPENROUTER_API_KEY",
        "BRAVE_API_KEY",
        "PRICE_SEARCH_BRAVE_ENDPOINT",
        "PRICE_SEARCH_BRAVE_COUNTRY",
        "PRICE_SEARCH_BRAVE_SEARCH_LANG",
        "PRICE_SEARCH_BRAVE_UI_LANG",
        "PRICE_SEARCH_BRAVE_RESULT_FILTER",
        "PRICE_SEARCH_BRAVE_EXTRA_SNIPPETS",
    ):
        monkeypatch.delenv(env_name, raising=False)
