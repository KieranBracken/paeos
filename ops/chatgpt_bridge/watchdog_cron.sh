#!/bin/bash
# PAEOS Watchdog — called by cron every hour
# Needs PATH set explicitly since cron has a minimal environment
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
export HOME="/Users/bob"

LOCK="/tmp/.paeos_watchdog.lock"
if [ -f "$LOCK" ]; then
    PID=$(cat "$LOCK")
    if kill -0 "$PID" 2>/dev/null; then
        exit 0  # already running
    fi
fi
echo $$ > "$LOCK"
trap "rm -f $LOCK" EXIT

/Users/bob/.pyenv/versions/3.10.13/bin/python3 \
    /Users/bob/GitHub/paeos/ops/chatgpt_bridge/watchdog.py \
    >> /Users/bob/GitHub/paeos/ops/chatgpt_bridge/watchdog.log 2>&1
