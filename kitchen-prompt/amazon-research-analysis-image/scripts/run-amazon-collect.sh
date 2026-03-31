#!/usr/bin/env bash
# Wrapper: run local scenario-driven collector.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COLLECT_SCRIPT="${SCRIPT_DIR}/run-research.sh"

if [ ! -f "$COLLECT_SCRIPT" ]; then
  echo "collector script not found: $COLLECT_SCRIPT" >&2
  exit 1
fi

# Pass through all args so both positional and long-option modes are supported.
bash "$COLLECT_SCRIPT" "$@"
