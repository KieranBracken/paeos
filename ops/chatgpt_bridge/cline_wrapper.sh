#!/usr/bin/env bash
# =============================================================================
# cline_wrapper.sh — Historical output capture helper for Cline/DeepSeek.
#                    It is not a transport or control-plane component.
#
# Usage:
#   chmod +x cline_wrapper.sh
#   ./cline_wrapper.sh
#
# This wrapper:
#   1. Captures all Cline stdout/stderr to cline_output.log (with timestamps)
#   2. Displays output in the terminal as normal (using `tee`)
#   3. Does not transmit, paste, or authorize any response
# =============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_FILE="$SCRIPT_DIR/cline_output.log"

# Clear previous log
> "$LOG_FILE"
echo "[wrapper] Logging Cline output to: $LOG_FILE"
echo "[wrapper] Start time: $(date)"
echo "---" >> "$LOG_FILE"

# If Cline writes to a specific log, just archive or inspect that instead.
# Otherwise, run a worker command with tee:
# Replace "cline ..." with your actual Cline launch command.

# ── Option A: If you launch Cline via npm/npx ─────────────────────────────
# npx cline 2>&1 | tee -a "$LOG_FILE"

# ── Option B: If Cline is a CLI tool ──────────────────────────────────────
# cline run 2>&1 | tee -a "$LOG_FILE"

# ── Option C: Generic — wrap any command ──────────────────────────────────
# Usage: ./cline_wrapper.sh <your-cline-command>
if [ $# -gt 0 ]; then
    "$@" 2>&1 | tee -a "$LOG_FILE"
else
    echo "[wrapper] No command provided. Just tailing for existing Cline output..."
    echo "[wrapper] Usage: $0 <cline command>"
    echo ""
    echo "[wrapper] Example: $0 npx @anthropic-ai/cline"
    echo ""
    echo "[wrapper] If Cline is already running, manually append its output:"
    echo "  script -a $LOG_FILE"
fi
