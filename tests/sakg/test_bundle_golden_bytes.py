"""Golden RFC-8785-style serialization tests for bundle fixtures."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
VALID = ROOT / "tests/sakg/fixtures/bundle/valid"
GOLDENS = ROOT / "tests/sakg/fixtures/bundle/goldens"


def _jcs(value: object) -> bytes:
    # Fixture values intentionally use only JSON strings, integers, booleans, arrays, and objects;
    # for this domain Python's UTF-8, sorted-key, compact representation is RFC-8785 byte-identical.
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def test_every_bundle_golden_is_byte_identical_and_hashed() -> None:
    fixtures = sorted(VALID.glob("*.json"))
    assert fixtures
    for fixture in fixtures:
        value = json.loads(fixture.read_text())
        golden = GOLDENS / (fixture.stem + ".jcs")
        digest = GOLDENS / (fixture.stem + ".sha256")
        expected = _jcs(value)
        assert golden.read_bytes() == expected
        assert digest.read_text().strip() == "sha256:" + hashlib.sha256(expected).hexdigest()
