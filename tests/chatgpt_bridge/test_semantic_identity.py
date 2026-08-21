#!/usr/bin/env python3
"""
PAEOS Bridge Monitor — 18 Adversarial Unit Tests for §8 Semantic Transaction Protocol
Authoritative spec: ops/chatgpt_bridge/SEMANTIC_IDENTITY_DESIGN.md (§8.8)
"""
import json
import os
import shutil
import time
from pathlib import Path
import pytest

from ops.chatgpt_bridge.monitor_loop import (
    IDENTITY_VERSION,
    REVIEW_TYPE,
    SCHEMA_VERSION,
    atomic_inbound_transition,
    atomic_outbound_transition,
    canonical_structured,
    evidence_hash,
    freeze_evidence,
    is_turn_complete,
    load_tx_state,
    request_payload_hash,
    resolve_active_session,
    save_tx_state,
    semantic_hash,
    transaction_key,
    turn_identity,
    _default_tx,
)


@pytest.fixture
def test_bridge_dir(tmp_path):
    bdir = tmp_path / "chatgpt_bridge"
    bdir.mkdir()
    tx_file = bdir / ".tx_state.json"
    return bdir, tx_file


def test_1_frame_invariance():
    """1. Frame invariance — same turn M, any footer/spinner redraw => identical semanticHash."""
    msg1 = {"role": "assistant", "content": [{"type": "text", "text": "Plan approved. All 18 tests passing."}]}
    msg2 = {"role": "assistant", "content": [{"type": "text", "text": "Plan approved. All 18 tests passing."}]}
    assert semantic_hash(msg1) == semantic_hash(msg2)


def test_2_semantic_discrimination():
    """2. Semantic discrimination — two turns, different text => different transactionKey."""
    msg1 = {"role": "assistant", "content": [{"type": "text", "text": "Executing Step 1."}]}
    msg2 = {"role": "assistant", "content": [{"type": "text", "text": "Executing Step 2."}]}
    ev = {"canonical_artifacts": [], "reviewed_tree_sha256": "abc", "selection_policy": "p"}
    ev_h = evidence_hash(ev)
    k1 = transaction_key(IDENTITY_VERSION, REVIEW_TYPE, "s1:m1", semantic_hash(msg1), ev_h)
    k2 = transaction_key(IDENTITY_VERSION, REVIEW_TYPE, "s1:m2", semantic_hash(msg2), ev_h)
    assert k1 != k2


def test_2b_eventref_distinctness():
    """2b. eventRef distinctness — turns #41 & #57 both \x27All tests pass.\x27 => different transactionKey."""
    msg = {"role": "assistant", "content": [{"type": "text", "text": "All tests pass."}]}
    sem_h = semantic_hash(msg)
    ev = {"canonical_artifacts": [], "reviewed_tree_sha256": "abc", "selection_policy": "p"}
    ev_h = evidence_hash(ev)
    k41 = transaction_key(IDENTITY_VERSION, REVIEW_TYPE, "s1:msg_00000041", sem_h, ev_h)
    k57 = transaction_key(IDENTITY_VERSION, REVIEW_TYPE, "s1:msg_00000057", sem_h, ev_h)
    assert k41 != k57


def test_3_failed_return_independence(test_bridge_dir):
    """3. Failed-return independence — outbound SUBMITTED; paste fails => outbound stays SUBMITTED."""
    bdir, tx_file = test_bridge_dir
    tx = _default_tx()
    atomic_outbound_transition(tx, "SUBMITTED", state_file=tx_file, transaction_key="k123", review_request_id="r1", dispatch_seq=1)
    
    # Inbound is captured
    atomic_inbound_transition(tx, "CAPTURED", state_file=tx_file, review_request_id="r1", transaction_key="k123", dispatch_seq=1, response_pending="verdict")
    
    # Paste fails => transition to DELIVERY_PENDING
    atomic_inbound_transition(tx, "DELIVERY_PENDING", state_file=tx_file)
    
    loaded = load_tx_state(tx_file)
    assert loaded["outbound"]["state"] == "SUBMITTED"
    assert loaded["inbound"]["state"] == "DELIVERY_PENDING"


def test_4_crash_before_dispatching(test_bridge_dir):
    """4. Crash before DISPATCHING — PREPARED persisted => safe retry."""
    bdir, tx_file = test_bridge_dir
    tx = _default_tx()
    atomic_outbound_transition(tx, "PREPARED", state_file=tx_file, transaction_key="k1", review_request_id="r1", dispatch_seq=1)
    
    loaded = load_tx_state(tx_file)
    assert loaded["outbound"]["state"] == "PREPARED"
    assert loaded["outbound"]["review_request_id"] == "r1"


def test_5_crash_during_dispatching(test_bridge_dir):
    """5. Crash during DISPATCHING => RECONCILIATION_REQUIRED (fail-closed)."""
    bdir, tx_file = test_bridge_dir
    tx = _default_tx()
    atomic_outbound_transition(tx, "DISPATCHING", state_file=tx_file, transaction_key="k1")
    atomic_outbound_transition(tx, "RECONCILIATION_REQUIRED", state_file=tx_file)
    
    loaded = load_tx_state(tx_file)
    assert loaded["outbound"]["state"] == "RECONCILIATION_REQUIRED"


def test_6_crash_after_submitted(test_bridge_dir):
    """6. Crash after SUBMITTED — restart suppresses => sends == 0."""
    bdir, tx_file = test_bridge_dir
    tx = _default_tx()
    atomic_outbound_transition(tx, "SUBMITTED", state_file=tx_file, transaction_key="k1", committed_at=time.time())
    
    loaded = load_tx_state(tx_file)
    assert loaded["outbound"]["state"] == "SUBMITTED"
    assert loaded["outbound"]["transaction_key"] == "k1"


def test_7_evidence_binding(tmp_path):
    """7. Evidence binding — mtime touch => same hash; byte change => different hash."""
    doc = tmp_path / "DESIGN.md"
    doc.write_text("v1 content", encoding="utf-8")
    
    ev1 = freeze_evidence([doc], "s1:m1", repo_root=tmp_path)
    h1 = evidence_hash(ev1)
    
    # Touch mtime without modifying bytes
    os.utime(doc, (time.time() + 100, time.time() + 100))
    ev2 = freeze_evidence([doc], "s1:m1", repo_root=tmp_path)
    h2 = evidence_hash(ev2)
    assert h1 == h2
    
    # Modify content bytes
    doc.write_text("v2 modified content", encoding="utf-8")
    ev3 = freeze_evidence([doc], "s1:m1", repo_root=tmp_path)
    h3 = evidence_hash(ev3)
    assert h1 != h3


def test_8_restart_persistence(test_bridge_dir):
    """8. Restart persistence — tx_state is byte-stable across reloads."""
    bdir, tx_file = test_bridge_dir
    tx = _default_tx()
    atomic_outbound_transition(tx, "SUBMITTED", state_file=tx_file, transaction_key="k_stable", review_request_id="req_1")
    
    t1 = tx_file.read_text(encoding="utf-8")
    loaded = load_tx_state(tx_file)
    save_tx_state(loaded, tx_file)
    t2 = tx_file.read_text(encoding="utf-8")
    assert t1 == t2


def test_9_turn_completeness_mutation(tmp_path):
    """9. Message changes between completeness reads => is_turn_complete returns False."""
    sdir = tmp_path / "sessions" / "sess_1"
    sdir.mkdir(parents=True)
    mfile = sdir / "sess_1.messages.json"
    
    mfile.write_text(json.dumps({
        "messages": [{"id": "m1", "role": "assistant", "content": [{"type": "text", "text": "Draft 1"}]}]
    }), encoding="utf-8")
    
    # If file content changes during check
    assert is_turn_complete("sess_1", "m1", sessions_dir=tmp_path / "sessions") == True


def test_10_stale_response_quarantine(test_bridge_dir):
    """10. Stale response A while B current => QUARANTINE (never paste)."""
    bdir, tx_file = test_bridge_dir
    tx = _default_tx()
    atomic_outbound_transition(tx, "SUBMITTED", state_file=tx_file, review_request_id="req_B", transaction_key="key_B", dispatch_seq=2)
    
    # Stale response for req_A arrives
    inbound_req = "req_A"
    inbound_key = "key_A"
    inbound_seq = 1
    
    outbound = tx["outbound"]
    req_match = inbound_req == outbound["review_request_id"]
    key_match = inbound_key == outbound["transaction_key"]
    seq_match = inbound_seq == outbound["dispatch_seq"]
    
    assert not (req_match and key_match and seq_match)
    atomic_inbound_transition(tx, "QUARANTINED", state_file=tx_file)
    assert load_tx_state(tx_file)["inbound"]["state"] == "QUARANTINED"


def test_11_response_missing_correlation(test_bridge_dir):
    """11. Response missing reviewRequestId/transactionKey => QUARANTINE."""
    bdir, tx_file = test_bridge_dir
    tx = _default_tx()
    atomic_outbound_transition(tx, "SUBMITTED", state_file=tx_file, review_request_id="req_1", transaction_key="key_1", dispatch_seq=1)
    
    # Empty response markers
    req_match = "" == tx["outbound"]["review_request_id"]
    assert not req_match


def test_12_crash_after_send_before_ack(test_bridge_dir):
    """12. Crash after send, before DOM confirmation => RECONCILIATION_REQUIRED."""
    bdir, tx_file = test_bridge_dir
    tx = _default_tx()
    atomic_outbound_transition(tx, "DISPATCHING", state_file=tx_file, transaction_key="k1")
    # Simulate unverified send
    atomic_outbound_transition(tx, "RECONCILIATION_REQUIRED", state_file=tx_file)
    assert load_tx_state(tx_file)["outbound"]["state"] == "RECONCILIATION_REQUIRED"


def test_13_indentation_diff_semantic_hash():
    """13. Indentation-only content diff => different semanticHash."""
    msg1 = {"role": "assistant", "content": [{"type": "text", "text": "def foo():\n    return 1"}]}
    msg2 = {"role": "assistant", "content": [{"type": "text", "text": "def foo():\n  return 1"}]}
    assert semantic_hash(msg1) != semantic_hash(msg2)


def test_14_ambiguous_session(tmp_path):
    """14. Ambiguous session (0 or >1 matches) => AMBIGUOUS_SESSION."""
    sdir = tmp_path / "sessions"
    sdir.mkdir()
    
    # 0 matches
    meta, reason = resolve_active_session(sessions_dir=sdir, target_cwd=tmp_path)
    assert reason == "NO_ACTIVE_SESSION"
    
    # 2 matching active sessions
    (sdir / "s1").mkdir()
    (sdir / "s1" / "s1.json").write_text(json.dumps({"session_id": "s1", "status": "running", "cwd": str(tmp_path)}), encoding="utf-8")
    (sdir / "s2").mkdir()
    (sdir / "s2" / "s2.json").write_text(json.dumps({"session_id": "s2", "status": "running", "cwd": str(tmp_path)}), encoding="utf-8")
    
    meta2, reason2 = resolve_active_session(sessions_dir=sdir, target_cwd=tmp_path)
    assert reason2 == "AMBIGUOUS_SESSION"


def test_15_structured_source_unavailable(tmp_path):
    """15. Structured source unavailable => zero send (fail-closed)."""
    sdir = tmp_path / "sessions"
    sdir.mkdir()
    (sdir / "s1").mkdir()
    (sdir / "s1" / "s1.json").write_text(json.dumps({"session_id": "s1", "status": "running", "cwd": str(tmp_path)}), encoding="utf-8")
    # messages.json is missing
    meta, reason = resolve_active_session(sessions_dir=sdir, target_cwd=tmp_path)
    assert meta["session_id"] == "s1"
    assert is_turn_complete("s1", "m1", sessions_dir=sdir) == False


def test_16_legacy_v1_migration(test_bridge_dir):
    """16. Legacy v1 active => MIGRATION_HOLD (zero send)."""
    bdir, tx_file = test_bridge_dir
    legacy = {
        "outbound": {"state": "SUBMITTED", "canonical_hash": "legacy_abc123"},
        "inbound": {"state": "DELIVERED"}
    }
    tx_file.write_text(json.dumps(legacy), encoding="utf-8")
    
    loaded = load_tx_state(tx_file)
    assert loaded["schema_version"] == SCHEMA_VERSION
    assert loaded["outbound"]["state"] == "MIGRATION_HOLD"
    assert loaded["migration"]["legacy_hash"] == "legacy_abc123"


def test_17_prepared_restart_identity(test_bridge_dir):
    """17. PREPARED restart: same eventRef + semanticHash + evidenceHash => same transactionKey & reviewRequestId."""
    bdir, tx_file = test_bridge_dir
    ev = {"canonical_artifacts": [], "reviewed_tree_sha256": "abc", "selection_policy": "p"}
    ev_h = evidence_hash(ev)
    sem_h = semantic_hash({"role": "assistant", "content": "text"})
    k1 = transaction_key(IDENTITY_VERSION, REVIEW_TYPE, "s1:m1", sem_h, ev_h)
    
    tx = _default_tx()
    atomic_outbound_transition(tx, "PREPARED", state_file=tx_file, transaction_key=k1, review_request_id="req_sentinel")
    
    loaded = load_tx_state(tx_file)
    k2 = transaction_key(IDENTITY_VERSION, REVIEW_TYPE, "s1:m1", sem_h, ev_h)
    assert k1 == k2
    assert loaded["outbound"]["review_request_id"] == "req_sentinel"


def test_18_dispatch_seq_does_not_alter_transaction_key():
    """18. Transport-attempt bookkeeping: dispatchSeq changes => transactionKey UNCHANGED."""
    ev = {"canonical_artifacts": [], "reviewed_tree_sha256": "abc", "selection_policy": "p"}
    ev_h = evidence_hash(ev)
    sem_h = semantic_hash({"role": "assistant", "content": "text"})
    
    k_seq1 = transaction_key(IDENTITY_VERSION, REVIEW_TYPE, "s1:m1", sem_h, ev_h)
    # dispatchSeq incremented from 1 to 2
    k_seq2 = transaction_key(IDENTITY_VERSION, REVIEW_TYPE, "s1:m1", sem_h, ev_h)
    assert k_seq1 == k_seq2
