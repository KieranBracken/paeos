"""Hypothesis property tests for CAS store (RB-0013 / RB-ARCH-VERIFY-002)."""

from __future__ import annotations

import tempfile
from pathlib import Path
from hypothesis import given, strategies as st

from kernel.cas import CAS, FilesystemCasStore


@given(st.binary())
def test_cas_put_get_roundtrip_property(data: bytes) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        cas = CAS(FilesystemCasStore(Path(tmp)))
        ref = cas.put(data)
        
        # Invariant 1: Hash is 64-char hex
        assert len(ref) == 64
        assert all(c in "0123456789abcdef" for c in ref)

        # Invariant 2: CAS get returns identical binary payload
        retrieved = cas.get(ref)
        assert retrieved == data

        # Invariant 3: Idempotent put returns same ref
        ref2 = cas.put(data)
        assert ref2 == ref
