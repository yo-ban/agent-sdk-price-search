#!/usr/bin/env python3
"""Infrastructure support: patch official playwright-cli runtime for Patchright compatibility."""

from __future__ import annotations

import sys
from pathlib import Path

_TAB_PATCH_OLD = """  async clearConsoleMessages() {
    await this._initializedPromise;
    await Promise.all([
      this.page.clearConsoleMessages(),
      this.page.clearPageErrors()
    ]);
  }
"""

_TAB_PATCH_NEW = """  async clearConsoleMessages() {
    await this._initializedPromise;
    const clearConsoleMessages = this.page.clearConsoleMessages?.bind(this.page);
    const clearPageErrors = this.page.clearPageErrors?.bind(this.page);
    await Promise.all([
      clearConsoleMessages ? clearConsoleMessages() : Promise.resolve(),
      clearPageErrors ? clearPageErrors() : Promise.resolve()
    ]);
  }
"""

_MESSAGE_PATCH_OLD = """function messageToConsoleMessage(message) {
  return {
    type: message.type(),
    timestamp: message.timestamp(),
    text: message.text(),
    toString: () => `[${message.type().toUpperCase()}] ${message.text()} @ ${message.location().url}:${message.location().lineNumber}`
  };
}
"""

_MESSAGE_PATCH_NEW = """function messageToConsoleMessage(message) {
  const timestamp = typeof message.timestamp === "function" ? message.timestamp() : Date.now();
  return {
    type: message.type(),
    timestamp,
    text: message.text(),
    toString: () => `[${message.type().toUpperCase()}] ${message.text()} @ ${message.location().url}:${message.location().lineNumber}`
  };
}
"""


def main() -> int:
    """Patch the installed runtime tree in place."""
    runtime_prefix = Path(sys.argv[1]).resolve()
    tab_js = runtime_prefix / "node_modules" / "playwright" / "lib" / "mcp" / "browser" / "tab.js"
    text = tab_js.read_text(encoding="utf-8")
    if _TAB_PATCH_NEW not in text:
        if _TAB_PATCH_OLD not in text:
            raise ValueError(f"Expected snippet not found: {tab_js}")
        text = text.replace(_TAB_PATCH_OLD, _TAB_PATCH_NEW, 1)
    if _MESSAGE_PATCH_NEW not in text:
        if _MESSAGE_PATCH_OLD not in text:
            raise ValueError(f"Expected console message snippet not found: {tab_js}")
        text = text.replace(_MESSAGE_PATCH_OLD, _MESSAGE_PATCH_NEW, 1)
    if _TAB_PATCH_NEW not in text or _MESSAGE_PATCH_NEW not in text:
        raise ValueError(f"Expected snippet not found: {tab_js}")
    tab_js.write_text(text, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
