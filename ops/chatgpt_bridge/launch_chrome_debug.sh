#!/usr/bin/env bash
# =============================================================================
# launch_chrome_debug.sh — Launch Google Chrome with remote debugging enabled
#
# Run this ONCE before starting the bridge. It quits any existing Chrome
# instance and reopens it with --remote-debugging-port=9222.
#
# WARNING: This will close all existing Chrome tabs!
# To avoid losing tabs, use the "gentle" mode which tries to connect first.
# =============================================================================

PORT=9222
CHROME="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

echo "=============================================="
echo "  Chrome Debug Launcher for ChatGPT Bridge"
echo "=============================================="
echo ""

# Check if Chrome is already running with debug port
if curl -s "http://127.0.0.1:$PORT/json" > /dev/null 2>&1; then
    echo "✅ Chrome is ALREADY running with debug port $PORT"
    echo "   You can start the bridge immediately."
    
    # Check for ChatGPT tab
    CHATGPT=$(curl -s "http://127.0.0.1:$PORT/json" | python3 -c "
import sys, json
tabs = json.load(sys.stdin)
chatgpt = [t['url'] for t in tabs if 'chatgpt' in t.get('url','') or 'openai' in t.get('url','')]
if chatgpt:
    print('✅ ChatGPT tab found:', chatgpt[0][:60])
else:
    print('⚠️  No ChatGPT tab found. Open chatgpt.com in Chrome.')
")
    echo "   $CHATGPT"
    exit 0
fi

echo "Chrome is not running with debug port."
echo ""
echo "Choose mode:"
echo "  1) Safe mode — keeps existing Chrome running, opens a NEW Chrome"
echo "     instance side-by-side (recommended, won't lose tabs)"
echo "  2) Full restart — quits Chrome and relaunches with debug port"
echo ""
read -p "Enter 1 or 2 [default: 1]: " MODE
MODE=${MODE:-1}

if [ "$MODE" = "2" ]; then
    echo "Quitting Chrome..."
    osascript -e 'quit app "Google Chrome"' 2>/dev/null
    sleep 2
fi

echo "Launching Chrome with --remote-debugging-port=$PORT ..."
"$CHROME" \
    --remote-debugging-port=$PORT \
    --no-first-run \
    --no-default-browser-check \
    "https://chatgpt.com" &

echo ""
echo "✅ Chrome launched! Opening chatgpt.com..."
echo ""
echo "Next steps:"
echo "  1. Log in to ChatGPT if needed"
echo "  2. Make sure you're on the conversation you want to use"
echo "  3. Then run:  python3 ops/chatgpt_bridge/bridge.py --watch-repo --reply-to-terminal"
echo ""
echo "Bridge command (copy this):"
echo "  cd /Users/bob/GitHub/paeos && python3 ops/chatgpt_bridge/bridge.py --watch-repo --reply-to-terminal"
