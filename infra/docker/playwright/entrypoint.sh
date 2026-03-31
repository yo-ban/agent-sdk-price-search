#!/usr/bin/env bash

# Keep a headed Xvfb session alive so docker exec can run official playwright-cli.

set -euo pipefail

XVFB_SCREEN="${PLAYWRIGHT_XVFB_SCREEN:-1920x1080x24}"
WINDOW_SIZE="${PLAYWRIGHT_WINDOW_SIZE:-1920,1080}"
CONFIG_PATH="/opt/price-search/playwright/cli.config.json"
export WINDOW_SIZE CONFIG_PATH

python3 - <<'PY'
"""Apply container-scoped browser window size overrides to the CLI config."""

import json
import os
from pathlib import Path

config_path = Path(os.environ["CONFIG_PATH"])
window_size = os.environ["WINDOW_SIZE"]

config = json.loads(config_path.read_text())
config["browser"]["launchOptions"]["args"] = [f"--window-size={window_size}"]
config_path.write_text(json.dumps(config, indent=2) + "\n")
PY

rm -f /tmp/.X99-lock
Xvfb :99 -screen 0 "${XVFB_SCREEN}" >/tmp/xvfb.log 2>&1 &
XVFB_PID=$!

cleanup() {
  kill "${XVFB_PID}" 2>/dev/null || true
  wait "${XVFB_PID}" 2>/dev/null || true
}

trap cleanup TERM INT EXIT

while true; do
  sleep 3600
done
