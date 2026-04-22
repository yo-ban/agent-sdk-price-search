"""Adapter tests for Docker-backed runtime preparation."""

from __future__ import annotations

import io
import json
import subprocess
import urllib.error
from pathlib import Path

from price_search_launcher.adapters.runtime.docker_runtime_service import (
    DockerRuntimeService,
)


class _JsonResponse(io.StringIO):
    """Minimal context-manager response for JSON urlopen stubs."""

    def __enter__(self) -> _JsonResponse:
        """Return the stream itself."""
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        """Close the in-memory stream."""
        self.close()


def test_ensure_ready_skips_compose_when_runtimes_are_already_available(
    monkeypatch,
) -> None:
    """Ready runtimes should not trigger any compose call."""
    compose_calls: list[tuple[str, bool]] = []

    monkeypatch.setattr(
        "price_search_launcher.adapters.runtime.docker_runtime_service.urllib.request.urlopen",
        lambda *_args, **_kwargs: _JsonResponse(json.dumps({"results": []})),
    )
    monkeypatch.setattr(
        "price_search_launcher.adapters.runtime.docker_runtime_service.time.sleep",
        lambda _seconds: None,
    )

    def fake_run(command: list[str], **kwargs) -> subprocess.CompletedProcess[str]:
        if command[:3] == ["docker", "compose", "-f"]:
            compose_calls.append((command[3], "--build" in command))
            return subprocess.CompletedProcess(command, 0)
        if command[:3] == ["docker", "inspect", "-f"]:
            return subprocess.CompletedProcess(command, 0, stdout="true\n")
        if command[:2] == ["docker", "exec"]:
            return subprocess.CompletedProcess(command, 0)
        raise AssertionError(f"unexpected command: {command!r}")

    monkeypatch.setattr(
        "price_search_launcher.adapters.runtime.docker_runtime_service.subprocess.run",
        fake_run,
    )

    service = DockerRuntimeService(repository_root=Path("/repo"))

    service.ensure_ready()

    assert compose_calls == []


def test_ensure_ready_starts_missing_runtimes_without_rebuilding_playwright(
    monkeypatch,
) -> None:
    """Stopped runtimes should be started before any Playwright rebuild is attempted."""
    compose_calls: list[tuple[str, bool]] = []
    state = {
        "searxng_ready": False,
        "playwright_running": False,
        "playwright_runtime_ready": False,
    }

    monkeypatch.setattr(
        "price_search_launcher.adapters.runtime.docker_runtime_service.time.sleep",
        lambda _seconds: None,
    )

    def fake_urlopen(*_args, **_kwargs) -> _JsonResponse:
        if not state["searxng_ready"]:
            raise urllib.error.URLError("offline")
        return _JsonResponse(json.dumps({"results": []}))

    def fake_run(command: list[str], **kwargs) -> subprocess.CompletedProcess[str]:
        if command[:3] == ["docker", "compose", "-f"]:
            compose_path = command[3]
            build = "--build" in command
            compose_calls.append((compose_path, build))
            if "searxng" in compose_path:
                state["searxng_ready"] = True
            if "playwright" in compose_path:
                state["playwright_running"] = True
                state["playwright_runtime_ready"] = True
            return subprocess.CompletedProcess(command, 0)
        if command[:3] == ["docker", "inspect", "-f"]:
            stdout = "true\n" if state["playwright_running"] else "false\n"
            return subprocess.CompletedProcess(command, 0, stdout=stdout)
        if command[:2] == ["docker", "exec"]:
            return subprocess.CompletedProcess(
                command,
                0 if state["playwright_runtime_ready"] else 1,
            )
        raise AssertionError(f"unexpected command: {command!r}")

    monkeypatch.setattr(
        "price_search_launcher.adapters.runtime.docker_runtime_service.urllib.request.urlopen",
        fake_urlopen,
    )
    monkeypatch.setattr(
        "price_search_launcher.adapters.runtime.docker_runtime_service.subprocess.run",
        fake_run,
    )

    service = DockerRuntimeService(repository_root=Path("/repo"))

    service.ensure_ready()

    assert len(compose_calls) == 2
    assert all(not build for _, build in compose_calls)


def test_ensure_ready_rebuilds_playwright_only_after_plain_start_is_insufficient(
    monkeypatch,
) -> None:
    """Playwright should fall back to rebuild only after a non-build start still fails."""
    compose_calls: list[tuple[str, bool]] = []
    state = {
        "plain_start_attempted": False,
        "build_attempted": False,
    }

    monkeypatch.setattr(
        "price_search_launcher.adapters.runtime.docker_runtime_service.urllib.request.urlopen",
        lambda *_args, **_kwargs: _JsonResponse(json.dumps({"results": []})),
    )
    monkeypatch.setattr(
        "price_search_launcher.adapters.runtime.docker_runtime_service.time.sleep",
        lambda _seconds: None,
    )

    def fake_run(command: list[str], **kwargs) -> subprocess.CompletedProcess[str]:
        if command[:3] == ["docker", "compose", "-f"]:
            compose_path = command[3]
            build = "--build" in command
            compose_calls.append((compose_path, build))
            if "playwright" in compose_path and build:
                state["build_attempted"] = True
            if "playwright" in compose_path and not build:
                state["plain_start_attempted"] = True
            return subprocess.CompletedProcess(command, 0)
        if command[:3] == ["docker", "inspect", "-f"]:
            if state["plain_start_attempted"] or state["build_attempted"]:
                return subprocess.CompletedProcess(command, 0, stdout="true\n")
            return subprocess.CompletedProcess(command, 0, stdout="false\n")
        if command[:2] == ["docker", "exec"]:
            return subprocess.CompletedProcess(
                command,
                0 if state["build_attempted"] else 1,
            )
        raise AssertionError(f"unexpected command: {command!r}")

    monkeypatch.setattr(
        "price_search_launcher.adapters.runtime.docker_runtime_service.subprocess.run",
        fake_run,
    )

    service = DockerRuntimeService(repository_root=Path("/repo"))

    service.ensure_ready()

    assert [build for path, build in compose_calls if "playwright" in path] == [False, True]


def test_ensure_ready_skips_searxng_when_brave_provider_is_selected(
    monkeypatch,
) -> None:
    """Brave provider should skip SearXNG readiness orchestration entirely."""
    compose_calls: list[tuple[str, bool]] = []

    monkeypatch.setattr(
        "price_search_launcher.adapters.runtime.docker_runtime_service.time.sleep",
        lambda _seconds: None,
    )

    def fail_urlopen(*_args, **_kwargs) -> _JsonResponse:
        raise AssertionError("SearXNG probe should not run for Brave provider")

    def fake_run(command: list[str], **kwargs) -> subprocess.CompletedProcess[str]:
        if command[:3] == ["docker", "compose", "-f"]:
            compose_calls.append((command[3], "--build" in command))
            return subprocess.CompletedProcess(command, 0)
        if command[:3] == ["docker", "inspect", "-f"]:
            return subprocess.CompletedProcess(command, 0, stdout="true\n")
        if command[:2] == ["docker", "exec"]:
            return subprocess.CompletedProcess(command, 0)
        raise AssertionError(f"unexpected command: {command!r}")

    monkeypatch.setattr(
        "price_search_launcher.adapters.runtime.docker_runtime_service.urllib.request.urlopen",
        fail_urlopen,
    )
    monkeypatch.setattr(
        "price_search_launcher.adapters.runtime.docker_runtime_service.subprocess.run",
        fake_run,
    )

    service = DockerRuntimeService(repository_root=Path("/repo"), search_provider="brave")

    service.ensure_ready()

    assert compose_calls == []
