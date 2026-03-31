#!/usr/bin/env bash

# Keep a headed Xvfb session alive so docker exec can run official playwright-cli.

set -euo pipefail

rm -f /tmp/.X99-lock
Xvfb :99 -screen 0 1440x900x24 >/tmp/xvfb.log 2>&1 &
XVFB_PID=$!

cleanup() {
  kill "${XVFB_PID}" 2>/dev/null || true
  wait "${XVFB_PID}" 2>/dev/null || true
}

trap cleanup TERM INT EXIT

while true; do
  sleep 3600
done
