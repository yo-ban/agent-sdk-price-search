"""Runtime adapter: local docker runtime を準備する。"""

from __future__ import annotations

import json
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Literal

SearchProvider = Literal["searxng", "brave"]

_PLAYWRIGHT_RUNTIME_CHECK = (
    "test -f '/opt/playwright-cli-runtime/node_modules/@playwright/cli/playwright-cli.js' "
    "&& test -x '/opt/google/chrome/chrome' "
    "&& test -S /tmp/.X11-unix/X99"
)


class DockerRuntimeService:
    """launcher 実行前に local docker runtime を起動・検証する。"""

    def __init__(
        self,
        *,
        repository_root: Path,
        playwright_container_name: str = "price-search-playwright-cli",
        search_provider: SearchProvider = "searxng",
        searxng_search_url: str = "http://127.0.0.1:18888/search",
    ) -> None:
        """compose file location と readiness 判定情報を保持する。"""
        self._repository_root = repository_root
        self._playwright_container_name = playwright_container_name
        self._search_provider = search_provider
        self._searxng_search_url = searxng_search_url

    def ensure_ready(self) -> None:
        """検索プロバイダ runtime と Patchright runtime を起動し、応答可能まで待つ。"""
        if self._search_provider == "searxng":
            self._ensure_searxng_ready()
        self._ensure_playwright_runtime_ready()

    def _ensure_searxng_ready(self) -> None:
        """ready な SearXNG には触れず、必要時だけ compose を起動する。"""
        if self._probe_searxng_ready():
            return

        self._run_compose(
            compose_path=self._repository_root / "infra" / "docker" / "searxng" / "compose.yaml",
            build=False,
        )
        if self._wait_for_searxng():
            return
        raise RuntimeError("SearXNG runtime is unavailable.")

    def _ensure_playwright_runtime_ready(self) -> None:
        """ready な browser runtime には触れず、必要時だけ起動・build する。"""
        if self._probe_playwright_runtime_ready():
            return

        compose_path = (
            self._repository_root / "infra" / "docker" / "playwright" / "compose.yaml"
        )
        self._run_compose(compose_path=compose_path, build=False)
        if self._wait_for_playwright_runtime(timeout_seconds=10):
            return

        self._run_compose(compose_path=compose_path, build=True)
        if self._wait_for_playwright_runtime(timeout_seconds=30):
            return
        raise RuntimeError("Playwright runtime is unavailable.")

    def _run_compose(self, *, compose_path: Path, build: bool) -> None:
        """指定 compose file を up -d する。"""
        command = ["docker", "compose", "-f", str(compose_path), "up", "-d"]
        if build:
            command.append("--build")
        subprocess.run(
            command,
            cwd=self._repository_root,
            check=True,
        )

    def _probe_searxng_ready(self) -> bool:
        """SearXNG JSON API がすでに使えるかを返す。"""
        probe_url = (
            f"{self._searxng_search_url}?q=price-search-health&format=json&engines=wikipedia"
        )
        try:
            with urllib.request.urlopen(probe_url, timeout=5) as response:
                payload = json.load(response)
            return isinstance(payload, dict) and "results" in payload
        except (OSError, urllib.error.URLError, json.JSONDecodeError):
            return False

    def _wait_for_searxng(self, *, timeout_seconds: int = 30) -> bool:
        """SearXNG JSON API が応答可能になるまで待つ。"""
        for _ in range(timeout_seconds):
            if self._probe_searxng_ready():
                return True
            time.sleep(1)
        return False

    def _probe_playwright_runtime_ready(self) -> bool:
        """Patchright runtime container がすでに使えるかを返す。"""
        running_state = subprocess.run(
            [
                "docker",
                "inspect",
                "-f",
                "{{.State.Running}}",
                self._playwright_container_name,
            ],
            cwd=self._repository_root,
            check=False,
            capture_output=True,
            text=True,
        )
        if running_state.returncode != 0 or running_state.stdout.strip() != "true":
            return False

        runtime_state = subprocess.run(
            [
                "docker",
                "exec",
                self._playwright_container_name,
                "bash",
                "-lc",
                _PLAYWRIGHT_RUNTIME_CHECK,
            ],
            cwd=self._repository_root,
            check=False,
        )
        return runtime_state.returncode == 0

    def _wait_for_playwright_runtime(self, *, timeout_seconds: int) -> bool:
        """Patchright runtime container が実行可能になるまで待つ。"""
        for _ in range(timeout_seconds):
            if self._probe_playwright_runtime_ready():
                return True
            time.sleep(1)
        return False
