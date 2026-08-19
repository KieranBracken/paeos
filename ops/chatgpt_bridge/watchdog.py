#!/usr/bin/env python3
"""
PAEOS Autonomous Workflow Watchdog
====================================
Runs every hour. Checks health of every component in the loop and
auto-heals whatever is stuck or dead. Reports to bridge_monitor.log.

Components watched:
  1. Bridge monitor loop (monitor_loop.py)
  2. Chrome + ChatGPT CDP connection
  3. Cline terminal session (ttys011)
  4. Repo activity (git — is Cline making progress?)
  5. Bridge response file (is ChatGPT responding?)

Auto-heals:
  - Restarts dead bridge monitor
  - Relaunches Chrome if CDP drops
  - Detects stuck Cline (no repo changes > 30 min) and pastes a nudge
  - Detects bridge loop crash and restarts it
"""

import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

REPO_ROOT      = Path("/Users/bob/GitHub/paeos")
BRIDGE_DIR     = REPO_ROOT / "ops" / "chatgpt_bridge"
LOG_FILE       = BRIDGE_DIR / "bridge_monitor.log"
WATCHDOG_LOG   = BRIDGE_DIR / "watchdog.log"
PID_FILE       = BRIDGE_DIR / ".monitor_pid"
RESPONSE_FILE  = BRIDGE_DIR / "chatgpt_response.md"
CHROME_URL     = "http://127.0.0.1:9222"
CLINE_CLICK_X  = 340
CLINE_CLICK_Y  = 822
STUCK_THRESHOLD_MIN = 30   # minutes of no repo changes = stuck

try:
    import requests
except ImportError:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "requests", "-q"])
    import requests


def wlog(msg: str):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[WATCHDOG {ts}] {msg}"
    print(line, flush=True)
    with open(WATCHDOG_LOG, "a") as f:
        f.write(line + "\n")
    # Also append to main monitor log so everything is in one place
    with open(LOG_FILE, "a") as f:
        f.write(line + "\n")


# ── Health checks ──────────────────────────────────────────────────────────────

def check_bridge_monitor() -> tuple[bool, int | None]:
    """Return (alive, pid). Reads PID file written by monitor_loop."""
    if not PID_FILE.exists():
        # Try to find it by process name
        r = subprocess.run(
            ["pgrep", "-f", "monitor_loop.py"],
            capture_output=True, text=True
        )
        pids = r.stdout.strip().splitlines()
        if pids:
            PID_FILE.write_text(pids[0])
            return True, int(pids[0])
        return False, None

    pid = int(PID_FILE.read_text().strip())
    # Check if alive
    try:
        os.kill(pid, 0)
        return True, pid
    except ProcessLookupError:
        PID_FILE.unlink(missing_ok=True)
        return False, None


def check_chrome_cdp() -> bool:
    try:
        tabs = requests.get(f"{CHROME_URL}/json", timeout=5).json()
        chatgpt = [t for t in tabs if "chatgpt" in t.get("url", "")]
        return bool(chatgpt)
    except Exception:
        return False


def check_cline_running() -> bool:
    r = subprocess.run(
        ["pgrep", "-f", "node.*cline"],
        capture_output=True, text=True
    )
    return bool(r.stdout.strip())


def get_repo_idle_minutes() -> float:
    """How many minutes since the last git activity (commit or working-tree change).
    Uses git only — no slow filesystem find."""
    try:
        # Check uncommitted working-tree changes first (fastest signal)
        r = subprocess.run(
            ["git", "-C", str(REPO_ROOT), "status", "--short", "--untracked-files=no"],
            capture_output=True, text=True, timeout=5
        )
        changed = [l[3:].strip() for l in r.stdout.splitlines()
                   if l.strip() and "ops/chatgpt_bridge" not in l and "misc/" not in l]
        if changed:
            latest = max(
                (REPO_ROOT / f).stat().st_mtime
                for f in changed[:20] if (REPO_ROOT / f).exists()
            )
            return (time.time() - latest) / 60
        # Fall back to last commit timestamp
        r2 = subprocess.run(
            ["git", "-C", str(REPO_ROOT), "log", "-1", "--format=%ct"],
            capture_output=True, text=True, timeout=5
        )
        last_commit = int(r2.stdout.strip() or "0")
        return (time.time() - last_commit) / 60
    except Exception:
        return 0.0


def get_bridge_log_last_activity_minutes() -> float:
    """Minutes since the bridge monitor log was last written to."""
    if not LOG_FILE.exists():
        return 999.0
    mtime = LOG_FILE.stat().st_mtime
    return (time.time() - mtime) / 60


def get_response_age_minutes() -> float:
    """Minutes since ChatGPT last responded."""
    if not RESPONSE_FILE.exists():
        return 999.0
    return (time.time() - RESPONSE_FILE.stat().st_mtime) / 60


# ── Healers ────────────────────────────────────────────────────────────────────

def restart_bridge_monitor():
    wlog("↻ Restarting bridge monitor loop...")
    log_out = open(LOG_FILE, "a")
    proc = subprocess.Popen(
        [sys.executable, str(BRIDGE_DIR / "monitor_loop.py")],
        stdout=log_out, stderr=log_out,
        cwd=str(REPO_ROOT)
    )
    PID_FILE.write_text(str(proc.pid))
    wlog(f"  Bridge monitor restarted — PID {proc.pid}")


def relaunch_chrome():
    wlog("↻ Relaunching Chrome with debug port...")
    subprocess.Popen(
        ["/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
         "--remote-debugging-port=9222",
         "--remote-allow-origins=http://127.0.0.1:9222",
         "--user-data-dir=/tmp/chrome-debug-profile",
         "--no-first-run",
         "https://chatgpt.com"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )
    time.sleep(8)
    if check_chrome_cdp():
        wlog("  Chrome relaunched — ChatGPT tab found ✓")
    else:
        wlog("  ⚠ Chrome relaunched but ChatGPT tab not found — may need login")


def nudge_cline(message: str) -> bool:
    """Paste a nudge message into the Cline terminal. Returns True if successful."""
    # Check if display is active before attempting UI automation
    disp = subprocess.run(
        ["ioreg", "-n", "IOHIDSystem", "-d", "1"],
        capture_output=True, text=True, timeout=5
    )
    if "HIDIdleTime" in disp.stdout:
        idle_ns = 0
        for line in disp.stdout.splitlines():
            if "HIDIdleTime" in line:
                try:
                    idle_ns = int(line.split("=")[-1].strip())
                except Exception:
                    pass
        idle_min = idle_ns / 1e9 / 60
        if idle_min > 5:
            wlog(f"  ⚠ Nudge skipped — display idle {idle_min:.0f} min (screen likely locked)")
            return False

    subprocess.run(["pbcopy"], input=message.encode(), check=True)
    time.sleep(0.3)
    script = f'''tell application "Terminal" to activate
delay 0.8
tell application "System Events"
    click at {{{CLINE_CLICK_X},{CLINE_CLICK_Y}}}
    delay 0.4
    keystroke "v" using {{command down}}
    delay 0.2
    key code 36
end tell'''
    r = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
    if r.returncode == 0:
        wlog(f"  Nudge sent to Cline: {message[:60]}...")
        return True
    else:
        wlog(f"  ⚠ Nudge failed: {r.stderr.strip()}")
        return False


def read_recent_bridge_log(lines: int = 20) -> str:
    if not LOG_FILE.exists():
        return ""
    with open(LOG_FILE) as f:
        all_lines = f.readlines()
    return "".join(all_lines[-lines:])


# ── Main watchdog run ──────────────────────────────────────────────────────────

def run_watchdog():
    wlog("=" * 55)
    wlog("  PAEOS Watchdog — hourly health check")
    wlog("=" * 55)

    issues = []
    healed = []

    # ── 1. Bridge monitor ──────────────────────────────────────
    bridge_alive, bridge_pid = check_bridge_monitor()
    wlog(f"Bridge monitor: {'✅ alive (PID ' + str(bridge_pid) + ')' if bridge_alive else '❌ DEAD'}")
    if not bridge_alive:
        issues.append("Bridge monitor dead")
        restart_bridge_monitor()
        healed.append("Bridge monitor restarted")
        time.sleep(3)

    # ── 2. Bridge log activity ────────────────────────────────
    log_idle = get_bridge_log_last_activity_minutes()
    wlog(f"Bridge log idle: {log_idle:.1f} min")
    if log_idle > 25 and bridge_alive:
        issues.append(f"Bridge log stale ({log_idle:.0f} min idle)")
        wlog("  Bridge appears frozen — killing and restarting")
        if bridge_pid:
            try:
                os.kill(bridge_pid, 9)
            except Exception:
                pass
        time.sleep(2)
        restart_bridge_monitor()
        healed.append("Frozen bridge monitor replaced")

    # ── 3. Chrome / CDP ──────────────────────────────────────
    chrome_ok = check_chrome_cdp()
    wlog(f"Chrome CDP: {'✅ ChatGPT tab alive' if chrome_ok else '❌ UNREACHABLE'}")
    if not chrome_ok:
        issues.append("Chrome CDP down")
        relaunch_chrome()
        healed.append("Chrome relaunched")
        # After relaunch also restart bridge so it reconnects
        time.sleep(2)
        bridge_alive2, _ = check_bridge_monitor()
        if bridge_alive2:
            os.kill(_, 9) if _ else None
        restart_bridge_monitor()
        healed.append("Bridge restarted to reconnect CDP")

    # ── 4. Cline alive ────────────────────────────────────────
    cline_alive = check_cline_running()
    wlog(f"Cline process: {'✅ running' if cline_alive else '❌ NOT FOUND'}")
    if not cline_alive:
        issues.append("Cline not running")
        wlog("  ⚠ Cline is not running — cannot auto-restart (needs your terminal)")

    # ── 5. Repo activity / stuck detection ───────────────────
    idle_min = get_repo_idle_minutes()
    wlog(f"Repo idle: {idle_min:.1f} min")
    if idle_min > STUCK_THRESHOLD_MIN and cline_alive:
        issues.append(f"Repo stuck ({idle_min:.0f} min no changes)")
        recent_log = read_recent_bridge_log(10)
        # Check if it's a bridge issue or a Cline issue
        if "Loop error" in recent_log or "Could not fill" in recent_log:
            wlog("  Bridge errors detected — restarting bridge")
            restart_bridge_monitor()
            healed.append("Bridge restarted after errors")
        else:
            # Nudge Cline to continue
            nudge = (
                "The autonomous workflow appears to have stalled. "
                "Please check your current task status, summarise what you last completed, "
                "and continue with the next step in the approved implementation sequence. "
                "If you are waiting for architect input, re-state your questions."
            )
            nudge_ok = nudge_cline(nudge)
            if nudge_ok:
                healed.append("Nudge sent to unstick Cline")
            else:
                issues.append("Nudge failed — screen likely locked, cannot auto-heal")

    # ── 6. Response freshness ────────────────────────────────
    resp_age = get_response_age_minutes()
    wlog(f"Last ChatGPT response: {resp_age:.1f} min ago")

    # ── 7. Quick git summary ──────────────────────────────────
    r = subprocess.run(
        ["git", "-C", str(REPO_ROOT), "log", "--oneline", "-3"],
        capture_output=True, text=True
    )
    wlog(f"Last 3 commits:\n  " + r.stdout.strip().replace("\n", "\n  "))

    # ── Summary ───────────────────────────────────────────────
    wlog("-" * 55)
    if not issues:
        wlog("✅ All systems healthy — autonomous loop running smoothly")
    else:
        wlog(f"⚠ Issues found: {len(issues)}")
        for i in issues: wlog(f"  • {i}")
        wlog(f"✅ Healed: {len(healed)}")
        for h in healed: wlog(f"  ↻ {h}")
    wlog("=" * 55 + "\n")


if __name__ == "__main__":
    run_watchdog()


# ── Better stuck detection using git ──────────────────────────────────────────

def get_git_idle_minutes() -> float:
    """Minutes since the last git commit. More reliable than file mtime."""
    try:
        r = subprocess.run(
            ["git", "-C", str(REPO_ROOT), "log", "-1", "--format=%ct"],
            capture_output=True, text=True, timeout=5
        )
        last_commit_ts = int(r.stdout.strip() or "0")
        return (time.time() - last_commit_ts) / 60
    except Exception:
        return 0.0


def get_working_tree_age_minutes() -> float:
    """Minutes since any tracked file was modified (uncommitted changes too)."""
    try:
        r = subprocess.run(
            ["git", "-C", str(REPO_ROOT), "status", "--short"],
            capture_output=True, text=True, timeout=5
        )
        changed_files = [
            line[3:].strip() for line in r.stdout.splitlines()
            if line.strip() and not line[3:].strip().startswith("ops/chatgpt_bridge")
        ]
        if not changed_files:
            return get_git_idle_minutes()  # no uncommitted changes, use last commit
        latest = 0.0
        for f in changed_files[:20]:
            try:
                mtime = (REPO_ROOT / f).stat().st_mtime
                if mtime > latest:
                    latest = mtime
            except Exception:
                pass
        return (time.time() - latest) / 60 if latest else get_git_idle_minutes()
    except Exception:
        return 0.0
