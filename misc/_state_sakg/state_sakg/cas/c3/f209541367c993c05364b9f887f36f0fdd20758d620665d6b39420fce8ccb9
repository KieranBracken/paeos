"""IP-0010: the architectural-invariants executor gates the current tree.

Runs the real `ops/ci/invariants.py` entrypoint (`--no-tests` to keep the meta-test fast: the
executed grep/loc invariants + the delegated ones, not the test-kind sub-pytests). CI runs it whole.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

_REGISTRY = Path("architecture/invariants.json")


def test_registry_declares_ai_001_through_011() -> None:
    data = json.loads(_REGISTRY.read_text(encoding="utf-8"))
    ids = {k for k in data if k.startswith("AI-")}
    assert {f"AI-{n:03d}" for n in range(1, 12)} <= ids  # AI-001..AI-011 present
    for aid, inv in data.items():
        if aid.startswith("AI-"):
            assert "verify" in inv and "kind" in inv["verify"]  # every invariant has a verifier


def test_executor_passes_on_the_current_tree() -> None:
    proc = subprocess.run(
        [sys.executable, "ops/ci/invariants.py", "--no-tests"],
        capture_output=True, text=True, check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "AI-001" in proc.stdout and "AI-010" in proc.stdout  # port-independence checks ran
    assert "FAILED" not in proc.stdout
