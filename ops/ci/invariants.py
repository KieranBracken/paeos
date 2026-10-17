"""Architectural invariants executor (IP-0010) — CI executes architectural truth every commit.

Reads `architecture/invariants.json` and runs each invariant's verifier. `grep-absent`,
`loc-budget`, `test` are *executed* here; `pyright`/`script`/`supply-chain` are **DELEGATED** to the
existing CI steps that already run them (pyright, `ops/ci/tcb_diff.py` for F2, the F3 supply-chain
step) — the registry references them rather than re-running expensive/merge-base-dependent gates.

Exit 0 iff no invariant FAILS. This is the executable form of already-derived architectural law
(runtime⊥MCP, single committer, adversary-PASS seal, probative evidence, Port Independence, …) —
downstream of the kernel, like a conformance suite for structure.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from collections.abc import Iterable
from pathlib import Path

_REGISTRY = Path("architecture/invariants.json")
_SKIP_DIRS = ("/.venv/", "/__pycache__/", "/.git/", "/.ruff_cache/")
_DELEGATED = {"pyright", "script", "supply-chain"}


def _py_files(base: str) -> Iterable[Path]:
    p = Path(base)
    if p.is_file():
        yield p
        return
    for f in p.rglob("*.py"):
        if not any(s in f.as_posix() for s in _SKIP_DIRS):
            yield f


def _grep_absent(spec: dict[str, object]) -> tuple[str, str]:
    pattern = re.compile(str(spec["pattern"]))
    paths = [str(x) for x in spec.get("paths", [])]  # type: ignore[union-attr]
    exclude = tuple(str(x) for x in spec.get("exclude", []))  # type: ignore[union-attr]
    hits: list[str] = []
    for base in paths:
        for f in _py_files(base):
            rel = f.as_posix()
            if any(ex in rel for ex in exclude):
                continue
            if pattern.search(f.read_text(encoding="utf-8", errors="replace")):
                hits.append(rel)
    return ("PASS", "absent") if not hits else ("FAIL", f"found in {sorted(hits)}")


def _loc_budget(spec: dict[str, object]) -> tuple[str, str]:
    paths = [str(x) for x in spec.get("paths", [])]  # type: ignore[union-attr]
    maximum = int(spec["max"])  # type: ignore[arg-type]
    total = sum(
        len(f.read_text(encoding="utf-8", errors="replace").splitlines())
        for base in paths
        for f in _py_files(base)
    )
    return ("PASS", f"{total}/{maximum}") if total <= maximum else ("FAIL", f"{total} > {maximum}")


def _test(spec: dict[str, object], *, run_tests: bool) -> tuple[str, str]:
    target = str(spec["target"])
    if not run_tests:
        return ("SKIP", "(tests disabled)")
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", target, "-q"],
        capture_output=True, text=True, check=False,
    )
    return ("PASS", "green") if proc.returncode == 0 else ("FAIL", proc.stdout.strip()[-200:])


def run(registry: Path = _REGISTRY, *, run_tests: bool = True) -> list[tuple[str, str, str, str]]:
    """Run every invariant; return (id, name, status, detail). status ∈ PASS/FAIL/DELEGATED/SKIP."""
    data = json.loads(registry.read_text(encoding="utf-8"))
    results: list[tuple[str, str, str, str]] = []
    for aid, inv in sorted((k, v) for k, v in data.items() if not k.startswith("_")):
        verify = inv["verify"]
        kind = verify["kind"]
        if kind == "grep-absent":
            status, detail = _grep_absent(verify)
        elif kind == "loc-budget":
            status, detail = _loc_budget(verify)
        elif kind == "test":
            status, detail = _test(verify, run_tests=run_tests)
        elif kind in _DELEGATED:
            status, detail = "DELEGATED", f"{kind}: existing CI gate"
        else:
            status, detail = "FAIL", f"unknown verifier kind {kind!r}"
        results.append((aid, inv["name"], status, detail))
    return results


def main(argv: list[str] | None = None) -> int:
    run_tests = "--no-tests" not in (argv or sys.argv[1:])
    failed = 0
    for aid, name, status, detail in run(run_tests=run_tests):
        print(f"  {aid}  {status:<9} {name} — {detail}")
        if status == "FAIL":
            failed += 1
    if failed:
        print(f"ARCHITECTURAL INVARIANTS: {failed} FAILED")
        return 1
    print("ARCHITECTURAL INVARIANTS: all pass (delegated gates run by their own CI steps)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
