"""Change classifier (conservative stub) — blast-radius SOFT/HARD (PAEOS-8 §10 B0.11 / A-2).

Task B0.11. The kernel's static blast-radius detector (`classify_change`, PAEOS-7.6 §4 step 5):
a change touching the TCB must route to the amendment path, not merge on Builder+Verifier alone.

Rule (conservative stub; full static analysis is deferred to Phase 2):
  * any changed path under `kernel/` or `constitution/`  ⇒ **HARD**
  * every changed path elsewhere                          ⇒ **SOFT**
  * anything the classifier cannot resolve to a safe path ⇒ **HARD** (fail-safe)

"Cannot resolve" covers an empty change set (no information), a blank path, and — the T4 defense —
a path that escapes the tree or reaches the TCB through traversal (`runtime/../kernel/x.py`). Paths
are normalised (separators unified, `.` / `..` collapsed, leading `/` and `./` stripped) *before*
the prefix test, so a TCB change disguised in a runtime path is still classified HARD.

This mirrors the CI F2 gate (`ops/ci/tcb_diff.py`) at the same prefixes; both must agree.
"""

from __future__ import annotations

import posixpath
from collections.abc import Iterable
from typing import Literal

__all__ = ["HARD_PREFIXES", "Classification", "classify_paths"]

Classification = Literal["SOFT", "HARD"]

# The Trusted Computing Base directories. A change under either routes to the amendment path.
HARD_PREFIXES: tuple[str, ...] = ("kernel", "constitution")


def _normalize(raw: str) -> str | None:
    """Return a normalised repo-relative path, or None if it cannot be safely resolved.

    None ⇒ fail-safe HARD: blank, tree-escaping (`..`), or degenerate paths.
    """
    if not raw or not raw.strip():
        return None
    unified = raw.strip().replace("\\", "/")
    normalized = posixpath.normpath(unified).lstrip("/")
    if normalized in ("", ".") or normalized == ".." or normalized.startswith("../"):
        return None
    return normalized


def classify_paths(paths: Iterable[str]) -> Classification:
    """Classify a change set. HARD if any path touches the TCB (or cannot be resolved), else SOFT.

    Deny-by-default / fail-safe: an empty change set or any unresolvable path ⇒ HARD.
    """
    materialized = list(paths)
    if not materialized:
        return "HARD"  # no information about the blast radius ⇒ fail-safe
    for raw in materialized:
        normalized = _normalize(raw)
        if normalized is None:
            return "HARD"  # unresolvable / tree-escaping ⇒ fail-safe (T4)
        top = normalized.split("/", 1)[0]
        if top in HARD_PREFIXES:
            return "HARD"
    return "SOFT"
