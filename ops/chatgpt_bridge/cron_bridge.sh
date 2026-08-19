#!/usr/bin/env bash
# =============================================================================
# cron_bridge.sh — Periodic poller for bridge.py (if you prefer cron over
#                  the built-in polling loop)
#
# To install as a cron job (every 30 seconds):
#   crontab -e
#   Add this line:
#   * * * * * /Users/bob/GitHub/paeos/ops/chatgpt_bridge/cron_bridge.sh
#   * * * * * sleep 30 && /Users/bob/GitHub/paeos/ops/chatgpt_bridge/cron_bridge.sh
#
# NOTE: bridge.py has its own polling loop (--poll flag), so you don't
# NEED this cron script unless you want the bridge as a pure cron job.
# =============================================================================

REPO="/Users/bob/GitHub/paeos"
LOG="$REPO/ops/chatgpt_bridge/bridge_cron.log"
LOCK="$REPO/ops/chatgpt_bridge/.bridge_lock"

# Prevent multiple simultaneous runs
if [ -f "$LOCK" ]; then
    PID=$(cat "$LOCK")
    if kill -0 "$PID" 2>/dev/null; then
        exit 0  # already running
    fi
fi
echo $$ > "$LOCK"
trap "rm -f $LOCK" EXIT

cd "$REPO" || exit 1

# Run one bridge cycle (--poll 0 would run once and exit, so we use --poll with a large number
# and just kill it after one cycle — or just invoke the bridge in one-shot mode)
python3 ops/chatgpt_bridge/bridge.py \
    --watch-repo \
    --reply-to-terminal \
    --poll 999999 \
    >> "$LOG" 2>&1 &

BRIDGE_PID=$!
sleep 60  # let it run for 60 seconds max per cron trigger
kill $BRIDGE_PID 2>/dev/null
