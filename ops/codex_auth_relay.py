#!/usr/bin/env python3
"""Retired UI authorization relay; it refuses before inspecting prompts or cached hashes."""

from __future__ import annotations

import glob
import os
import re
import subprocess
import sys
import time
from pathlib import Path

HASH_REGEX = re.compile(r"Evidence Bundle SHA-256:\s*([0-9a-f]{64})", re.IGNORECASE)
STATE_FILE = Path("/tmp/paeos_codex_last_approved_hash.txt")


class LocalDisclosureDenied(RuntimeError):
    """The legacy authorization-shaped UI relay is disabled."""


def _deny_local_disclosure() -> None:
    raise LocalDisclosureDenied("local UI disclosure helper disabled; no content was sent")


def get_latest_hash() -> tuple[str | None, Path | None]:
    prompt_files = glob.glob("/private/tmp/*prompt*.md")
    if not prompt_files:
        return None, None
    # Sort by modification time, newest first
    prompt_files.sort(key=lambda p: os.path.getmtime(p), reverse=True)
    for p_str in prompt_files:
        p = Path(p_str)
        try:
            content = p.read_text(encoding="utf-8")
            match = HASH_REGEX.search(content)
            if match:
                return match.group(1).lower(), p
        except Exception:
            continue
    return None, None


def get_last_approved_hash() -> str | None:
    if STATE_FILE.exists():
        try:
            return STATE_FILE.read_text(encoding="utf-8").strip()
        except Exception:
            pass
    return None


def set_last_approved_hash(h: str) -> None:
    try:
        STATE_FILE.write_text(h.strip(), encoding="utf-8")
    except Exception:
        pass


def send_approval_to_chatgpt(bundle_hash: str, max_tokens: int = 4096) -> bool:
    _deny_local_disclosure()

    approval_text = (
        f"I authorize one one-shot transmission of the PAEOS evidence bundle with SHA-256 {bundle_hash} "
        f"to Google Gemini (gemini-3.6-flash) for the L14/L17 audit using max_tokens={max_tokens}, "
        f"with no fallback, retry, code changes, promotion, merge, or main/trunk mutation."
    )
    applescript = f"""
    set theApproval to "{approval_text}"
    set the clipboard to theApproval
    tell application "ChatGPT" to activate
    delay 0.8
    tell application "System Events" to tell process "ChatGPT"
        keystroke "v" using {{command down}}
        delay 0.5
        keystroke return
    end tell
    """
    try:
        subprocess.run(["osascript", "-e", applescript], capture_output=True, text=True, check=True)
        print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Authorized bundle hash: {bundle_hash} (max_tokens={max_tokens})")
        set_last_approved_hash(bundle_hash)
        return True
    except subprocess.CalledProcessError as e:
        print(f"[Relay] AppleScript injection failed: {e.stderr}", file=sys.stderr)
        return False


def check_and_authorize() -> bool:
    _deny_local_disclosure()

    latest_hash, prompt_path = get_latest_hash()
    last_hash = get_last_approved_hash()
    if latest_hash and latest_hash != last_hash:
        print(f"[Relay] New evidence bundle hash detected in {prompt_path}: {latest_hash}")
        return send_approval_to_chatgpt(latest_hash)
    elif latest_hash:
        print(f"[Relay] Latest hash {latest_hash} is already authorized.")
        return True
    else:
        print("[Relay] No active evidence bundle hash found.")
        return False


if __name__ == "__main__":
    check_and_authorize()

