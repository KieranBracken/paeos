"""B0.2 acceptance tests for the CAS (PAEOS-8 §10).

Covers every B0.2 criterion: same content ⇒ same hash ⇒ one entry (dedup/immutability),
10k-blob round-trip, get-after-restart (durable filesystem backend), and GC refusing to
collect a referenced hash. Core tests run against both backends; the restart test is
filesystem-only (in-memory has no "restart").
"""

from __future__ import annotations

from pathlib import Path

import pytest
from kernel.cas import (
    CAS,
    CasCorruption,
    CasMiss,
    CasStore,
    FilesystemCasStore,
    InMemoryCasStore,
    content_hash,
    is_valid_hash,
)

# ---- backends under test --------------------------------------------------


@pytest.fixture(params=["memory", "filesystem"])
def store(request: pytest.FixtureRequest, tmp_path: Path) -> CasStore:
    if request.param == "memory":
        return InMemoryCasStore()
    return FilesystemCasStore(tmp_path / "cas")


def _keys(store: CasStore) -> list[str]:
    return sorted(store.iter_keys())


# ---- put / get / addressing ----------------------------------------------


def test_put_returns_content_hash_and_get_round_trips(store: CasStore) -> None:
    cas = CAS(store)
    data = b"hello paeos"
    key = cas.put(data)
    assert key == content_hash(data)
    assert is_valid_hash(key)
    assert cas.get(key) == data


def test_same_content_same_hash_one_entry(store: CasStore) -> None:
    cas = CAS(store)
    a = cas.put(b"identical")
    b = cas.put(b"identical")  # dedup: no second entry
    assert a == b
    assert _keys(store) == [a]  # exactly one stored blob


def test_distinct_content_distinct_entries(store: CasStore) -> None:
    cas = CAS(store)
    k1 = cas.put(b"one")
    k2 = cas.put(b"two")
    assert k1 != k2
    assert len(_keys(store)) == 2
    assert cas.get(k1) == b"one"
    assert cas.get(k2) == b"two"


def test_empty_blob_is_addressable(store: CasStore) -> None:
    cas = CAS(store)
    key = cas.put(b"")
    assert key == content_hash(b"")
    assert cas.get(key) == b""
    assert cas.has(key)


def test_get_missing_raises(store: CasStore) -> None:
    cas = CAS(store)
    absent = content_hash(b"never stored")
    assert not cas.has(absent)
    with pytest.raises(CasMiss):
        cas.get(absent)


def test_get_rejects_malformed_hash(store: CasStore) -> None:
    cas = CAS(store)
    with pytest.raises(ValueError):
        cas.get("not-a-hash")
    assert not cas.has("not-a-hash")  # malformed address is simply absent, no raise


# ---- immutability ---------------------------------------------------------


def test_reput_does_not_overwrite(store: CasStore) -> None:
    cas = CAS(store)
    key = cas.put(b"immutable")
    cas.put(b"immutable")
    assert cas.get(key) == b"immutable"
    assert _keys(store) == [key]


# ---- corruption detection (address is the checksum) -----------------------


def test_get_detects_corruption_in_memory() -> None:
    store = InMemoryCasStore()
    cas = CAS(store)
    key = cas.put(b"trustworthy")
    store._blobs[key] = b"tampered"  # bit-rot / tamper under the same address
    with pytest.raises(CasCorruption):
        cas.get(key)


def test_get_detects_corruption_on_disk(tmp_path: Path) -> None:
    fs = FilesystemCasStore(tmp_path / "cas")
    cas = CAS(fs)
    key = cas.put(b"trustworthy")
    (tmp_path / "cas" / key[:2] / key[2:]).write_bytes(b"tampered on disk")
    with pytest.raises(CasCorruption):
        cas.get(key)


def test_verify_off_skips_check() -> None:
    store = InMemoryCasStore()
    cas = CAS(store, verify_on_read=False)
    key = cas.put(b"x")
    store._blobs[key] = b"y"
    assert cas.get(key) == b"y"  # no verification → returns whatever is stored


# ---- durability across restart (filesystem) -------------------------------


def test_orphaned_temp_file_is_not_a_key(tmp_path: Path) -> None:
    root = tmp_path / "cas"
    fs = FilesystemCasStore(root)
    cas = CAS(fs)
    key = cas.put(b"real")
    # simulate a crash mid-write: a stray .tmp left inside the shard dir
    (root / key[:2] / f".{key[2:]}.999.tmp").write_bytes(b"partial")
    assert sorted(fs.iter_keys()) == [key]  # orphan ignored, only real blobs are keys
    assert cas.gc(reachable={key}) == []  # GC does not treat the orphan as a collectable key


def test_get_after_restart(tmp_path: Path) -> None:
    root = tmp_path / "cas"
    key = CAS(FilesystemCasStore(root)).put(b"survives restart")
    # a brand-new store instance over the same directory models a process restart
    reopened = CAS(FilesystemCasStore(root))
    assert reopened.get(key) == b"survives restart"
    assert reopened.has(key)


# ---- 10k round-trip (B0.2 acceptance) -------------------------------------


def test_ten_thousand_blob_round_trip(store: CasStore) -> None:
    cas = CAS(store)
    keys: dict[str, bytes] = {}
    for i in range(10_000):
        data = f"blob-{i}".encode()
        keys[cas.put(data)] = data
    assert len(keys) == 10_000  # all distinct
    assert len(_keys(store)) == 10_000
    for key, data in keys.items():
        assert cas.get(key) == data
    # re-putting the whole corpus adds nothing (dedup holds at scale)
    for data in keys.values():
        cas.put(data)
    assert len(_keys(store)) == 10_000


# ---- GC referential integrity (B0.2 acceptance) ---------------------------


def test_gc_refuses_to_collect_referenced_hash(store: CasStore) -> None:
    cas = CAS(store)
    referenced = cas.put(b"reachable")
    orphan = cas.put(b"orphan")
    collected = cas.gc(reachable={referenced})
    assert collected == [orphan]  # only the unreferenced blob swept
    assert cas.has(referenced)  # referenced hash survives
    assert cas.get(referenced) == b"reachable"
    assert not cas.has(orphan)


def test_gc_empty_reachable_collects_all(store: CasStore) -> None:
    cas = CAS(store)
    a = cas.put(b"a")
    b = cas.put(b"b")
    assert cas.gc(reachable=set()) == sorted([a, b])
    assert _keys(store) == []


def test_gc_ignores_dangling_reachable(store: CasStore) -> None:
    cas = CAS(store)
    kept = cas.put(b"kept")
    dangling = content_hash(b"never stored")  # a reference to something not in the store
    collected = cas.gc(reachable={kept, dangling})
    assert collected == []  # nothing to collect; dangling ref is not repaired here
    assert cas.has(kept)


def test_gc_is_idempotent(store: CasStore) -> None:
    cas = CAS(store)
    cas.put(b"x")
    first = cas.gc(reachable=set())
    second = cas.gc(reachable=set())
    assert len(first) == 1
    assert second == []


# ---- store contract sanity ------------------------------------------------


def test_iter_keys_matches_puts(store: CasStore) -> None:
    cas = CAS(store)
    expected = {cas.put(f"v{i}".encode()) for i in range(50)}
    assert set(store.iter_keys()) == expected
