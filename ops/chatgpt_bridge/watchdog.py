"""Observer-only health reporting for the PAEOS bridge control plane.

The module reads process, file-age, and repository signals without changing them.
"""

from __future__ import annotations

import argparse
import logging
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Thresholds (minutes)
# ---------------------------------------------------------------------------
_BRIDGE_LOG_THRESHOLD = 25.0
_REPO_IDLE_THRESHOLD = 30.0
_RESPONSE_THRESHOLD = 30.0


# ---------------------------------------------------------------------------
# Report type
# ---------------------------------------------------------------------------
@dataclass(frozen=True, slots=True)
class WatchdogReport:
    bridge_alive: bool
    bridge_pid: int | None
    bridge_log_age_minutes: float | None
    cline_alive: bool
    repo_idle_minutes: float | None
    response_age_minutes: float | None
    issues: tuple[str, ...]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def check_bridge_monitor(pid_file: Path) -> tuple[bool, int | None]:
    """Check whether the bridge process identified by *pid_file* is alive.

    Returns (alive, pid).  Never modifies *pid_file*.
    """
    try:
        raw = pid_file.read_text().strip()
    except (OSError, ValueError):
        return (False, None)

    if not raw:
        return (False, None)

    try:
        pid = int(raw)
    except (ValueError, TypeError):
        return (False, None)

    if pid <= 0:
        return (False, None)

    result = subprocess.run(
        ["ps", "-p", str(pid), "-o", "pid="],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode == 0 and result.stdout.strip():
        return (True, pid)

    return (False, pid)


def file_age_minutes(path: Path, *, now: float | None = None) -> float | None:
    """Return the elapsed minutes since *path* was last modified, or None."""
    try:
        mtime = path.stat().st_mtime
    except OSError:
        return None

    if now is None:
        now = time.time()
    elapsed_seconds = max(0.0, now - mtime)
    return elapsed_seconds / 60.0


def check_cline_process() -> bool:
    """Return True if at least one running process contains 'cline' (case-insensitive)."""
    result = subprocess.run(
        ["ps", "-axo", "command="],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return False
    cmd_lower = result.stdout.lower()
    return "cline" in cmd_lower


def repo_idle_minutes(repo_root: Path, *, now: float | None = None) -> float | None:
    """Return the minutes since the most recent commit in *repo_root*, or None."""
    result = subprocess.run(
        ["git", "-C", str(repo_root), "log", "-1", "--format=%ct"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return None
    raw = result.stdout.strip()
    if not raw:
        return None
    try:
        commit_ts = int(raw)
    except (ValueError, TypeError):
        return None

    if now is None:
        now = time.time()
    elapsed_seconds = max(0.0, now - commit_ts)
    return elapsed_seconds / 60.0


# ---------------------------------------------------------------------------
# Report collection
# ---------------------------------------------------------------------------
def collect_report(repo_root: Path, bridge_dir: Path) -> WatchdogReport:
    """Build a WatchdogReport by observing every signal once.

    Semantic issues are generated for every unhealthy signal.
    """
    pid_file = bridge_dir / ".monitor_pid"
    log_file = bridge_dir / "bridge.log"
    response_file = bridge_dir / "chatgpt_response.md"

    # --- bridge monitor ---
    bridge_alive, bridge_pid = check_bridge_monitor(pid_file)

    # --- bridge log age ---
    bridge_log_age = file_age_minutes(log_file)

    # --- cline process ---
    cline_alive = check_cline_process()

    # --- repository idle ---
    repo_idle = repo_idle_minutes(repo_root)

    # --- response age ---
    response_age = file_age_minutes(response_file)

    # --- issue assembly (order: most-blocking first) ---
    issues: list[str] = []

    if not bridge_alive:
        issues.append("bridge monitor stopped")

    if bridge_log_age is None or bridge_log_age > _BRIDGE_LOG_THRESHOLD:
        issues.append("bridge log stale")

    if not cline_alive:
        issues.append("cline process missing")

    if repo_idle is None or repo_idle > _REPO_IDLE_THRESHOLD:
        issues.append("repository stale")

    if response_age is None or response_age > _RESPONSE_THRESHOLD:
        issues.append("response stale")

    return WatchdogReport(
        bridge_alive=bridge_alive,
        bridge_pid=bridge_pid,
        bridge_log_age_minutes=bridge_log_age,
        cline_alive=cline_alive,
        repo_idle_minutes=repo_idle,
        response_age_minutes=response_age,
        issues=tuple(issues),
    )


# ---------------------------------------------------------------------------
# Run-once entry point
# ---------------------------------------------------------------------------
def run_watchdog(repo_root: Path, bridge_dir: Path) -> WatchdogReport:
    """Collect and log one report, then return it unchanged."""
    report = collect_report(repo_root, bridge_dir)

    if report.issues:
        for issue in report.issues:
            logger.warning("watchdog issue: %s", issue)
    else:
        logger.info("watchdog healthy")

    return report


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser(description="PAEOS watchdog — read-only bridge health monitor")
    parser.add_argument("repo_root", type=Path, help="Path to the repository root")
    parser.add_argument("bridge_dir", type=Path, help="Path to the bridge working directory")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        stream=sys.stderr,
    )

    report = run_watchdog(args.repo_root.resolve(), args.bridge_dir.resolve())
    raise SystemExit(1 if report.issues else 0)


if __name__ == "__main__":
    main()
