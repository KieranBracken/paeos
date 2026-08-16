import pytest
from hypothesis import given
from hypothesis import strategies as st
from kernel.cas import CAS, CasMiss, InMemoryCasStore, content_hash, is_valid_hash


@given(st.binary())
def test_cas_determinism_and_format(data: bytes):
    """Hash should be deterministic, 64-char hex, and identical for same bytes."""
    h1 = content_hash(data)
    h2 = content_hash(data)
    assert h1 == h2
    assert is_valid_hash(h1)


@given(st.binary())
def test_cas_idempotency_and_missing(data: bytes):
    """Put is idempotent, and missing hashes raise CasMiss."""
    cas = CAS(InMemoryCasStore())
    addr1 = cas.put(data)
    addr2 = cas.put(data)

    assert addr1 == addr2
    assert cas.has(addr1)
    assert cas.get(addr1) == data

    # Random invalid hash should miss
    with pytest.raises(CasMiss):
        cas.get("0" * 64)
