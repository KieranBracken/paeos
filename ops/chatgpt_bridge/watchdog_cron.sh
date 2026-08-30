#!/bin/bash
# PAEOS event watchdog — one run per scheduler tick; no GUI or terminal automation.
set -u
SCRIPT_DIR="$(cd -- "$(dirname -- "$0")" && pwd)"
REPO_ROOT="$(cd -- "$SCRIPT_DIR/../.." && pwd)"
PYTHON_BIN="${PAEOS_PYTHON_BIN:-$REPO_ROOT/.venv/bin/python}"
STATE_ROOT="${PAEOS_STATE_ROOT:-$REPO_ROOT/.paeos_state}"
exec "$PYTHON_BIN" "$REPO_ROOT/ops/control_plane_watchdog.py" \
    --state-root "$STATE_ROOT"
