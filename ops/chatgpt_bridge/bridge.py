#!/usr/bin/env python3
"""
PAEOS → ChatGPT Browser Bridge
================================
Monitors a Cline/DeepSeek terminal log file (or the PAEOS bridge prompt file)
for new output, sends it to the open ChatGPT tab via Chrome CDP, waits for the
response, then writes the response back to a file and (optionally) pastes it
back into the Cline terminal.

Usage:
  python bridge.py [--log-file PATH] [--chrome-url http://127.0.0.1:9222]
                   [--watch-repo] [--reply-to-terminal]

Requirements:
  pip install websocket-client requests
"""

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import time
import threading
from datetime import datetime
from pathlib import Path

try:
    import requests
    import websocket
except ImportError:
    print("Installing required packages...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "requests", "websocket-client"])
    import requests
    import websocket

# ── Config ────────────────────────────────────────────────────────────────────
REPO_ROOT = Path(__file__).parent.parent.parent  # /Users/bob/GitHub/paeos
BRIDGE_DIR = REPO_ROOT / ".paeos_state" / "bridge"
CLINE_LOG = REPO_ROOT / "ops" / "chatgpt_bridge" / "cline_output.log"
RESPONSE_FILE = REPO_ROOT / "ops" / "chatgpt_bridge" / "chatgpt_response.md"
SENT_HASH_FILE = REPO_ROOT / "ops" / "chatgpt_bridge" / ".last_sent_hash"
POLL_INTERVAL = 15  # seconds between checks

# Markers Cline/DeepSeek uses when it pauses waiting for input
PAUSE_MARKERS = [
    "The user denied",
    "Do you want to proceed?",
    "Please choose an option",
    "[Y/n]",
    "waiting for input",
    "Task completed",
    "I need clarification",
    "Which option",
]

# ChatGPT DOM selectors (update if ChatGPT changes its UI)
CHATGPT_INPUT_SELECTOR = "#prompt-textarea"
CHATGPT_SEND_SELECTOR = '[data-testid="send-button"]'
CHATGPT_RESPONSE_SELECTOR = '[data-message-author-role="assistant"]'


# ── CDP Client ────────────────────────────────────────────────────────────────
class CDPClient:
    """Minimal Chrome DevTools Protocol client."""

    def __init__(self, chrome_url: str = "http://127.0.0.1:9222"):
        self.chrome_url = chrome_url
        self.ws = None
        self.ws_url = None
        self._msg_id = 0
        self._responses: dict = {}
        self._lock = threading.Lock()

    def _next_id(self) -> int:
        with self._lock:
            self._msg_id += 1
            return self._msg_id

    def connect_to_chatgpt_tab(self) -> bool:
        """Find the ChatGPT tab and connect to it."""
        try:
            resp = requests.get(f"{self.chrome_url}/json", timeout=5)
            tabs = resp.json()
        except Exception as e:
            print(f"[CDP] Cannot reach Chrome at {self.chrome_url}: {e}")
            print("[CDP] Did you launch Chrome with --remote-debugging-port=9222 ?")
            return False

        chatgpt_tab = None
        for tab in tabs:
            url = tab.get("url", "")
            if "chatgpt.com" in url or "chat.openai.com" in url:
                chatgpt_tab = tab
                break

        if not chatgpt_tab:
            print(f"[CDP] No ChatGPT tab found. Open tabs: {[t.get('url') for t in tabs[:5]]}")
            return False

        self.ws_url = chatgpt_tab["webSocketDebuggerUrl"]
        print(f"[CDP] Connected to ChatGPT tab: {chatgpt_tab['url'][:80]}")

        self.ws = websocket.create_connection(self.ws_url, timeout=30)

        # Start listener thread
        def _listener():
            while True:
                try:
                    raw = self.ws.recv()
                    msg = json.loads(raw)
                    if "id" in msg:
                        with self._lock:
                            self._responses[msg["id"]] = msg
                except Exception:
                    break

        t = threading.Thread(target=_listener, daemon=True)
        t.start()
        return True

    def send(self, method: str, params: dict = None, timeout: float = 10.0) -> dict:
        """Send a CDP command and wait for its response."""
        msg_id = self._next_id()
        payload = json.dumps({"id": msg_id, "method": method, "params": params or {}})
        self.ws.send(payload)

        deadline = time.time() + timeout
        while time.time() < deadline:
            with self._lock:
                if msg_id in self._responses:
                    return self._responses.pop(msg_id)
            time.sleep(0.05)
        raise TimeoutError(f"CDP command {method} timed out after {timeout}s")

    def evaluate(self, expression: str, timeout: float = 10.0) -> any:
        """Evaluate JS in the page context and return the result."""
        resp = self.send("Runtime.evaluate", {
            "expression": expression,
            "returnByValue": True,
            "awaitPromise": True,
        }, timeout=timeout)
        result = resp.get("result", {}).get("result", {})
        if result.get("subtype") == "error":
            raise RuntimeError(f"JS error: {result.get('description')}")
        return result.get("value")

    def fill_input(self, selector: str, text: str) -> bool:
        """Type text into a textarea/input using CDP Input events."""
        # Focus via JS click
        self.evaluate(f'document.querySelector({json.dumps(selector)})?.focus()')
        time.sleep(0.3)

        # Clear existing content
        self.evaluate(f'''
            const el = document.querySelector({json.dumps(selector)});
            if (el) {{
                el.value = "";
                el.dispatchEvent(new Event("input", {{bubbles: true}}));
            }}
        ''')
        time.sleep(0.2)

        # For React-controlled textareas we need the nativeInputValueSetter trick
        js_set = f'''
            (function() {{
                const el = document.querySelector({json.dumps(selector)});
                if (!el) return false;
                const nativeInputValueSetter = Object.getOwnPropertyDescriptor(
                    window.HTMLTextAreaElement.prototype, "value").set;
                nativeInputValueSetter.call(el, {json.dumps(text)});
                el.dispatchEvent(new Event("input", {{bubbles: true}}));
                el.dispatchEvent(new Event("change", {{bubbles: true}}));
                return true;
            }})()
        '''
        result = self.evaluate(js_set)
        return bool(result)

    def click(self, selector: str):
        """Click an element by CSS selector."""
        self.evaluate(f'document.querySelector({json.dumps(selector)})?.click()')

    def get_last_assistant_message(self) -> str | None:
        """Extract the text of the last assistant response from ChatGPT."""
        js = '''
            (function() {
                const msgs = document.querySelectorAll('[data-message-author-role="assistant"]');
                if (!msgs.length) return null;
                const last = msgs[msgs.length - 1];
                return last.innerText || last.textContent || null;
            })()
        '''
        return self.evaluate(js, timeout=5)

    def wait_for_response_complete(self, timeout: float = 180.0) -> str | None:
        """
        Poll until ChatGPT stops streaming (the 'Stop generating' button disappears
        and message count stabilises), then return the last message text.
        """
        print("[CDP] Waiting for ChatGPT response to complete...")
        deadline = time.time() + timeout
        last_text = None
        stable_count = 0

        while time.time() < deadline:
            # Check if still generating (stop button visible)
            is_generating = self.evaluate('''
                !!document.querySelector('[data-testid="stop-button"]')
            ''')

            current_text = self.get_last_assistant_message()

            if not is_generating and current_text == last_text and current_text:
                stable_count += 1
                if stable_count >= 3:  # stable for 3 polls (~3s)
                    print(f"[CDP] Response complete ({len(current_text)} chars)")
                    return current_text
            else:
                stable_count = 0
                last_text = current_text

            time.sleep(1.0)

        print("[CDP] Timed out waiting for response")
        return last_text


# ── Core Bridge Logic ─────────────────────────────────────────────────────────

def content_hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:16]


def get_last_sent_hash() -> str:
    if SENT_HASH_FILE.exists():
        return SENT_HASH_FILE.read_text().strip()
    return ""


def save_sent_hash(h: str):
    SENT_HASH_FILE.write_text(h)


def is_pause_moment(text: str) -> bool:
    """Detect if Cline output contains a pause/question marker."""
    lower = text.lower()
    for marker in PAUSE_MARKERS:
        if marker.lower() in lower:
            return True
    return False


def extract_relevant_content(log_text: str, max_chars: int = 6000) -> str:
    """
    Extract the most recent meaningful chunk from Cline log output.
    Clips to last max_chars to stay within context limits.
    """
    # Remove ANSI escape codes
    ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
    clean = ansi_escape.sub('', log_text)

    # Take last max_chars
    if len(clean) > max_chars:
        clean = "...[earlier output truncated]...\n\n" + clean[-max_chars:]

    return clean.strip()


def scan_repo_for_new_docs() -> list[Path]:
    """Scan PAEOS repo for recently modified markdown docs worth reviewing."""
    interesting = []
    cutoff = time.time() - 300  # last 5 minutes

    scan_dirs = [
        REPO_ROOT / "backlog" / "research",
        REPO_ROOT / "architecture",
        REPO_ROOT / "design",
        REPO_ROOT / "proposals",
    ]

    for d in scan_dirs:
        if not d.exists():
            continue
        for f in d.rglob("*.md"):
            if f.stat().st_mtime > cutoff:
                interesting.append(f)

    return interesting


def format_message_for_chatgpt(cline_output: str, repo_docs: list[Path]) -> str:
    """Build the message to send to ChatGPT."""
    parts = []
    parts.append("## Cline/DeepSeek Terminal Output\n")
    parts.append("```")
    parts.append(cline_output)
    parts.append("```\n")

    if repo_docs:
        parts.append("\n## Recently Modified PAEOS Documents\n")
        for doc in repo_docs[:3]:  # cap at 3 docs
            try:
                content = doc.read_text()[:2000]  # first 2000 chars
                parts.append(f"\n### {doc.relative_to(REPO_ROOT)}\n")
                parts.append(content)
                if len(doc.read_text()) > 2000:
                    parts.append("\n...[truncated]")
            except Exception:
                pass

    parts.append("\n\n---\n*PAEOS Senior Architect Bridge — please review and respond.*")
    return "\n".join(parts)


def paste_response_to_terminal(response_text: str):
    """
    Write response to clipboard and use osascript to paste it
    into the front Terminal/iTerm2 window.
    """
    # Write to clipboard
    proc = subprocess.run(["pbcopy"], input=response_text.encode(), check=True)

    # Use AppleScript to find the terminal and paste
    script = '''
    tell application "System Events"
        set frontApp to name of first application process whose frontmost is true
    end tell

    if frontApp contains "Terminal" or frontApp contains "iTerm" then
        tell application "System Events"
            keystroke "v" using {command down}
        end tell
    end if
    '''
    subprocess.run(["osascript", "-e", script])
    print("[Bridge] Pasted response to terminal")


def run_bridge_cycle(cdp: CDPClient, log_file: Path, watch_repo: bool,
                     reply_to_terminal: bool):
    """Run one check-and-send cycle."""
    if not log_file.exists():
        return

    log_text = log_file.read_text()
    if not log_text.strip():
        return

    # Check if we've already sent this exact content
    h = content_hash(log_text)
    if h == get_last_sent_hash():
        return  # nothing new

    # Decide if we should send now
    clean_output = extract_relevant_content(log_text)
    should_send = is_pause_moment(clean_output)

    if not should_send:
        print(f"[Bridge] {datetime.now().strftime('%H:%M:%S')} — No pause detected, skipping")
        return

    print(f"[Bridge] {datetime.now().strftime('%H:%M:%S')} — Pause detected! Sending to ChatGPT...")

    # Gather any relevant repo docs
    repo_docs = scan_repo_for_new_docs() if watch_repo else []

    # Build message
    message = format_message_for_chatgpt(clean_output, repo_docs)

    # Fill ChatGPT input and send
    if not cdp.fill_input(CHATGPT_INPUT_SELECTOR, message):
        print("[Bridge] ERROR: Could not fill ChatGPT input box")
        return

    time.sleep(0.5)
    cdp.click(CHATGPT_SEND_SELECTOR)
    save_sent_hash(h)

    # Wait for response
    response = cdp.wait_for_response_complete(timeout=180)

    if response:
        # Save response
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        RESPONSE_FILE.write_text(f"# ChatGPT Response\n*{ts}*\n\n{response}\n")
        print(f"[Bridge] Response saved to {RESPONSE_FILE}")

        if reply_to_terminal:
            paste_response_to_terminal(response)
    else:
        print("[Bridge] No response received from ChatGPT")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="PAEOS → ChatGPT Bridge")
    parser.add_argument("--log-file", default=str(CLINE_LOG),
                        help="Path to Cline output log file to monitor")
    parser.add_argument("--chrome-url", default="http://127.0.0.1:9222",
                        help="Chrome remote debugging URL")
    parser.add_argument("--watch-repo", action="store_true",
                        help="Also scan PAEOS repo for recently modified docs")
    parser.add_argument("--reply-to-terminal", action="store_true",
                        help="Paste ChatGPT response back into front terminal")
    parser.add_argument("--poll", type=int, default=POLL_INTERVAL,
                        help="Poll interval in seconds (default: 15)")
    args = parser.parse_args()

    log_file = Path(args.log_file)
    log_file.parent.mkdir(parents=True, exist_ok=True)

    print(f"""
╔══════════════════════════════════════════════════════╗
║        PAEOS → ChatGPT Bridge v1.0                  ║
╠══════════════════════════════════════════════════════╣
║  Log file  : {str(log_file)[:50]:<50} ║
║  Chrome    : {args.chrome_url:<50} ║
║  Poll      : {args.poll}s{'':<47} ║
║  Repo scan : {'yes' if args.watch_repo else 'no':<50} ║
║  Reply     : {'yes' if args.reply_to_terminal else 'no':<50} ║
╚══════════════════════════════════════════════════════╝
""")

    # Connect to Chrome
    cdp = CDPClient(args.chrome_url)
    if not cdp.connect_to_chatgpt_tab():
        print("\n[ERROR] Could not connect to ChatGPT tab.")
        print("Please:")
        print("  1. Quit Google Chrome completely")
        print('  2. Run: /Applications/Google\\ Chrome.app/Contents/MacOS/Google\\ Chrome --remote-debugging-port=9222 &')
        print("  3. Open chatgpt.com in the new Chrome window")
        print("  4. Re-run this script")
        sys.exit(1)

    print(f"[Bridge] Monitoring {log_file} every {args.poll}s...")
    print("[Bridge] Press Ctrl+C to stop\n")

    try:
        while True:
            try:
                run_bridge_cycle(cdp, log_file, args.watch_repo, args.reply_to_terminal)
            except Exception as e:
                print(f"[Bridge] Cycle error: {e}")
            time.sleep(args.poll)
    except KeyboardInterrupt:
        print("\n[Bridge] Stopped.")


if __name__ == "__main__":
    main()
