#!/usr/bin/env bash
# ============================================================
# START CLINE WITH OUTPUT LOGGING
# Run this INSTEAD of launching Cline directly.
# It tees all output to cline_output.log so the bridge
# can read the FULL history (not just what's on screen).
# ============================================================

LOG="/Users/bob/GitHub/paeos/ops/chatgpt_bridge/cline_output.log"
> "$LOG"  # clear previous log

echo "[$(date)] Cline session started with logging" >> "$LOG"
echo "Logging to: $LOG"
echo ""

# Launch Cline and tee output to log file
# The `script` command captures EVERYTHING including escape codes
script -q -F "$LOG" /usr/bin/env bash -c "node /opt/homebrew/bin/cline"
