#!/usr/bin/env bash

# Run the price-search launcher directly from the repository root.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPOSITORY_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

cd "${REPOSITORY_ROOT}"
exec uv run price-search-run "$@"
