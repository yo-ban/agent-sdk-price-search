#!/usr/bin/env bash

# Start the launcher-backed Web API with stable local defaults.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPOSITORY_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

HOST="${PRICE_SEARCH_WEB_API_HOST:-127.0.0.1}"
PORT="${PRICE_SEARCH_WEB_API_PORT:-8000}"

while [ "$#" -gt 0 ]; do
  case "$1" in
    --host)
      HOST="${2:?missing value for --host}"
      shift 2
      ;;
    --port)
      PORT="${2:?missing value for --port}"
      shift 2
      ;;
    -h|--help)
      cat <<'EOF'
usage: tools/start-web-api.sh [--host HOST] [--port PORT]
EOF
      exit 0
      ;;
    *)
      printf 'Unknown argument: %s\n' "$1" >&2
      exit 1
      ;;
  esac
done

cd "${REPOSITORY_ROOT}"
exec uv run price-search-web-api --host "${HOST}" --port "${PORT}"
