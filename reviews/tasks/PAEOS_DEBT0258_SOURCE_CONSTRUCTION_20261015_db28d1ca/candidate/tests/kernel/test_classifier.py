"""B0.11 acceptance tests for the change classifier (PAEOS-8 §10 / A-2).

kernel/ or constitution/ ⇒ HARD; elsewhere ⇒ SOFT; unresolvable ⇒ HARD (fail-safe). Adversary
(T4) disguises a TCB change in a runtime path via traversal — still HARD.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest
from kernel.classifier import HARD_PREFIXES, classify_paths


@pytest.mark.parametrize(
    ("paths", "expected"),
    [
        (["kernel/ledger.py"], "HARD"),
        (["constitution/PAEOS-0.md"], "HARD"),
        (["kernel"], "HARD"),  # the TCB dir itself
        (["constitution"], "HARD"),
        (["docs/notes.md"], "SOFT"),
        (["runtime/agents/dispatcher.py"], "SOFT"),
        (["tests/kernel/test_ledger.py"], "SOFT"),
        (["ops/ci/loc_budget.py"], "SOFT"),
        (["docs/a.md", "runtime/b.py"], "SOFT"),  # all-soft set
        (["docs/a.md", "kernel/b.py"], "HARD"),  # any HARD ⇒ HARD
    ],
)
def test_classification(paths: list[str], expected: str) -> None:
    assert classify_paths(paths) == expected


# ---- fail-safe (unknown ⇒ HARD) -------------------------------------------


def test_empty_change_set_is_hard() -> None:
    assert classify_paths([]) == "HARD"


def test_blank_path_is_hard() -> None:
    assert classify_paths([""]) == "HARD"
    assert classify_paths(["   "]) == "HARD"


def test_tree_escaping_path_is_hard() -> None:
    assert classify_paths(["../etc/passwd"]) == "HARD"
    assert classify_paths([".."]) == "HARD"


# ---- Adversary T4: TCB change disguised in a runtime path -----------------


def test_traversal_into_kernel_is_hard() -> None:
    # a diff that looks like it touches runtime/ but reaches kernel/ via `..`
    assert classify_paths(["runtime/../kernel/ledger.py"]) == "HARD"
    assert classify_paths(["docs/../../kernel/x.py"]) == "HARD"  # also escapes → fail-safe HARD


def test_leading_dot_slash_and_absolute_normalised() -> None:
    assert classify_paths(["./kernel/x.py"]) == "HARD"
    assert classify_paths(["/kernel/x.py"]) == "HARD"
    assert classify_paths(["./docs/x.md"]) == "SOFT"


def test_backslash_separators_normalised() -> None:
    assert classify_paths(["kernel\\ledger.py"]) == "HARD"


def test_kernel_lookalike_is_not_hard() -> None:
    # a genuine runtime file whose name merely contains "kernel" is SOFT (it is in runtime/)
    assert classify_paths(["runtime/kernel_shim.py"]) == "SOFT"
    assert classify_paths(["kernelish/x.py"]) == "SOFT"  # not the kernel/ dir


# ---- DEBT-0007: Synchronisation guard with ops/ci/tcb_diff.py -----------------


def test_tcb_diff_prefixes_sync() -> None:
    tcb_diff_path = Path(__file__).resolve().parents[2] / "ops" / "ci" / "tcb_diff.py"
    spec = importlib.util.spec_from_file_location("tcb_diff", tcb_diff_path)
    assert spec is not None and spec.loader is not None
    tcb_diff = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(tcb_diff)

    tcb_diff_dirs = tuple(p.rstrip("/") for p in tcb_diff.HARD_PREFIXES)
    assert tcb_diff_dirs == HARD_PREFIXES



