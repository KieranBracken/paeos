#!/usr/bin/env python3
"""TCB gate F2 (PAEOS-8 §8): the soft/hard blast-radius detector.

The CI enactment of the soft/hard boundary (PAEOS-7.5 A-2). Any change under
kernel/ or constitution/ is HARD-LOOP: it cannot merge on Builder+Verifier
approval alone — it requires a human ratifier + a passing Adversary review.
Everything else is SOFT (ordinary merge path). Unknown/unreadable input is
treated as HARD (fail-safe).

Reads changed paths from argv or stdin (one per line; e.g. `git diff --name-only`).

Usage:  git diff --name-only origin/main... | python ops/ci/tcb_diff.py
        python ops/ci/tcb_diff.py kernel/ledger.py docs/x.md
Exit:   0 = SOFT (ordinary path) · 2 = HARD-LOOP (block pending human + Adversary)
        1 = usage/other error (fail-safe → treat as HARD upstream)
"""

from __future__ import annotations

import sys

# PAEOS-8 §8 F2 / §1: the TCB is kernel/ + constitution/.
HARD_PREFIXES = ("kernel/", "constitution/")


def classify(paths: list[str]) -> tuple[str, list[str]]:
    hard_hits = [p for p in paths if p.strip().startswith(HARD_PREFIXES)]
    return ("HARD-LOOP" if hard_hits else "SOFT"), hard_hits


def read_paths(argv: list[str]) -> list[str]:
    if argv:
        return argv
    return [line.strip() for line in sys.stdin if line.strip()]


def main() -> int:
    paths = read_paths(sys.argv[1:])
    if not paths:
        print("[tcb-diff] no changed paths given → SOFT (nothing to gate)")
        return 0
    verdict, hits = classify(paths)
    print(f"[tcb-diff] {len(paths)} changed path(s) → {verdict}")
    if verdict == "HARD-LOOP":
        for h in hits:
            print(f"[tcb-diff]   TCB touch: {h}")
        print(
            "[tcb-diff] HARD-LOOP: requires human ratifier + passing Adversary review "
            "before merge (PAEOS-7.5 A-2). Blocking Builder+Verifier-only merge.",
            file=sys.stderr,
        )
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
