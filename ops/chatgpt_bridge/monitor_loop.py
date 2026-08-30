#!/usr/bin/env python3
"""Disabled legacy GUI bridge monitor.

The old loop copied terminal text through a browser and pasted responses into whichever terminal
was focused. That path cannot provide transaction correlation or physical provenance. Use
``ops/control_plane_watchdog.py`` with an explicit state root instead.
"""

from __future__ import annotations

import sys


def main() -> int:
    print(
        "legacy monitor_loop is disabled; run ops/control_plane_watchdog.py with --state-root",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
