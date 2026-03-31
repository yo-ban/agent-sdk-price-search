#!/usr/bin/env bash

# Start the local Web API in the background and the frontend dev server in the foreground.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPOSITORY_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

API_HOST="${PRICE_SEARCH_WEB_API_HOST:-127.0.0.1}"
API_PORT="${PRICE_SEARCH_WEB_API_PORT:-8000}"
FRONTEND_HOST="${PRICE_SEARCH_FRONTEND_HOST:-0.0.0.0}"
FRONTEND_PORT="${PRICE_SEARCH_FRONTEND_PORT:-5173}"

while [ "$#" -gt 0 ]; do
  case "$1" in
    --api-host)
      API_HOST="${2:?missing value for --api-host}"
      shift 2
      ;;
    --api-port)
      API_PORT="${2:?missing value for --api-port}"
      shift 2
      ;;
    --frontend-host)
      FRONTEND_HOST="${2:?missing value for --frontend-host}"
      shift 2
      ;;
    --frontend-port)
      FRONTEND_PORT="${2:?missing value for --frontend-port}"
      shift 2
      ;;
    -h|--help)
      cat <<'EOF'
usage: tools/start-web-stack.sh [--api-host HOST] [--api-port PORT] [--frontend-host HOST] [--frontend-port PORT]
EOF
      exit 0
      ;;
    *)
      printf 'Unknown argument: %s\n' "$1" >&2
      exit 1
      ;;
  esac
done

"${SCRIPT_DIR}/start-web-api.sh" --host "${API_HOST}" --port "${API_PORT}" &
API_PID=$!

cleanup() {
  if kill -0 "${API_PID}" >/dev/null 2>&1; then
    kill "${API_PID}" >/dev/null 2>&1 || true
    wait "${API_PID}" 2>/dev/null || true
  fi
}

trap cleanup EXIT INT TERM

for _ in $(seq 1 30); do
  if curl -fsS "http://${API_HOST}:${API_PORT}/api/health" >/dev/null 2>&1; then
    break
  fi
  sleep 1
done

cd "${REPOSITORY_ROOT}"
"${SCRIPT_DIR}/start-frontend.sh" --host "${FRONTEND_HOST}" --port "${FRONTEND_PORT}"
