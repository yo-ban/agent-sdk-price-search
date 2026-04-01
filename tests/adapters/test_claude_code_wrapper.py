"""Tests for the Claude Code environment-cleaning wrapper."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path


def test_claude_code_wrapper_unsets_provider_env_before_exec(tmp_path: Path) -> None:
    """Wrapper should remove configured provider env vars before launching Claude."""
    fake_claude_path = tmp_path / "fake-claude"
    fake_claude_path.write_text(
        "\n".join(
            [
                "#!/usr/bin/env python3",
                "import json",
                "import os",
                "keys = [",
                "    'ANTHROPIC_API_KEY',",
                "    'ANTHROPIC_AUTH_TOKEN',",
                "    'ANTHROPIC_BASE_URL',",
                "    'OPENROUTER_API_KEY',",
                "    'CLAUDE_CODE_USE_BEDROCK',",
                "]",
                "print(json.dumps({key: os.environ.get(key) for key in keys}))",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    fake_claude_path.chmod(0o755)

    wrapper_path = (
        Path(__file__).resolve().parents[2]
        / "workspace_assets"
        / "bin"
        / "claude-code-wrapper"
    )
    env = {
        **os.environ,
        "PRICE_SEARCH_CLAUDE_REAL_CLI_PATH": str(fake_claude_path),
        "PRICE_SEARCH_CLAUDE_UNSET_ENV": (
            "ANTHROPIC_API_KEY,ANTHROPIC_AUTH_TOKEN,ANTHROPIC_BASE_URL,OPENROUTER_API_KEY"
        ),
        "ANTHROPIC_API_KEY": "anthropic-key",
        "ANTHROPIC_AUTH_TOKEN": "auth-token",
        "ANTHROPIC_BASE_URL": "https://openrouter.ai/api",
        "OPENROUTER_API_KEY": "openrouter-key",
        "CLAUDE_CODE_USE_BEDROCK": "1",
    }

    completed_process = subprocess.run(
        [str(wrapper_path), "--version"],
        check=True,
        text=True,
        capture_output=True,
        env=env,
    )

    observed_env = json.loads(completed_process.stdout)
    assert observed_env["ANTHROPIC_API_KEY"] is None
    assert observed_env["ANTHROPIC_AUTH_TOKEN"] is None
    assert observed_env["ANTHROPIC_BASE_URL"] is None
    assert observed_env["OPENROUTER_API_KEY"] is None
    assert observed_env["CLAUDE_CODE_USE_BEDROCK"] == "1"
