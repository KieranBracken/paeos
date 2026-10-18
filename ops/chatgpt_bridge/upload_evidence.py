#!/usr/bin/env python3
"""Retired UI disclosure helper; outbound submission is disabled before payload handling."""
import os
import sys
import json
import time
import subprocess
from pathlib import Path

REPO_ROOT = Path("/Users/bob/GitHub/paeos")


class LocalDisclosureDenied(RuntimeError):
    """The legacy UI disclosure path is disabled before inspecting its payload."""


def _deny_local_disclosure() -> None:
    raise LocalDisclosureDenied("local UI disclosure helper disabled; no content was sent")


def get_latest_evidence_files():
    """Find any freshly generated markdown/evidence files in docs/, .paeos_state/, ops/."""
    candidates = []
    for search_dir in [REPO_ROOT / ".paeos_state", REPO_ROOT / "docs", REPO_ROOT / "ops"]:
        if not search_dir.exists():
            continue
        for p in search_dir.rglob("*.md"):
            mtime = p.stat().st_mtime
            if time.time() - mtime < 1800:
                candidates.append(p)
    return sorted(candidates, key=lambda p: p.stat().st_mtime, reverse=True)

def submit_payload_to_chatgpt(text_content: str, files_to_attach=None):
    """Refuse the unbound legacy UI route before reading or serializing its payload."""
    _deny_local_disclosure()

    js_text = json.dumps(text_content)
    
    insert_js = f"""(() => {{
        const el = document.getElementById("prompt-textarea");
        if (!el) return "no-textarea";
        el.focus();
        const sel = window.getSelection();
        const range = document.createRange();
        range.selectNodeContents(el);
        sel.removeAllRanges();
        sel.addRange(range);
        document.execCommand("insertText", false, {js_text});
        return "inserted";
    }})()"""
    
    with open("/tmp/paeos_bridge_insert.js", "w") as f:
        f.write(insert_js)
        
    subprocess.run([
        "osascript", "-e",
        'tell application "Google Chrome" to activate',
        "-e",
        'tell application "Google Chrome" to tell active tab of front window to execute javascript (read POSIX file "/tmp/paeos_bridge_insert.js")'
    ], capture_output=True)
    
    time.sleep(0.5)
    
    click_js = """(() => {
        const btn = document.querySelector('button[data-testid="send-button"], button[aria-label="Send prompt"], button.composer-submit-button-color');
        if (btn && !btn.disabled) {
            btn.click();
            return "clicked";
        }
        return "no-btn-or-disabled";
    })()"""
    
    with open("/tmp/paeos_bridge_click.js", "w") as f:
        f.write(click_js)
        
    res = subprocess.run([
        "osascript", "-e",
        'tell application "Google Chrome" to tell active tab of front window to execute javascript (read POSIX file "/tmp/paeos_bridge_click.js")'
    ], capture_output=True, text=True)
    return res.stdout.strip()

if __name__ == "__main__":
    files = get_latest_evidence_files()
    print("Found recent evidence files:", [str(f) for f in files])
