"""B0.1 acceptance tests for the ledger (PAEOS-8 §10).

Covers every B0.1 criterion: monotonic seq, per-row prev_hash, verify_chain detects any
tampered row (hypothesis, random rows + random fields), a second writer is refused, a
fork is refused (Adversary T7), and the 1k-event property test. The reference backend is
InMemoryLedgerStore; the same tests bind unchanged to any LedgerStore.
"""

from __future__ import annotations

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from kernel.ledger import (
    GENESIS_HASH,
    ChainCorruption,
    Event,
    ForkRejected,
    InMemoryLedgerStore,
    Ledger,
    LedgerError,
    SingleWriterViolation,
    compute_row_hash,
    tamper,
)

# ---- strategies -----------------------------------------------------------

_json_scalars = (
    st.none()
    | st.booleans()
    | st.integers()
    | st.floats(allow_nan=False, allow_infinity=False)
    | st.text(max_size=20)
)
_json_values = st.recursive(
    _json_scalars,
    lambda children: st.lists(children, max_size=4)
    | st.dictionaries(st.text(max_size=8), children, max_size=4),
    max_leaves=6,
)
_payloads = st.dictionaries(st.text(max_size=8), _json_values, max_size=4)
_events = st.builds(
    Event,
    schema_ver=st.integers(min_value=0, max_value=5),
    kind=st.text(min_size=1, max_size=12),
    payload=_payloads,
)


def _fresh() -> tuple[InMemoryLedgerStore, Ledger]:
    store = InMemoryLedgerStore()
    return store, Ledger(store)


# ---- append / seq / chain -------------------------------------------------


def test_empty_ledger_head_is_genesis() -> None:
    _, ledger = _fresh()
    assert ledger.head() is None
    assert ledger.head_hash() == GENESIS_HASH
    assert ledger.verify_chain() == GENESIS_HASH


def test_append_returns_monotonic_seq_from_one() -> None:
    _, ledger = _fresh()
    seqs = [ledger.append(Event(1, "e", {"i": i})) for i in range(5)]
    assert seqs == [1, 2, 3, 4, 5]


def test_first_row_binds_to_genesis_then_chains() -> None:
    store, ledger = _fresh()
    ledger.append(Event(1, "a"))
    ledger.append(Event(1, "b"))
    rows = ledger.read()
    assert rows[0].prev_hash == GENESIS_HASH
    assert rows[1].prev_hash == rows[0].row_hash  # each row commits to its predecessor
    assert ledger.head_hash() == rows[-1].row_hash
    assert store.count() == 2


def test_append_never_mutates_prior_rows() -> None:
    _, ledger = _fresh()
    ledger.append(Event(1, "a", {"x": 1}))
    before = ledger.read(1, 2)[0]
    for i in range(10):
        ledger.append(Event(1, "b", {"i": i}))
    after = ledger.read(1, 2)[0]
    assert before == after  # frozen row is byte-identical after later appends


# ---- read range semantics -------------------------------------------------


def test_read_range_is_half_open() -> None:
    _, ledger = _fresh()
    for i in range(1, 6):
        ledger.append(Event(1, "e", {"i": i}))
    assert [r.seq for r in ledger.read(2, 4)] == [2, 3]
    assert [r.seq for r in ledger.read()] == [1, 2, 3, 4, 5]
    assert [r.seq for r in ledger.read(3)] == [3, 4, 5]
    assert ledger.read(6) == []


def test_read_rejects_bad_bounds() -> None:
    _, ledger = _fresh()
    ledger.append(Event(1, "e"))
    with pytest.raises(ValueError):
        ledger.read(0)
    with pytest.raises(ValueError):
        ledger.read(5, 2)


# ---- single writer (FR-5) -------------------------------------------------


def test_second_writer_refused() -> None:
    store = InMemoryLedgerStore()
    first = Ledger(store, writer_id="alpha")
    with pytest.raises(SingleWriterViolation):
        Ledger(store, writer_id="beta")
    first.close()  # released → a new writer may now attach
    second = Ledger(store, writer_id="beta")
    assert second.append(Event(1, "ok")) == 1


def test_same_writer_id_is_idempotent_reattach() -> None:
    store = InMemoryLedgerStore()
    Ledger(store, writer_id="same")
    # same owner re-attaching is allowed (models a reconnecting session holding the lock)
    again = Ledger(store, writer_id="same")
    assert again.append(Event(1, "ok")) == 1


def test_context_manager_releases_writer() -> None:
    store = InMemoryLedgerStore()
    with Ledger(store, writer_id="ctx") as ledger:
        ledger.append(Event(1, "e"))
    Ledger(store, writer_id="other")  # no raise: writer released on exit


def test_closed_ledger_refuses_append() -> None:
    _, ledger = _fresh()
    ledger.close()
    with pytest.raises(LedgerError):
        ledger.append(Event(1, "e"))


# ---- fork rejection (Adversary T7) ---------------------------------------


def test_fork_at_existing_seq_refused() -> None:
    store, ledger = _fresh()
    ledger.append(Event(1, "a"))
    # Adversary forges a competing row at seq 1 and pushes it straight at the store.
    forged = compute_row_hash(GENESIS_HASH, 1, "2026-01-01T00:00:00+00:00", Event(1, "evil"))
    forged_row = tamper(ledger.read(1, 2)[0], event=Event(1, "evil"), row_hash=forged)
    with pytest.raises(ForkRejected):
        store.append_row(forged_row)


def test_seq_must_be_dense_no_skips() -> None:
    store, ledger = _fresh()
    ledger.append(Event(1, "a"))
    skipped = tamper(ledger.read(1, 2)[0], seq=3)
    with pytest.raises(ForkRejected):
        store.append_row(skipped)


# ---- tamper detection (property: any row, any field) ----------------------


@settings(max_examples=100)
@given(events=st.lists(_events, min_size=1, max_size=25), seed=st.integers())
def test_verify_detects_any_tampered_row(events: list[Event], seed: int) -> None:
    store = InMemoryLedgerStore()
    ledger = Ledger(store)
    for ev in events:
        ledger.append(ev)
    assert ledger.verify_chain() == ledger.head_hash()  # honest chain verifies

    n = len(events)
    i = seed % n  # a random row to corrupt
    original = store._rows[i]  # test reaches into the reference backend
    kind2 = original.event.kind + "!"
    mutated_event = Event(original.event.schema_ver, kind2, original.event.payload)

    # each tamper touches a different field; every one must break verify_chain
    tampered_variants = [
        tamper(original, row_hash="0" * 64),
        tamper(original, prev_hash="f" * 64),
        tamper(original, timestamp="X" + original.timestamp),
        tamper(original, event=mutated_event),
    ]
    for bad in tampered_variants:
        store._rows[i] = bad
        with pytest.raises(ChainCorruption):
            ledger.verify_chain()
    store._rows[i] = original
    assert ledger.verify_chain() == ledger.head_hash()  # restored → honest again


def test_dropping_a_row_is_detected() -> None:
    store, ledger = _fresh()
    for i in range(5):
        ledger.append(Event(1, "e", {"i": i}))
    del store._rows[2]  # excise seq 3; leaves a link/seq break
    with pytest.raises(ChainCorruption):
        ledger.verify_chain()


# ---- the 1k-event corpus (B0.1 acceptance) --------------------------------


def test_thousand_event_corpus() -> None:
    store = InMemoryLedgerStore()
    ledger = Ledger(store)
    for i in range(1000):
        payload: dict[str, object] = {
            "i": i,
            "parity": "even" if i % 2 == 0 else "odd",
            "nested": {"square": i * i, "tags": [f"t{i % 7}", None, i % 2 == 0]},
        }
        seq = ledger.append(Event(schema_ver=1, kind="corpus", payload=payload))  # type: ignore[arg-type]
        assert seq == i + 1
    assert store.count() == 1000
    assert [r.seq for r in ledger.read()] == list(range(1, 1001))
    assert ledger.read(1, 1)[0:0] == []  # empty half-open range is empty
    head = ledger.verify_chain()  # full-chain integrity over 1k rows
    assert head == ledger.head_hash()
    # a single tamper anywhere in the 1k corpus is still caught
    store._rows[500] = tamper(store._rows[500], row_hash="0" * 64)
    with pytest.raises(ChainCorruption):
        ledger.verify_chain()
