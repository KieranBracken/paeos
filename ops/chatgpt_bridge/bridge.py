#!/usr/bin/env python3
"""Retired GUI bridge entrypoint.

The former implementation drove Chrome CDP and pasted responses into whichever terminal was
focused. That path had no transaction binding, could repeat uncertain sends, and bypassed the
PAEOS evidence ledger. It is intentionally non-executable now. Use the state-root-bound
``ops/control_plane_watchdog.py`` and the canonical chat-bridge runtime instead.
"""

from __future__ import annotations

import sys


def main() -> int:
    print(
        "legacy GUI bridge is disabled; use the state-root-bound PAEOS control plane",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
