"""Evidence-boundary tests: bundles may carry references, never inline evidence."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
VALID = ROOT / "tests/sakg/fixtures/bundle/valid"
INVALID = ROOT / "tests/sakg/fixtures/bundle/invalid"
FORBIDDEN = {"content", "payload", "evidence_payload", "inline_evidence", "raw_evidence"}


def _keys(value: object) -> set[str]:
    found: set[str] = set()
    if isinstance(value, dict):
        for key, child in value.items():
            if key.lower() in FORBIDDEN:
                found.add(key)
            found |= _keys(child)
    elif isinstance(value, list):
        for child in value:
            found |= _keys(child)
    return found


def test_valid_bundles_contain_no_inline_evidence_keys() -> None:
    for path in VALID.glob("*.json"):
        assert not _keys(json.loads(path.read_text()))


def test_inline_evidence_fixture_is_rejected() -> None:
    bad = json.loads((INVALID / "inline-evidence.json").read_text())
    assert {"evidence_payload", "payload"} <= _keys(bad)
