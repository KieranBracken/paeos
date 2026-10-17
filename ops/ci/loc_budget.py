#!/usr/bin/env python3
"""TCB gate F1 (PAEOS-8 §8): kernel/ LOC budget.

The kernel is the trusted computing base; it MUST stay small and auditable
(PAEOS-7.5 §3 / T8). This gate fails CLOSED (exit 1) if the total lines of
Python under kernel/ exceed the budget.

Usage:  python ops/ci/loc_budget.py [--budget N] [--root DIR]
Exit:   0 = within budget (GREEN) · 1 = over budget (RED, fail closed)
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

DEFAULT_BUDGET = 20_000  # PAEOS-8 §8 F1: kernel/ LOC budget ≤ 20k


def count_kernel_loc(root: Path) -> int:
    total = 0
    for path in sorted(root.rglob("*.py")):
        total += sum(1 for _ in path.open("r", encoding="utf-8", errors="replace"))
    return total


def main() -> int:
    ap = argparse.ArgumentParser(description="kernel/ LOC budget gate (PAEOS-8 §8 F1)")
    ap.add_argument("--budget", type=int, default=DEFAULT_BUDGET)
    ap.add_argument("--root", type=Path, default=Path("kernel"))
    args = ap.parse_args()

    if not args.root.exists():
        print(f"[loc-budget] root {args.root} not found", file=sys.stderr)
        return 1

    loc = count_kernel_loc(args.root)
    status = "GREEN" if loc <= args.budget else "RED"
    print(f"[loc-budget] {args.root}: {loc} LOC / budget {args.budget} → {status}")
    if loc > args.budget:
        print(
            f"[loc-budget] FAIL CLOSED: kernel TCB exceeds budget by {loc - args.budget} LOC.",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
