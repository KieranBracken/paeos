"""Junk-artifact exclusion in `_collect_writes` (notebook Entry 141, Finding K).

24 of 25 historical seals certified junk — 15 × a macOS `.DS_Store`, 9 × a 0-byte file —
because workspace harvesting collected OS droppings and empty files as authored work.
These must never be collected as writes/artifacts.
"""

from __future__ import annotations

from pathlib import Path

from runtime.integrations import _collect_writes


def test_junk_files_are_never_collected(tmp_path: Path) -> None:
    ws = tmp_path / "ws"
    (ws / "src").mkdir(parents=True)
    (ws / ".DS_Store").write_bytes(b"\x00\x00\x00\x01Bud1")  # Finder metadata
    (ws / "src" / ".DS_Store").write_bytes(b"\x00\x00\x00\x01Bud1")
    (ws / "src" / "empty.txt").write_bytes(b"")  # 0-byte file
    (ws / "src" / "real.py").write_bytes(b"print('authored work')\n")

    writes = _collect_writes(ws, ("src", "**", "*"))
    paths = [w.path for w in writes]
    assert paths == ["src/real.py"]  # only authored work survives
    assert all(len(w.content) > 0 for w in writes)
