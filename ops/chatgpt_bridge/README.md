# PAEOS → ChatGPT Bridge

Automatically relays Cline/DeepSeek terminal output to your open ChatGPT browser tab and pastes the architect's response back into the terminal.

## How It Works

```
Cline/DeepSeek terminal
        │ (outputs to log file via tee)
        ▼
  bridge.py (polls every 15s)
        │ detects pause/question marker
        │
        ▼
  Chrome CDP (port 9222)
        │ fills ChatGPT input box
        │ clicks Send
        │ waits for response to finish streaming
        │
        ▼
  chatgpt_response.md (saved)
        │
        ▼
  osascript → pastes response into front terminal
        │
        ▼
Cline/DeepSeek terminal receives the architect's answer
```

## First-Time Setup

### Step 1: Install Python deps
```bash
pip install requests websocket-client
```

### Step 2: Launch Chrome with debugging port

> ⚠️ You need a **Chrome instance** with remote debugging enabled.
> The script below handles this safely.

```bash
chmod +x ops/chatgpt_bridge/launch_chrome_debug.sh
./ops/chatgpt_bridge/launch_chrome_debug.sh
```

**Choose mode 1** (side-by-side) to keep your existing browser tabs.
Log into ChatGPT in the new window.

### Step 3: Start Cline with output capture

Instead of running Cline directly, wrap it:
```bash
chmod +x ops/chatgpt_bridge/cline_wrapper.sh
./ops/chatgpt_bridge/cline_wrapper.sh <your cline command>
```

Or if Cline is already running in another terminal, use `script` to mirror output:
```bash
# In the terminal where Cline is running, run:
script -a /Users/bob/GitHub/paeos/ops/chatgpt_bridge/cline_output.log
# Then relaunch Cline in that same terminal
```

### Step 4: Start the bridge

```bash
cd /Users/bob/GitHub/paeos
python3 ops/chatgpt_bridge/bridge.py \
    --watch-repo \
    --reply-to-terminal \
    --poll 15
```

## How Pause Detection Works

The bridge watches for these phrases in the Cline output log:
- `"Do you want to proceed?"`
- `"Please choose an option"`
- `"Task completed"`
- `"[Y/n]"`
- `"I need clarification"`
- `"Which option"`

When detected, it:
1. Grabs the last ~6000 chars of Cline output
2. Scans for recently modified PAEOS docs (last 5 min)
3. Sends all of this to ChatGPT
4. Waits for the response to finish streaming
5. Saves it to `chatgpt_response.md`
6. Optionally pastes it into your front terminal window

## Multiple-Choice Workaround

For Cline's option selection screens (where you can't paste):
- Tell Cline to **wait** / select "other" → Cline exits option mode
- The bridge then pastes the full ChatGPT response normally

## Files

| File | Purpose |
|------|---------|
| `bridge.py` | Main bridge script |
| `cline_wrapper.sh` | Wraps Cline to capture output to log |
| `launch_chrome_debug.sh` | Launches Chrome with CDP debugging |
| `cron_bridge.sh` | Optional cron job wrapper |
| `cline_output.log` | Live Cline output (auto-created) |
| `chatgpt_response.md` | ChatGPT responses (auto-created) |

## Troubleshooting

**"Cannot reach Chrome"**: Run `launch_chrome_debug.sh` first.

**"No ChatGPT tab found"**: Open `chatgpt.com` in the debug Chrome window.

**Bridge sends but gets no response**: ChatGPT may have changed its DOM structure. Update `CHATGPT_INPUT_SELECTOR` and `CHATGPT_SEND_SELECTOR` in `bridge.py`.

**Response not pasting to terminal**: Make sure the Terminal/iTerm2 window is in front when the bridge runs. Grant Accessibility permissions if prompted (System Preferences → Privacy → Accessibility).
