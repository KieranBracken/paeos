"""Synthetic signatures only; exercise the canonical producer and durable fence."""

import copy
import hashlib
import importlib.util
import json
from dataclasses import replace
from datetime import UTC, datetime

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from kernel.ledger import InMemoryLedgerStore, Ledger
from kernel.ledger_sqlite import SqliteLedgerStore
from runtime.autonomy.admission_send_fence import (
    AdmissionNotCurrent,
    AdmissionSendFence,
    DuplicateSendOperation,
    SendOperation,
    SendOutcome,
    SendSettlementError,
)

NOW = datetime(2026, 10, 19, 12, tzinfo=UTC)
END = "2026-10-20T12:00:00+00:00"


def test_parent_tool_claim_requires_dedicated_versioned_authority():
    from runtime.autonomy.admission_authority import AdmissionAuthority

    assert callable(getattr(AdmissionAuthority, "claim_parent_tool_read", None)), (
        "missing dedicated parent-tool claim verifier/producer"
    )
    ledger, authority, *_ = setup_authority()
    before = ledger.head_hash()
    with pytest.raises(ValueError):
        authority.claim_parent_tool_read(b'{"ready":true}')
    assert ledger.head_hash() == before


BINDINGS = dict(
    goal_id="mission",
    task_id="task",
    run_id="run",
    session_id="session",
    stage="BUILD",
    role="BUILDER",
    workspace_id="workspace",
    contract_digest="a" * 64,
    scope_digest="b" * 64,
    route_id="destination",
    route_digest="c" * 64,
    root_allocation_id="allocation",
)


def signed(body, key):
    body = dict(body)
    body["signature"] = key.sign(
        json.dumps(
            body, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
        ).encode()
    ).hex()
    return body


def setup_authority(ledger=None, *, root=None):
    assert importlib.util.find_spec("runtime.autonomy.admission_authority"), (
        "missing concrete authority producer/verifier"
    )
    from runtime.autonomy.admission_authority import (
        AdmissionAuthority,
        EnrolledIdentity,
        FrozenTrust,
    )

    root = root or Ed25519PrivateKey.generate()
    issuer, receiver = [Ed25519PrivateKey.generate() for _ in range(2)]
    grant = signed(
        dict(
            schema=1,
            record_kind="ROOT_GRANT",
            issuer_id="root",
            grant_id="grant",
            delegate_id="issuer",
            reconciler_id="receiver",
            domain_tag="TEST",
            expires_at=END,
            max_frames=2,
            **BINDINGS,
        ),
        root,
    )
    trust = FrozenTrust(
        roots=(EnrolledIdentity("root", root.public_key().public_bytes_raw()),),
        identities=(
            EnrolledIdentity("issuer", issuer.public_key().public_bytes_raw()),
            EnrolledIdentity("receiver", receiver.public_key().public_bytes_raw()),
        ),
        grants=(json.dumps(grant).encode(),),
    )
    ledger = ledger or Ledger(InMemoryLedgerStore())
    authority = AdmissionAuthority(ledger, trust=trust, domain_tag="TEST", now=lambda: NOW)
    common = dict(grant_id="grant", expires_at=END, **BINDINGS)
    policy = authority.issue(
        "DISCLOSURE_POLICY_CURRENT",
        dict(
            common,
            policy_id="policy",
            revision=1,
            frame_digests=[hashlib.sha256(b"frame").hexdigest()],
        ),
        issuer_id="issuer",
        signer=issuer.sign,
    )
    admission = authority.issue(
        "ADMISSION_CURRENT",
        dict(
            common,
            admission_ref="admission",
            epoch=1,
            logical_job_id="job",
            policy_id="policy",
            policy_revision=1,
            policy_digest=policy["digest"],
        ),
        issuer_id="issuer",
        signer=issuer.sign,
    )
    fence = AdmissionSendFence(ledger, authority=authority, domain_tag="TEST", now=lambda: NOW)
    op = SendOperation(
        admission_ref="admission",
        expected_epoch=1,
        request_id="request",
        frame=b"frame",
        operation_kind="PROVIDER_FRAME",
        frame_ordinal=0,
        **BINDINGS,
    )
    return ledger, authority, fence, op, policy, admission, issuer, receiver, trust


def test_signed_producer_authorizes_exact_frame_and_separate_launch():
    ledger, authority, fence, op, policy, admission, *_ = setup_authority()
    assert authority.verify_policy(policy) and authority.verify_admission(admission)
    assert authority.authorize_frame(
        admission, policy, frame_digest=op.frame_digest, route_digest=op.route_digest
    )
    lease = fence.acquire_send_lease(op)
    assert ledger.read()[-1].event.payload["root_allocation_id"] == "allocation"
    launch = fence.acquire_send_lease(replace(op, operation_kind="WORKER_LAUNCH", frame_ordinal=0))
    assert launch.lease_id != lease.lease_id
    with pytest.raises(DuplicateSendOperation):
        fence.acquire_send_lease(replace(op, request_id="new-uuid"))
    fence.acquire_send_lease(replace(op, frame_ordinal=1))
    with pytest.raises(AdmissionNotCurrent):
        fence.acquire_send_lease(replace(op, frame_ordinal=2))


@pytest.mark.parametrize("field", list(BINDINGS))
def test_each_parent_binding_denies_mismatch(field):
    _, _, fence, op, *_ = setup_authority()
    with pytest.raises((AdmissionNotCurrent, ValueError)):
        fence.acquire_send_lease(
            replace(op, **{field: "d" * 64 if field.endswith("digest") else "other"})
        )


@pytest.mark.parametrize(
    "mutation", ["signature", "issuer_id", "scope_digest", "grant_id", "expires_at"]
)
def test_forgery_substitution_and_stale_proofs_denied(mutation):
    ledger, authority, _, _, _, admission, *_ = setup_authority()
    changed = copy.deepcopy(admission)
    changed[mutation] = "forged"
    before = len(ledger.read())
    assert not authority.verify_admission(changed)
    with pytest.raises(ValueError):
        authority.append_signed(changed)
    assert len(ledger.read()) == before


def test_missing_enrollment_and_attacker_signer_fail_closed():
    ledger, _, _, _, _, admission, _, _, _ = setup_authority()
    from runtime.autonomy.admission_authority import AdmissionAuthority, FrozenTrust

    empty = AdmissionAuthority(ledger, trust=FrozenTrust(), domain_tag="TEST", now=lambda: NOW)
    assert not empty.verify_admission(admission)
    bad = signed(
        {k: v for k, v in admission.items() if k != "signature"}, Ed25519PrivateKey.generate()
    )
    assert not empty.verify_admission(bad)


@pytest.mark.parametrize(
    "kind", ["ADMISSION_REVOKED", "DISCLOSURE_POLICY_REVOKED", "AUTHORITY_GRANT_REVOKED"]
)
def test_authenticated_revocation_is_terminal(kind):
    _ledger, authority, fence, op, policy, admission, issuer, _receiver, _trust = setup_authority()
    target = (
        {"admission_ref": "admission", "epoch": 1}
        if kind == "ADMISSION_REVOKED"
        else {"policy_id": "policy", "revision": 1}
    )
    if kind == "AUTHORITY_GRANT_REVOKED":
        # Root revocations must use a root signer, not the delegate.
        with pytest.raises(ValueError):
            authority.issue(
                kind, dict(grant_id="grant", expires_at=END), issuer_id="issuer", signer=issuer.sign
            )
        return
    authority.issue(
        kind,
        dict(target, grant_id="grant", expires_at=END, **BINDINGS),
        issuer_id="issuer",
        signer=issuer.sign,
    )
    with pytest.raises(AdmissionNotCurrent):
        fence.acquire_send_lease(op)
    with pytest.raises(ValueError):
        authority.append_signed(admission if kind == "ADMISSION_REVOKED" else policy)


def test_restart_reconciliation_requires_authenticated_exact_return_bytes(tmp_path):
    store = SqliteLedgerStore(tmp_path / "ledger.db")
    ledger, authority, fence, op, _, _, issuer, receiver, trust = setup_authority(Ledger(store))
    lease = fence.acquire_send_lease(op)
    claim = ledger.read()[-1].event.payload
    ledger.close()
    store.close()
    store = SqliteLedgerStore(tmp_path / "ledger.db")
    reopened = Ledger(store)
    from runtime.autonomy.admission_authority import AdmissionAuthority

    authority = AdmissionAuthority(reopened, trust=trust, domain_tag="TEST", now=lambda: NOW)
    fence = AdmissionSendFence(reopened, authority=authority, domain_tag="TEST", now=lambda: NOW)
    assert fence.query_send_claim(lease.lease_id)["state"] == "CLAIMED"
    with pytest.raises(DuplicateSendOperation):
        fence.acquire_send_lease(replace(op, request_id="retry"))
    evidence = signed(
        dict(
            schema=1,
            record_kind="SEND_EVIDENCE",
            issuer_id="receiver",
            domain_tag="TEST",
            grant_id="grant",
            lease_id=lease.lease_id,
            claim_digest=hashlib.sha256(
                json.dumps(
                    claim, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
                ).encode()
            ).hexdigest(),
            outcome="RETURNED",
            outcome_ref=hashlib.sha256(b"actual response").hexdigest(),
            expires_at=END,
        ),
        receiver,
    )
    with pytest.raises(SendSettlementError):
        fence.reconcile_send_claim(lease.lease_id, evidence, outcome_bytes=b"fabricated")
    forged = signed({k: v for k, v in evidence.items() if k != "signature"}, issuer)
    with pytest.raises(SendSettlementError):
        fence.reconcile_send_claim(lease.lease_id, forged, outcome_bytes=b"actual response")
    fence.reconcile_send_claim(lease.lease_id, evidence, outcome_bytes=b"actual response")
    assert fence.query_send_claim(lease.lease_id)["outcome"] == "RETURNED"
    with pytest.raises(SendSettlementError):
        fence.reconcile_send_claim(lease.lease_id, evidence, outcome_bytes=b"actual response")
    reopened.close()
    store.close()


def test_live_object_cannot_fabricate_returned_and_unknown_is_consumed():
    _, _, fence, op, *_ = setup_authority()
    lease = fence.acquire_send_lease(op)
    with pytest.raises(SendSettlementError):
        fence.finish_send_lease(lease, SendOutcome.RETURNED, outcome_ref="d" * 64)
    fence.finish_send_lease(lease, SendOutcome.UNKNOWN)
    assert fence.query_send_claim(lease.lease_id)["outcome"] == "UNKNOWN"
    with pytest.raises(DuplicateSendOperation):
        fence.acquire_send_lease(op)


def unsigned(record):
    return {k: v for k, v in record.items() if k != "signature"}


def receipt(claim, receiver, *, outcome="UNKNOWN", data=None):
    return signed(
        dict(
            schema=1,
            record_kind="SEND_EVIDENCE",
            issuer_id="receiver",
            domain_tag="TEST",
            grant_id="grant",
            lease_id=claim["lease_id"],
            claim_digest=hashlib.sha256(
                json.dumps(
                    claim, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
                ).encode()
            ).hexdigest(),
            outcome=outcome,
            outcome_ref=hashlib.sha256(data).hexdigest() if data is not None else None,
            expires_at=END,
        ),
        receiver,
    )


@pytest.mark.parametrize("kind", ["ADMISSION_REVOKED", "DISCLOSURE_POLICY_REVOKED"])
def test_replayed_signed_record_cannot_resurrect_revoked_identity(kind):
    from kernel.ledger import Event

    ledger, authority, fence, op, policy, admission, issuer, *_ = setup_authority()
    record = admission if kind == "ADMISSION_REVOKED" else policy
    authority.issue(kind, unsigned(record), issuer_id="issuer", signer=issuer.sign)
    # A valid old signature appended after revocation is still not current authority.
    ledger.append(Event(1, record["record_kind"], record), domain_tag="TEST")
    with pytest.raises(AdmissionNotCurrent):
        fence.acquire_send_lease(op)


def test_domain_and_canonical_ledger_binding_cannot_be_substituted():
    ledger, authority, _, _, *_ = setup_authority()
    with pytest.raises(ValueError):
        AdmissionSendFence(ledger, authority=authority, domain_tag="PRODUCTION")
    with pytest.raises(ValueError):
        AdmissionSendFence(Ledger(InMemoryLedgerStore()), authority=authority, domain_tag="TEST")


def test_signed_root_grant_revocation_denies_claim_and_new_records():
    root = Ed25519PrivateKey.generate()
    ledger, authority, fence, op, _, admission, issuer, *_ = setup_authority(root=root)
    authority.issue(
        "AUTHORITY_GRANT_REVOKED",
        dict(grant_id="grant", expires_at=END),
        issuer_id="root",
        signer=root.sign,
    )
    with pytest.raises(AdmissionNotCurrent):
        fence.acquire_send_lease(op)
    with pytest.raises(ValueError):
        authority.issue(
            "ADMISSION_CURRENT",
            dict(unsigned(admission), epoch=2),
            issuer_id="issuer",
            signer=issuer.sign,
        )
    assert len(ledger.read()) == 3


@pytest.mark.parametrize(
    "changed",
    [dict(max_frames=3), dict(session_id="new-session"), dict(root_allocation_id="new-allocation")],
)
def test_worker_cannot_change_root_grant_or_signer(changed):
    from runtime.autonomy.admission_authority import AdmissionAuthority

    ledger, authority, _, _, _, admission, issuer, _, trust = setup_authority()
    grant = dict(unsigned(json.loads(trust.grants[0])), **changed)
    forged = replace(trust, grants=(json.dumps(signed(grant, issuer)).encode(),))
    bad = AdmissionAuthority(ledger, trust=forged, domain_tag="TEST", now=lambda: NOW)
    assert not bad.verify_admission(admission)
    assert not authority.verify_admission(signed(unsigned(admission), Ed25519PrivateKey.generate()))


@pytest.mark.parametrize("kind", ["ADMISSION_CURRENT", "DISCLOSURE_POLICY_CURRENT"])
def test_genuinely_signed_expired_records_and_revision_rollback_deny(kind):
    ledger, authority, _, _, policy, admission, issuer, *_ = setup_authority()
    original = admission if kind == "ADMISSION_CURRENT" else policy
    before = len(ledger.read())
    with pytest.raises(ValueError):
        authority.issue(
            kind,
            dict(unsigned(original), expires_at="2026-10-18T00:00:00+00:00"),
            issuer_id="issuer",
            signer=issuer.sign,
        )
    with pytest.raises(ValueError):
        authority.append_signed(original)
    assert len(ledger.read()) == before


def test_new_policy_revision_invalidates_old_admission_until_explicit_rebind():
    ledger, authority, fence, op, policy, admission, issuer, *_ = setup_authority()
    new = authority.issue(
        "DISCLOSURE_POLICY_CURRENT",
        dict(unsigned(policy), revision=2),
        issuer_id="issuer",
        signer=issuer.sign,
    )
    with pytest.raises(AdmissionNotCurrent):
        fence.acquire_send_lease(op)
    authority.issue(
        "ADMISSION_CURRENT",
        dict(unsigned(admission), epoch=2, policy_revision=2, policy_digest=new["digest"]),
        issuer_id="issuer",
        signer=issuer.sign,
    )
    with pytest.raises(AdmissionNotCurrent):
        fence.acquire_send_lease(op)
    fence.acquire_send_lease(replace(op, expected_epoch=2))
    assert len(ledger.read()) == 5


def test_new_admission_identity_does_not_reset_allocation_after_restart(tmp_path):
    from runtime.autonomy.admission_authority import AdmissionAuthority

    store = SqliteLedgerStore(tmp_path / "ledger.db")
    ledger, authority, fence, op, _, admission, issuer, _, trust = setup_authority(Ledger(store))
    fence.acquire_send_lease(op)
    authority.issue(
        "ADMISSION_CURRENT",
        dict(unsigned(admission), admission_ref="new-admission", logical_job_id="new-job"),
        issuer_id="issuer",
        signer=issuer.sign,
    )
    ledger.close()
    store.close()
    store = SqliteLedgerStore(tmp_path / "ledger.db")
    ledger = Ledger(store)
    authority = AdmissionAuthority(ledger, trust=trust, domain_tag="TEST", now=lambda: NOW)
    fence = AdmissionSendFence(ledger, authority=authority, domain_tag="TEST", now=lambda: NOW)
    with pytest.raises(DuplicateSendOperation):
        fence.acquire_send_lease(replace(op, admission_ref="new-admission", request_id="new-uuid"))
    fence.acquire_send_lease(replace(op, admission_ref="new-admission", frame_ordinal=1))
    with pytest.raises(AdmissionNotCurrent):
        fence.acquire_send_lease(replace(op, admission_ref="new-admission", frame_ordinal=2))
    ledger.close()
    store.close()


def test_same_root_allocation_cannot_be_expanded_by_replacing_grant(tmp_path):
    from runtime.autonomy.admission_authority import AdmissionAuthority

    root = Ed25519PrivateKey.generate()
    ledger, _, fence, op, _, _admission, _, _, trust = setup_authority(root=root)
    fence.acquire_send_lease(op)
    grant = signed(dict(unsigned(json.loads(trust.grants[0])), max_frames=3), root)
    expanded = AdmissionAuthority(
        ledger,
        trust=replace(trust, grants=(json.dumps(grant).encode(),)),
        domain_tag="TEST",
        now=lambda: NOW,
    )
    other = AdmissionSendFence(ledger, authority=expanded, domain_tag="TEST", now=lambda: NOW)
    with pytest.raises(AdmissionNotCurrent):
        other.acquire_send_lease(replace(op, frame_ordinal=2))


def test_unknown_authenticated_reconciliation_is_terminal_and_cannot_claim_bytes():
    ledger, _, fence, op, _, _, _, receiver, _ = setup_authority()
    lease = fence.acquire_send_lease(op)
    claim = ledger.read()[-1].event.payload
    evidence = receipt(claim, receiver)
    with pytest.raises(SendSettlementError):
        fence.reconcile_send_claim(lease.lease_id, evidence, outcome_bytes=b"invented")
    fence.reconcile_send_claim(lease.lease_id, evidence)
    assert fence.query_send_claim(lease.lease_id)["outcome"] == "UNKNOWN"
    with pytest.raises(SendSettlementError):
        fence.reconcile_send_claim(
            lease.lease_id,
            receipt(claim, receiver, outcome="RETURNED", data=b"response"),
            outcome_bytes=b"response",
        )
    with pytest.raises(DuplicateSendOperation):
        fence.acquire_send_lease(replace(op, request_id="retry"))


def test_claim_then_revocation_still_allows_bound_return_evidence():
    ledger, authority, fence, op, _, admission, issuer, receiver, _ = setup_authority()
    lease = fence.acquire_send_lease(op)
    claim = ledger.read()[-1].event.payload
    authority.issue(
        "ADMISSION_REVOKED", unsigned(admission), issuer_id="issuer", signer=issuer.sign
    )
    fence.reconcile_send_claim(
        lease.lease_id,
        receipt(claim, receiver, outcome="RETURNED", data=b"response"),
        outcome_bytes=b"response",
    )
    assert fence.query_send_claim(lease.lease_id)["outcome"] == "RETURNED"
    with pytest.raises(AdmissionNotCurrent):
        fence.acquire_send_lease(replace(op, frame_ordinal=1))


def test_authenticated_sink_return_stays_unresolved_until_receiver_receipt():
    ledger, _, fence, op, *_ = setup_authority()
    sent = []

    def sink(frame):
        sent.append(frame)
        return b"response"

    assert fence.send_once(op, sink) == b"response"
    assert sent == [b"frame"]
    assert ledger.read()[-1].event.kind == "ADMISSION_SEND_CLAIMED"
    with pytest.raises(DuplicateSendOperation):
        fence.send_once(op, sink)
    assert len(sent) == 1


@pytest.mark.parametrize(
    "overrides",
    [
        dict(operation_kind=None),
        dict(frame_ordinal=True),
        dict(frame_ordinal=-1),
        dict(session_id=None),
        dict(scope_digest=None),
        dict(frame=b"different"),
    ],
)
def test_incomplete_parent_frame_cannot_send(overrides):
    ledger, _, fence, op, *_ = setup_authority()
    before = len(ledger.read())
    with pytest.raises((AdmissionNotCurrent, ValueError)):
        fence.acquire_send_lease(replace(op, **overrides))
    assert len(ledger.read()) == before


def test_empty_production_trust_denies_before_sink():
    from runtime.autonomy.admission_authority import AdmissionAuthority, FrozenTrust

    ledger = Ledger(InMemoryLedgerStore())
    authority = AdmissionAuthority(ledger, trust=FrozenTrust())
    fence = AdmissionSendFence(ledger, authority=authority)
    _, _, _, op, *_ = setup_authority()
    sent = []
    with pytest.raises(AdmissionNotCurrent):
        fence.send_once(op, sent.append)
    assert sent == [] and ledger.read() == []


def test_reissued_records_cannot_reallocate_an_existing_root_allowance():
    from runtime.autonomy.admission_authority import AdmissionAuthority

    root = Ed25519PrivateKey.generate()
    ledger, _, fence, op, policy, _, issuer, _, trust = setup_authority(root=root)
    fence.acquire_send_lease(op)
    grant = signed(dict(unsigned(json.loads(trust.grants[0])), max_frames=3), root)
    expanded = AdmissionAuthority(
        ledger,
        trust=replace(trust, grants=(json.dumps(grant).encode(),)),
        domain_tag="TEST",
        now=lambda: NOW,
    )
    with pytest.raises(ValueError):
        expanded.issue(
            "DISCLOSURE_POLICY_CURRENT",
            dict(unsigned(policy), policy_id="new-policy"),
            issuer_id="issuer",
            signer=issuer.sign,
        )


def test_valid_old_admission_and_policy_cannot_be_replayed_after_new_versions():
    from kernel.ledger import Event

    ledger, authority, fence, op, policy, admission, issuer, *_ = setup_authority()
    new = authority.issue(
        "DISCLOSURE_POLICY_CURRENT",
        dict(unsigned(policy), revision=2),
        issuer_id="issuer",
        signer=issuer.sign,
    )
    authority.issue(
        "ADMISSION_CURRENT",
        dict(unsigned(admission), epoch=2, policy_revision=2, policy_digest=new["digest"]),
        issuer_id="issuer",
        signer=issuer.sign,
    )
    ledger.append(Event(1, "DISCLOSURE_POLICY_CURRENT", policy), domain_tag="TEST")
    ledger.append(Event(1, "ADMISSION_CURRENT", admission), domain_tag="TEST")
    with pytest.raises(AdmissionNotCurrent):
        fence.acquire_send_lease(op)


class PausingClaimStore(SqliteLedgerStore):
    """Only synthetic SQLite claim commit is paused to force the CAS race."""

    def __init__(self, path, ready, resume):
        super().__init__(path)
        self.ready, self.resume = ready, resume

    def append_row_if_head(self, row, expected_head_hash):
        if row.event.kind == "ADMISSION_SEND_CLAIMED":
            self.ready.set()
            if not self.resume.wait(10):
                raise TimeoutError("revoker did not release sender")
        super().append_row_if_head(row, expected_head_hash)


def signed_process_send(database, trust, op, gate, results, sink_path, pause=None):
    from pathlib import Path

    from runtime.autonomy.admission_authority import AdmissionAuthority

    store = PausingClaimStore(database, *pause) if pause else SqliteLedgerStore(database)
    ledger = Ledger(store, writer_id="signed-process-test")
    authority = AdmissionAuthority(ledger, trust=trust, domain_tag="TEST", now=lambda: NOW)
    fence = AdmissionSendFence(ledger, authority=authority, domain_tag="TEST", now=lambda: NOW)

    def sink(frame):
        with Path(sink_path).open("ab") as stream:
            stream.write(frame + b"\n")
        return b"local-reply"

    try:
        if gate is not None:
            gate.wait(10)
        fence.send_once(op, sink)
        results.put("SENT")
    except (DuplicateSendOperation, AdmissionNotCurrent):
        results.put("DENIED")
    except Exception as exc:
        results.put(("ERROR", type(exc).__name__))
    finally:
        ledger.close()
        store.close()


def signed_process_revoke(database, trust, revocation, ready, resume, results):
    from runtime.autonomy.admission_authority import AdmissionAuthority

    try:
        if not ready.wait(10):
            raise TimeoutError("sender never validated")
        store = SqliteLedgerStore(database)
        ledger = Ledger(store, writer_id="signed-process-test")
        try:
            authority = AdmissionAuthority(ledger, trust=trust, domain_tag="TEST", now=lambda: NOW)
            authority.append_signed(revocation)
            results.put("REVOKED")
        finally:
            ledger.close()
            store.close()
    except Exception as exc:
        results.put(("ERROR", type(exc).__name__))
    finally:
        resume.set()


def join_processes(processes):
    try:
        for process in processes:
            process.start()
        for process in processes:
            process.join(15)
        assert all(process.exitcode == 0 for process in processes)
    finally:
        for process in processes:
            if process.is_alive():
                process.terminate()
                process.join(5)


def test_authenticated_two_process_claims_send_exactly_once(tmp_path):
    import multiprocessing

    database = tmp_path / "ledger.db"
    sink = tmp_path / "local-sink"
    store = SqliteLedgerStore(database)
    ledger = Ledger(store, writer_id="signed-process-test")
    _, _, _, op, _, _, _, _, trust = setup_authority(ledger)
    ledger.close()
    store.close()
    context = multiprocessing.get_context("spawn")
    gate = context.Barrier(2)
    results = context.Queue()
    processes = [
        context.Process(
            target=signed_process_send,
            args=(str(database), trust, replace(op, request_id=str(i)), gate, results, str(sink)),
        )
        for i in range(2)
    ]
    join_processes(processes)
    outcomes = [results.get(timeout=5) for _ in processes]
    assert sorted(outcomes) == ["DENIED", "SENT"]
    assert sink.read_bytes() == b"frame\n"
    store = SqliteLedgerStore(database)
    ledger = Ledger(store, writer_id="signed-process-test")
    assert sum(r.event.kind == "ADMISSION_SEND_CLAIMED" for r in ledger.read()) == 1
    assert ledger.verify_chain() == ledger.head_hash()
    ledger.close()
    store.close()
    results.close()
    results.join_thread()


@pytest.mark.parametrize(
    "kind", ["ADMISSION_REVOKED", "DISCLOSURE_POLICY_REVOKED", "AUTHORITY_GRANT_REVOKED"]
)
def test_authenticated_revocation_wins_between_validation_and_claim(tmp_path, kind):
    import multiprocessing

    root = Ed25519PrivateKey.generate()
    database = tmp_path / "ledger.db"
    sink = tmp_path / "local-sink"
    store = SqliteLedgerStore(database)
    ledger = Ledger(store, writer_id="signed-process-test")
    _, _, _, op, policy, admission, issuer, _, trust = setup_authority(ledger, root=root)
    target = policy if kind == "DISCLOSURE_POLICY_REVOKED" else admission
    body = dict(unsigned(target), record_kind=kind)
    if kind == "AUTHORITY_GRANT_REVOKED":
        body["issuer_id"] = "root"
    revoke = signed(body, root if kind == "AUTHORITY_GRANT_REVOKED" else issuer)
    ledger.close()
    store.close()
    context = multiprocessing.get_context("spawn")
    ready = context.Event()
    resume = context.Event()
    results = context.Queue()
    sender = context.Process(
        target=signed_process_send,
        args=(str(database), trust, op, None, results, str(sink), (ready, resume)),
    )
    revoker = context.Process(
        target=signed_process_revoke, args=(str(database), trust, revoke, ready, resume, results)
    )
    join_processes([sender, revoker])
    assert sorted(results.get(timeout=5) for _ in range(2)) == ["DENIED", "REVOKED"]
    assert not sink.exists()
    store = SqliteLedgerStore(database)
    ledger = Ledger(store, writer_id="signed-process-test")
    assert not any(r.event.kind == "ADMISSION_SEND_CLAIMED" for r in ledger.read())
    assert ledger.read()[-1].event.kind == kind
    assert ledger.verify_chain() == ledger.head_hash()
    ledger.close()
    store.close()
    results.close()
    results.join_thread()


def test_launch_preflight_uses_parent_claim_identity():
    _, _, fence, op, *_ = setup_authority()
    fence.acquire_send_lease(op)
    fence.preflight(op.admission_ref, op.expected_epoch)
    fence.acquire_send_lease(replace(op, operation_kind="WORKER_LAUNCH"))
    with pytest.raises(DuplicateSendOperation):
        fence.preflight(op.admission_ref, op.expected_epoch)


def test_query_rejects_unsigned_returned_settlement():
    from kernel.ledger import Event

    ledger, _, fence, op, *_ = setup_authority()
    lease = fence.acquire_send_lease(op)
    ledger.append(
        Event(
            1,
            "ADMISSION_SEND_SETTLED",
            {
                "lease_id": lease.lease_id,
                "logical_job_id": lease.logical_job_id,
                "outcome": "RETURNED",
                "outcome_ref": "a" * 64,
            },
        ),
        domain_tag="TEST",
    )
    with pytest.raises(SendSettlementError):
        fence.query_send_claim(lease.lease_id)


@pytest.mark.parametrize(
    "field,value", [("signature", None), ("signature", b"invalid"), ("expires_at", None)]
)
def test_malformed_envelopes_raise_value_error_without_append(field, value):
    ledger, authority, _, _, _, admission, issuer, *_ = setup_authority()
    record = dict(unsigned(admission), **{field: value})
    if field != "signature":
        record = signed(record, issuer)
    before = len(ledger.read())
    with pytest.raises(ValueError):
        authority.append_signed(record)
    assert len(ledger.read()) == before


@pytest.mark.parametrize(
    "kind,version", [("ADMISSION_REVOKED", "epoch"), ("DISCLOSURE_POLICY_REVOKED", "revision")]
)
def test_signed_revocation_rejects_boolean_version(kind, version):
    ledger, authority, _, _, policy, admission, issuer, *_ = setup_authority()
    record = admission if kind == "ADMISSION_REVOKED" else policy
    before = len(ledger.read())
    with pytest.raises(ValueError):
        authority.issue(
            kind, dict(unsigned(record), **{version: True}), issuer_id="issuer", signer=issuer.sign
        )
    assert len(ledger.read()) == before


def test_authenticated_unknown_remains_consumed_after_restart(tmp_path):
    from runtime.autonomy.admission_authority import AdmissionAuthority

    database = tmp_path / "ledger.db"
    store = SqliteLedgerStore(database)
    ledger, _, fence, op, _, _, _, receiver, trust = setup_authority(Ledger(store))
    lease = fence.acquire_send_lease(op)
    claim = ledger.read()[-1].event.payload
    ledger.close()
    store.close()
    store = SqliteLedgerStore(database)
    ledger = Ledger(store)
    authority = AdmissionAuthority(ledger, trust=trust, domain_tag="TEST", now=lambda: NOW)
    fence = AdmissionSendFence(ledger, authority=authority, domain_tag="TEST", now=lambda: NOW)
    fence.reconcile_send_claim(lease.lease_id, receipt(claim, receiver))
    ledger.close()
    store.close()
    store = SqliteLedgerStore(database)
    ledger = Ledger(store)
    authority = AdmissionAuthority(ledger, trust=trust, domain_tag="TEST", now=lambda: NOW)
    fence = AdmissionSendFence(ledger, authority=authority, domain_tag="TEST", now=lambda: NOW)
    assert fence.query_send_claim(lease.lease_id)["outcome"] == "UNKNOWN"
    with pytest.raises(DuplicateSendOperation):
        fence.acquire_send_lease(replace(op, request_id="after-second-restart"))
    with pytest.raises(SendSettlementError):
        fence.reconcile_send_claim(
            lease.lease_id,
            receipt(claim, receiver, outcome="RETURNED", data=b"invented"),
            outcome_bytes=b"invented",
        )
    ledger.close()
    store.close()


# Independent wire fixtures: no production encoder, observer, artifact read or sink.
TOOL_PURPOSES = ("PARENT_TOOL_CLAIM_REQUEST", "PARENT_TOOL_OBSERVATION", "PARENT_TOOL_COMMIT_ACK")


def wire_json(value):
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
    ).encode("ascii")


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def tool_signed(body, key, *, prefix=None):
    if prefix is None:
        prefix = (
            b"PAEOS_PARENT_TOOL_GRANT/v2\0"
            if body.get("schema") == 2
            else ("PAEOS_" + body["purpose"] + "/v1\0").encode()
        )
    return wire_json({"body": body, "signature": key.sign(prefix + wire_json(body)).hex()})


def tool_rebuild(f, *, grant=None, policy=None, trust=None, now=NOW):
    from runtime.autonomy.admission_authority import AdmissionAuthority

    grant = f["grant"] if grant is None else grant
    policy = f["policy_bytes"] if policy is None else policy
    trust = trust or replace(f["trust"], grants=(f["base_raw"], tool_signed(grant, f["root"])))
    return AdmissionAuthority(
        f["ledger"],
        trust=trust,
        domain_tag="TEST",
        now=lambda: now,
        tool_policy_manifests=(policy,),
    )


def tool_fixture(ledger=None, *, raw=b"known synthetic text \xc2\xa3\n", policy_mutate=None):
    import base64

    from runtime.autonomy.admission_authority import EnrolledIdentity

    root, parent = Ed25519PrivateKey.generate(), Ed25519PrivateKey.generate()
    ledger, legacy, _, _, policy, admission, issuer, receiver, trust = setup_authority(
        ledger, root=root
    )
    manifest = dict(
        schema="paeos.disclosure-policy/2",
        policy_id="policy",
        revision=1,
        status="ACTIVE",
        founder_authority=dict(
            key_id="root", algorithm="Ed25519", signature_encoding="base64url-no-pad"
        ),
        issued_at="2026-10-19T00:00:00Z",
        expires_at="2026-10-20T12:00:00Z",
        revocation_mode="IMMEDIATE",
        classes=[
            dict(
                class_id="PUBLIC_ARTIFACT",
                data_class="PUBLIC",
                purpose_ids=["synthetic-audit"],
                scope=dict(
                    repository_ids=["synthetic-repository"],
                    scope_mode="EXACT_ARTIFACTS",
                    allowed_artifacts=[
                        dict(relative_path="docs/synthetic.txt", sha256=sha(raw), max_bytes=16384)
                    ],
                ),
                allowed_routes=[
                    dict(
                        provider_id="google",
                        model_id="synthetic-model-1",
                        model_family="gemini",
                        entitlement_class="FREE",
                        transport_profile_id="synthetic-transport",
                        external_operator_id="synthetic-operator",
                    )
                ],
                max_bundle_bytes=131072,
                max_artifacts=1,
                required_exclusions=[
                    "credentials",
                    "sentium",
                    "legacy_orca_credentials",
                    "unrelated_private_data",
                ],
                require_builder_auditor_family_distinct=True,
                require_a08=True,
                max_attempts=1,
                capability_ttl_seconds=60,
            )
        ],
        derivative_rules=[
            dict(
                rule_id="read-rule",
                class_id="PUBLIC_ARTIFACT",
                input_artifact_sha256s=[sha(raw)],
                input_data_class="PUBLIC",
                output_data_class="PUBLIC",
                tool_envelope_sha256="d" * 64,
                transformation_ids=["READ_APPROVED_ARTIFACT"],
                max_output_bytes=131072,
            )
        ],
    )
    if policy_mutate:
        policy_mutate(manifest)
    policy_signing = json.dumps(
        manifest, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    ).encode()
    manifest["founder_authority"]["signature"] = (
        base64.urlsafe_b64encode(root.sign(b"PAEOS-DISCLOSURE-POLICY-V2\0" + policy_signing))
        .rstrip(b"=")
        .decode()
    )
    policy_bytes = wire_json(manifest)
    base_raw = trust.grants[0]
    grant = dict(
        schema=2,
        record_kind="ROOT_GRANT",
        domain_tag="TEST",
        issuer_id="root",
        grant_id="tool-grant",
        issued_at=NOW.isoformat(),
        expires_at=END,
        parent_grant_id="grant",
        parent_grant_digest=sha(wire_json(json.loads(base_raw))),
        bindings=dict(BINDINGS),
        admission_ref="admission",
        admission_epoch=1,
        policy_id="policy",
        policy_revision=1,
        policy_digest=policy["digest"],
        policy_signer_id="root",
        signed_v2_manifest_sha256=sha(policy_bytes),
        derivative_rule_id="read-rule",
        parent_identity_sha256=sha(parent.public_key().public_bytes_raw()),
        tool_name="read_artifact",
        tool_envelope_sha256="d" * 64,
        tool_source_sha256="e" * 64,
        tool_protocol_version="mcp-v1",
        transformation="READ_APPROVED_ARTIFACT",
        transformation_version="read-v1",
        artifact_id="artifact",
        expected_input_sha256=sha(raw),
        max_operations=1,
        max_raw_bytes=16384,
        max_result_bytes=131072,
        start_window_seconds=30,
        purpose_delegations=[
            dict(
                purpose=p,
                purpose_version=1,
                signer_identity_id="issuer" if p == TOOL_PURPOSES[2] else "parent",
                public_key_sha256=sha(
                    (issuer if p == TOOL_PURPOSES[2] else parent).public_key().public_bytes_raw()
                ),
                expires_at=END,
            )
            for p in TOOL_PURPOSES
        ],
    )
    trust = replace(
        trust,
        identities=(
            *trust.identities,
            EnrolledIdentity("parent", parent.public_key().public_bytes_raw()),
        ),
    )
    f = dict(
        ledger=ledger,
        legacy=legacy,
        root=root,
        parent=parent,
        issuer=issuer,
        receiver=receiver,
        base_raw=base_raw,
        trust=trust,
        grant=grant,
        policy_bytes=policy_bytes,
        admission=admission,
        policy=policy,
        raw=raw,
    )
    f["authority"] = tool_rebuild(f)
    f["trust"] = f["authority"].trust
    f["request"] = tool_request(f)
    f["operation"] = json.loads(f["request"])["body"]["operation_id"]
    return f


def tool_request(f, *, grant=None, changes=None):
    g = grant or f["grant"]
    context = dict(
        bindings=copy.deepcopy(g["bindings"]),
        base_grant_id=g["parent_grant_id"],
        base_grant_digest=g["parent_grant_digest"],
        tool_grant_id=g["grant_id"],
        tool_grant_digest=sha(wire_json(g)),
        **{
            k: g[k]
            for k in (
                "admission_ref",
                "admission_epoch",
                "policy_id",
                "policy_revision",
                "policy_digest",
                "signed_v2_manifest_sha256",
                "derivative_rule_id",
            )
        },
    )
    body = dict(
        schema=1,
        purpose=TOOL_PURPOSES[0],
        purpose_version=1,
        domain_tag="TEST",
        issuer_id="parent",
        issued_at=NOW.isoformat(),
        expires_at=END,
        context=context,
        operation_id=sha(
            wire_json(
                dict(
                    root_allocation_id=g["bindings"]["root_allocation_id"],
                    operation_kind="PARENT_TOOL_READ",
                    ordinal=0,
                )
            )
        ),
        ordinal=0,
        request_id="request-1",
        mcp_id=7,
        arguments={"artifact_id": "artifact"},
        arguments_sha256=sha(wire_json({"artifact_id": "artifact"})),
        parent_boot_id="boot-1",
        parent_process_id="process-1",
        **{
            k: g[k]
            for k in (
                "tool_name",
                "artifact_id",
                "expected_input_sha256",
                "tool_envelope_sha256",
                "tool_source_sha256",
                "tool_protocol_version",
                "transformation",
                "transformation_version",
                "parent_identity_sha256",
                "max_raw_bytes",
                "max_result_bytes",
            )
        },
    )
    if changes:
        body.update(changes)
    return tool_signed(body, f["parent"])


def tool_observation(f, *, changes=None, outcome="RETURNED"):
    import base64

    req = json.loads(f["request"])["body"]
    claim = next(r for r in f["ledger"].read() if r.event.kind == "PARENT_TOOL_READ_CLAIMED")
    raw = f["raw"]
    inner = json.dumps(
        dict(artifact_id=req["artifact_id"], text=raw.decode(), sha256=sha(raw)), sort_keys=True
    )
    result = (
        wire_json(
            dict(
                jsonrpc="2.0",
                id=req["mcp_id"],
                result={"content": [{"type": "text", "text": inner}]},
            )
        )
        + b"\n"
    )
    body = dict(
        schema=1,
        purpose=TOOL_PURPOSES[1],
        purpose_version=1,
        domain_tag="TEST",
        issuer_id="parent",
        issued_at=NOW.isoformat(),
        expires_at=END,
        context=req["context"],
        operation_id=req["operation_id"],
        ordinal=0,
        request_sha256=sha(f["request"]),
        claim_seq=claim.seq,
        claim_row_hash=claim.row_hash,
        **{k: req[k] for k in ("parent_identity_sha256", "parent_boot_id", "parent_process_id")},
        effect_started_at=NOW.isoformat(),
        observed_at=NOW.isoformat(),
        outcome=outcome,
        error_code=None,
        actual_input_sha256=sha(raw),
        raw_length=len(raw),
        raw_b64=base64.b64encode(raw).decode(),
        result_sha256=sha(result),
        result_length=len(result),
        result_b64=base64.b64encode(result).decode(),
    )
    if outcome != "RETURNED":
        body.update(error_code="UNKNOWN" if outcome == "UNKNOWN" else "READ_FAILED")
        body.update(
            {
                k: None
                for k in (
                    "actual_input_sha256",
                    "raw_length",
                    "raw_b64",
                    "result_sha256",
                    "result_length",
                    "result_b64",
                )
            }
        )
    if changes:
        body.update(changes)
    return tool_signed(body, f["parent"]), result


def test_parent_tool_commits_exact_rows_and_independent_ack_readback():
    import base64
    from dataclasses import FrozenInstanceError

    f = tool_fixture()
    a, ledger = f["authority"], f["ledger"]
    seq = a.claim_parent_tool_read(f["request"])
    claim = ledger.read()[-1]
    assert seq == claim.seq == 3
    assert claim.event.kind == "PARENT_TOOL_READ_CLAIMED"
    assert set(claim.event.payload) == {
        "schema",
        "domain_tag",
        "operation_id",
        "ordinal",
        "request_b64",
        "request_sha256",
        "base_grant_b64",
        "tool_grant_b64",
        "authority_claimed_at",
        "start_deadline",
    }
    assert base64.b64decode(claim.event.payload["request_b64"]) == f["request"]
    assert base64.b64decode(claim.event.payload["tool_grant_b64"]) == f["trust"].grants[1]
    ack = a.issue_parent_tool_commit_ack(
        f["operation"], "CLAIM", issuer_id="issuer", signer=f["issuer"].sign
    )
    claim_view = a.verify_parent_tool_commit_ack(ack, expected_request_bytes=f["request"])
    assert claim_view.outcome == "UNRESOLVED" and claim_view.result_bytes is None
    assert claim_view.claim_row_hash == claim.row_hash
    obs, result = tool_observation(f)
    accepted = a.record_parent_tool_observation(obs)
    row = ledger.read()[-1]
    assert accepted == row.seq == 4 and row.event.kind == "PARENT_TOOL_OBSERVATION_RECORDED"
    assert set(row.event.payload) == {
        "schema",
        "domain_tag",
        "operation_id",
        "ordinal",
        "claim_seq",
        "claim_row_hash",
        "observation_b64",
        "observation_sha256",
    }
    assert base64.b64decode(row.event.payload["observation_b64"]) == obs
    ack = a.issue_parent_tool_commit_ack(
        f["operation"], "OUTCOME", issuer_id="issuer", signer=f["issuer"].sign
    )
    view = a.verify_parent_tool_commit_ack(
        ack, expected_request_bytes=f["request"], expected_observation_bytes=obs
    )
    assert view == a.read_parent_tool_operation(f["operation"])
    assert (view.raw_bytes, view.result_bytes, view.accepted_seq, view.accepted_row_hash) == (
        f["raw"],
        result,
        row.seq,
        row.row_hash,
    )
    with pytest.raises(FrozenInstanceError):
        view.outcome = "UNKNOWN"
    assert ledger.verify_chain() == ledger.head_hash()
    assert not any(r.event.kind == "ADMISSION_SEND_CLAIMED" for r in ledger.read())


@pytest.mark.parametrize(
    "field,value",
    [
        ("schema", True),
        ("purpose_version", True),
        ("ordinal", False),
        ("ordinal", 1),
        ("mcp_id", True),
        ("mcp_id", -1),
        ("mcp_id", 2**53),
        ("request_id", ""),
        ("request_id", "x" * 129),
        ("parent_boot_id", "boot\0"),
        ("parent_process_id", None),
        ("tool_name", "shell"),
        ("tool_source_sha256", "a" * 64),
        ("tool_protocol_version", "wrong"),
        ("transformation", "SCOPED_PATCH"),
        ("transformation_version", "wrong"),
        ("arguments", {}),
        ("arguments", {"artifact_id": "wrong"}),
        ("arguments_sha256", "A" * 64),
        ("expected_input_sha256", "a" * 64),
        ("max_raw_bytes", True),
        ("max_result_bytes", 131073),
        ("issuer_id", "receiver"),
        ("domain_tag", "PRODUCTION"),
        ("issued_at", "2026-10-19T12:00:01+00:00"),
        ("expires_at", "2026-10-21T12:00:00+00:00"),
        ("issued_at", "2026-10-19T12:00:00"),
    ],
)
def test_parent_tool_bad_request_denies_without_append(field, value):
    f = tool_fixture()
    before = f["ledger"].head_hash()
    with pytest.raises(ValueError):
        f["authority"].claim_parent_tool_read(tool_request(f, changes={field: value}))
    assert f["ledger"].head_hash() == before


@pytest.mark.parametrize(
    "field,value",
    [
        ("admission_epoch", True),
        ("policy_revision", True),
        ("policy_digest", "a" * 64),
        ("signed_v2_manifest_sha256", "a" * 64),
        ("tool_grant_digest", "a" * 64),
        ("base_grant_digest", "a" * 64),
    ],
)
def test_parent_tool_context_is_exact_and_type_preserving(field, value):
    f = tool_fixture()
    body = json.loads(f["request"])["body"]
    body["context"][field] = value
    before = f["ledger"].head_hash()
    with pytest.raises(ValueError):
        f["authority"].claim_parent_tool_read(tool_signed(body, f["parent"]))
    assert f["ledger"].head_hash() == before


@pytest.mark.parametrize(
    "field,value",
    [
        ("max_operations", 2),
        ("max_operations", True),
        ("max_raw_bytes", 16385),
        ("max_result_bytes", 131073),
        ("start_window_seconds", 31),
        ("start_window_seconds", False),
        ("parent_grant_digest", "a" * 64),
        ("parent_identity_sha256", "a" * 64),
        ("policy_digest", "a" * 64),
        ("policy_signer_id", "parent"),
        ("derivative_rule_id", "absent"),
        ("purpose_delegations", []),
        ("transformation", "MODEL_OUTPUT_WITH_CONFINED_INPUTS"),
    ],
)
def test_parent_tool_signed_grant_cannot_expand_scope(field, value):
    f = tool_fixture()
    grant = copy.deepcopy(f["grant"])
    grant[field] = value
    a = tool_rebuild(f, grant=grant)
    before = f["ledger"].head_hash()
    with pytest.raises(ValueError):
        a.claim_parent_tool_read(tool_request(f, grant=grant))
    assert f["ledger"].head_hash() == before


@pytest.mark.parametrize(
    "case",
    [
        "missing",
        "duplicate",
        "receiver_ack",
        "parent_ack",
        "root_ack",
        "wrong_public_key",
        "wrong_parent",
        "wrong_version",
    ],
)
def test_parent_tool_purposes_need_explicit_distinct_enrollment(case):
    f = tool_fixture()
    grant = copy.deepcopy(f["grant"])
    entries = grant["purpose_delegations"]
    if case == "missing":
        entries.pop()
    elif case == "duplicate":
        entries[2] = copy.deepcopy(entries[1])
    elif case.endswith("_ack"):
        who = case.removesuffix("_ack")
        entries[2]["signer_identity_id"] = who
        entries[2]["public_key_sha256"] = sha(f[who].public_key().public_bytes_raw())
    elif case == "wrong_public_key":
        entries[0]["public_key_sha256"] = "a" * 64
    elif case == "wrong_parent":
        entries[1]["signer_identity_id"] = "receiver"
    else:
        entries[0]["purpose_version"] = True
    with pytest.raises(ValueError):
        tool_rebuild(f, grant=grant).claim_parent_tool_read(tool_request(f, grant=grant))
    assert len(f["ledger"].read()) == 2


def test_parent_tool_strict_wire_encodings_and_domain_separation():
    f = tool_fixture()
    a = f["authority"]
    body = json.loads(f["request"])["body"]
    malformed = [
        f["request"] + b"\n",
        json.dumps(json.loads(f["request"])).encode(),
        f["request"].replace(b'"ordinal":0', b'"ordinal":0,"ordinal":0'),
        f["request"].replace(b'"mcp_id":7', b'"mcp_id":NaN'),
        f["request"].replace(b'"mcp_id":7', b'"mcp_id":Infinity'),
        b" " * 32769,
        tool_signed(dict(body, unknown=1), f["parent"]),
        tool_signed({k: v for k, v in body.items() if k != "arguments"}, f["parent"]),
        wire_json(signed(body, f["parent"])),
        f["base_raw"],
        tool_signed(body, f["parent"], prefix=b"PAEOS_PARENT_TOOL_OBSERVATION/v1\0"),
        tool_signed(body, f["parent"], prefix=b"PAEOS_PARENT_TOOL_COMMIT_ACK/v1\0"),
        tool_signed(body, f["receiver"]),
    ]
    for raw in malformed:
        with pytest.raises(ValueError):
            a.claim_parent_tool_read(raw)
    assert len(f["ledger"].read()) == 2
    with pytest.raises(ValueError):
        a.append_signed(json.loads(f["request"])["body"])
    with pytest.raises(ValueError):
        a.append_signed(json.loads(f["trust"].grants[1]))
    assert len(f["ledger"].read()) == 2


@pytest.mark.parametrize(
    "case",
    [
        "empty_policy",
        "missing_grant",
        "duplicate_grant",
        "bad_signature",
        "missing_parent",
        "old_manifest",
    ],
)
def test_parent_tool_no_default_positive_configuration(case):
    from runtime.autonomy.admission_authority import AdmissionAuthority

    f = tool_fixture()
    trust = f["trust"]
    policies = (f["policy_bytes"],)
    if case == "empty_policy":
        policies = ()
    elif case == "missing_grant":
        trust = replace(trust, grants=trust.grants[:1])
    elif case == "duplicate_grant":
        trust = replace(trust, grants=(*trust.grants, trust.grants[1]))
    elif case == "missing_parent":
        trust = replace(trust, identities=trust.identities[:2])
    elif case == "old_manifest":
        policies = (b"{}",)
    else:
        env = json.loads(trust.grants[1])
        env["signature"] = "0" * 128
        trust = replace(trust, grants=(trust.grants[0], wire_json(env)))
    a = AdmissionAuthority(
        f["ledger"], trust=trust, domain_tag="TEST", now=lambda: NOW, tool_policy_manifests=policies
    )
    with pytest.raises(ValueError):
        a.claim_parent_tool_read(f["request"])
    assert len(f["ledger"].read()) == 2


@pytest.mark.parametrize(
    "case",
    [
        "secret",
        "class_mismatch",
        "omitted_input",
        "no_read",
        "rule_bound",
        "artifact_bound",
        "envelope",
    ],
)
def test_parent_tool_signed_policy_is_independently_enforced(case):
    def mutate(p):
        rule = p["derivative_rules"][0]
        cls = p["classes"][0]
        if case == "secret":
            cls["data_class"] = "SECRET"
        elif case == "class_mismatch":
            rule["output_data_class"] = "INTERNAL"
        elif case == "omitted_input":
            rule["input_artifact_sha256s"] = []
        elif case == "no_read":
            rule["transformation_ids"] = ["SCOPED_PATCH"]
        elif case == "rule_bound":
            rule["max_output_bytes"] = 100
        elif case == "artifact_bound":
            cls["scope"]["allowed_artifacts"][0]["max_bytes"] = 10
        else:
            rule["tool_envelope_sha256"] = "a" * 64

    f = tool_fixture(policy_mutate=mutate)
    with pytest.raises(ValueError):
        f["authority"].claim_parent_tool_read(f["request"])
    assert len(f["ledger"].read()) == 2


@pytest.mark.parametrize(
    "field,value",
    [
        ("claim_seq", True),
        ("claim_seq", 1),
        ("claim_row_hash", "a" * 64),
        ("request_sha256", "a" * 64),
        ("parent_boot_id", "other"),
        ("parent_process_id", "other"),
        ("raw_length", True),
        ("raw_length", 16385),
        ("result_length", 131073),
        ("actual_input_sha256", "a" * 64),
        ("result_sha256", "a" * 64),
        ("raw_b64", ""),
        ("raw_b64", "YQ"),
        ("result_b64", "YQ=="),
        ("effect_started_at", "2026-10-19T11:59:59+00:00"),
        ("observed_at", "2026-10-19T11:59:59+00:00"),
        ("effect_started_at", "2026-10-19T12:00:31+00:00"),
        ("error_code", "arbitrary text"),
        ("outcome", "missing"),
    ],
)
def test_parent_tool_observation_cannot_substitute_bytes_or_claim(field, value):
    f = tool_fixture()
    a = f["authority"]
    a.claim_parent_tool_read(f["request"])
    before = f["ledger"].head_hash()
    obs, _ = tool_observation(f, changes={field: value})
    with pytest.raises(ValueError):
        a.record_parent_tool_observation(obs)
    assert f["ledger"].head_hash() == before
    assert a.read_parent_tool_operation(f["operation"]).result_bytes is None


@pytest.mark.parametrize(
    "case",
    [
        "noncanonical_result",
        "different_result",
        "different_raw",
        "overflow_raw",
        "noncanonical_base64",
        "oversize_wire",
    ],
)
def test_parent_tool_hashes_alone_do_not_prove_exact_observed_bytes(case):
    import base64

    f = tool_fixture()
    a = f["authority"]
    a.claim_parent_tool_read(f["request"])
    obs, result = tool_observation(f)
    body = json.loads(obs)["body"]
    if case in {"different_raw", "overflow_raw", "noncanonical_base64"}:
        raw = b"wrong" if case == "different_raw" else b"x" * 16385
        if case == "noncanonical_base64":
            body["raw_b64"] += "="
        else:
            body.update(
                raw_b64=base64.b64encode(raw).decode(),
                raw_length=len(raw),
                actual_input_sha256=sha(raw),
            )
    elif case == "oversize_wire":
        body["result_b64"] = "A" * 196608
    else:
        result = (
            json.dumps(json.loads(result), indent=2).encode()
            if case == "noncanonical_result"
            else b"{}\n"
        )
        body.update(
            result_b64=base64.b64encode(result).decode(),
            result_length=len(result),
            result_sha256=sha(result),
        )
    before = f["ledger"].head_hash()
    with pytest.raises(ValueError):
        a.record_parent_tool_observation(tool_signed(body, f["parent"]))
    assert f["ledger"].head_hash() == before


@pytest.mark.parametrize("outcome", ["UNKNOWN", "ERROR"])
def test_parent_tool_uncertain_outcome_is_terminal_without_result_ack(outcome):
    f = tool_fixture()
    a = f["authority"]
    a.claim_parent_tool_read(f["request"])
    obs, _ = tool_observation(f, outcome=outcome)
    a.record_parent_tool_observation(obs)
    view = a.read_parent_tool_operation(f["operation"])
    assert view.outcome == outcome and view.raw_bytes is view.result_bytes is None
    before = f["ledger"].head_hash()
    returned, _ = tool_observation(f)
    for raw in (obs, returned):
        with pytest.raises(ValueError):
            a.record_parent_tool_observation(raw)
    with pytest.raises(ValueError):
        a.issue_parent_tool_commit_ack(
            f["operation"], "OUTCOME", issuer_id="issuer", signer=f["issuer"].sign
        )
    assert f["ledger"].head_hash() == before


@pytest.mark.parametrize(
    "field,value",
    [
        ("accepted_seq", 1),
        ("accepted_seq", True),
        ("accepted_row_hash", "a" * 64),
        ("accepted_prev_hash", "a" * 64),
        ("commit_head_hash", "a" * 64),
        ("verified_head_hash", "a" * 64),
        ("claim_row_hash", "a" * 64),
        ("claim_seq", 1),
        ("ordinal", 1),
        ("ordinal", False),
        ("request_sha256", "a" * 64),
        ("observation_sha256", "a" * 64),
        ("phase", "CLAIM"),
        ("parent_boot_id", "other"),
        ("raw_length", True),
        ("result_sha256", "a" * 64),
        ("status", "READY"),
        ("issuer_id", "receiver"),
        ("purpose", TOOL_PURPOSES[1]),
    ],
)
def test_parent_tool_signed_ack_must_join_actual_ledger(field, value):
    f = tool_fixture()
    a = f["authority"]
    a.claim_parent_tool_read(f["request"])
    obs, _ = tool_observation(f)
    a.record_parent_tool_observation(obs)
    ack = a.issue_parent_tool_commit_ack(
        f["operation"], "OUTCOME", issuer_id="issuer", signer=f["issuer"].sign
    )
    body = json.loads(ack)["body"]
    body[field] = value
    with pytest.raises(ValueError):
        a.verify_parent_tool_commit_ack(
            tool_signed(body, f["issuer"]),
            expected_request_bytes=f["request"],
            expected_observation_bytes=obs,
        )


def test_parent_tool_ack_requires_concrete_store_and_exact_expected_wires():
    from kernel.ledger import Event
    from runtime.autonomy.admission_authority import AdmissionAuthority

    f = tool_fixture()
    a = f["authority"]
    a.claim_parent_tool_read(f["request"])
    obs, _ = tool_observation(f)
    a.record_parent_tool_observation(obs)
    ack = a.issue_parent_tool_commit_ack(
        f["operation"], "OUTCOME", issuer_id="issuer", signer=f["issuer"].sign
    )
    absent = AdmissionAuthority(
        Ledger(InMemoryLedgerStore()),
        trust=f["trust"],
        domain_tag="TEST",
        now=lambda: NOW,
        tool_policy_manifests=(f["policy_bytes"],),
    )
    with pytest.raises(ValueError):
        absent.verify_parent_tool_commit_ack(
            ack, expected_request_bytes=f["request"], expected_observation_bytes=obs
        )
    for request, observation in (
        (f["request"] + b"\n", obs),
        (f["request"], None),
        (f["request"], obs + b"\n"),
    ):
        with pytest.raises(ValueError):
            a.verify_parent_tool_commit_ack(
                ack, expected_request_bytes=request, expected_observation_bytes=observation
            )
    f["ledger"].append(Event(1, "UNRELATED", {}), domain_tag="TEST")
    assert (
        a.verify_parent_tool_commit_ack(
            ack, expected_request_bytes=f["request"], expected_observation_bytes=obs
        ).outcome
        == "RETURNED"
    )
    with pytest.raises(ValueError):
        a.issue_parent_tool_commit_ack(
            f["operation"], "OUTCOME", issuer_id="receiver", signer=f["receiver"].sign
        )
    with pytest.raises(ValueError):
        a.issue_parent_tool_commit_ack(
            f["operation"], "OUTCOME", issuer_id="issuer", signer=f["parent"].sign
        )


def test_parent_tool_claim_ack_cannot_extend_start_window_or_survive_signer_revocation():
    from kernel.ledger import Event

    f = tool_fixture()
    a = f["authority"]
    a.claim_parent_tool_read(f["request"])
    ack = a.issue_parent_tool_commit_ack(
        f["operation"], "CLAIM", issuer_id="issuer", signer=f["issuer"].sign
    )
    body = json.loads(ack)["body"]
    body["expires_at"] = END
    with pytest.raises(ValueError):
        a.verify_parent_tool_commit_ack(
            tool_signed(body, f["issuer"]), expected_request_bytes=f["request"]
        )

    def revoking_signer(data):
        f["ledger"].append(
            Event(1, "AUTHORITY_GRANT_REVOKED", {"grant_id": "tool-grant"}), domain_tag="TEST"
        )
        return f["issuer"].sign(data)

    with pytest.raises(ValueError):
        a.issue_parent_tool_commit_ack(
            f["operation"], "CLAIM", issuer_id="issuer", signer=revoking_signer
        )


@pytest.mark.parametrize(
    "kind,field,identity",
    [
        ("AUTHORITY_GRANT_REVOKED", "grant_id", "grant"),
        ("AUTHORITY_GRANT_REVOKED", "grant_id", "tool-grant"),
        ("ADMISSION_REVOKED", "admission_ref", "admission"),
        ("DISCLOSURE_POLICY_REVOKED", "policy_id", "policy"),
    ],
)
def test_parent_tool_revocation_preserves_historical_outcome_but_denies_fresh_use(
    kind, field, identity
):
    from kernel.ledger import Event

    f = tool_fixture()
    a = f["authority"]
    a.claim_parent_tool_read(f["request"])
    obs, _ = tool_observation(f)
    f["ledger"].append(Event(1, kind, {field: identity}), domain_tag="TEST")
    seq = a.record_parent_tool_observation(obs)
    assert f["ledger"].read()[-1].seq == seq
    with pytest.raises(ValueError):
        a.read_parent_tool_operation(f["operation"])
    with pytest.raises(ValueError):
        a.issue_parent_tool_commit_ack(
            f["operation"], "OUTCOME", issuer_id="issuer", signer=f["issuer"].sign
        )
    with pytest.raises(ValueError):
        a.claim_parent_tool_read(tool_request(f, changes={"request_id": "new"}))


def test_parent_tool_supersession_expiry_and_removed_purpose_deny_replay():
    from kernel.ledger import Event

    f = tool_fixture()
    a = f["authority"]
    a.claim_parent_tool_read(f["request"])
    obs, _ = tool_observation(f)
    a.record_parent_tool_observation(obs)
    later = tool_rebuild(f, now=datetime(2026, 10, 20, 12, tzinfo=UTC))
    with pytest.raises(ValueError):
        later.read_parent_tool_operation(f["operation"])
    removed = tool_rebuild(f, trust=replace(f["trust"], grants=(f["base_raw"],)))
    with pytest.raises(ValueError):
        removed.read_parent_tool_operation(f["operation"])
    f["ledger"].append(
        Event(1, "ADMISSION_CURRENT", dict(f["admission"], epoch=2)), domain_tag="TEST"
    )
    with pytest.raises(ValueError):
        a.read_parent_tool_operation(f["operation"])


def test_parent_tool_sqlite_reopen_unsettled_and_returned_retains_exact_bytes(tmp_path):
    from runtime.autonomy.admission_authority import AdmissionAuthority

    database = tmp_path / "parent-tool.db"
    store = SqliteLedgerStore(database)
    f = tool_fixture(Ledger(store))
    f["authority"].claim_parent_tool_read(f["request"])
    f["ledger"].close()
    store.close()
    store = SqliteLedgerStore(database)
    ledger = Ledger(store)
    f["ledger"] = ledger
    a = tool_rebuild(f)
    f["authority"] = a
    assert a.read_parent_tool_operation(f["operation"]).outcome == "UNRESOLVED"
    with pytest.raises(ValueError):
        a.claim_parent_tool_read(tool_request(f, changes={"request_id": "after-crash"}))
    grant = dict(f["grant"], grant_id="new-tool-grant")
    with pytest.raises(ValueError):
        tool_rebuild(f, grant=grant).claim_parent_tool_read(tool_request(f, grant=grant))
    obs, result = tool_observation(f)
    a.record_parent_tool_observation(obs)
    ledger.close()
    store.close()
    store = SqliteLedgerStore(database)
    ledger = Ledger(store)
    a = AdmissionAuthority(
        ledger,
        trust=f["trust"],
        domain_tag="TEST",
        now=lambda: NOW,
        tool_policy_manifests=(f["policy_bytes"],),
    )
    try:
        view = a.read_parent_tool_operation(f["operation"])
        assert (view.raw_bytes, view.result_bytes, view.observation_bytes) == (
            f["raw"],
            result,
            obs,
        )
        before = ledger.head_hash()
        for _ in range(2):
            ack = a.issue_parent_tool_commit_ack(
                f["operation"], "OUTCOME", issuer_id="issuer", signer=f["issuer"].sign
            )
            assert (
                a.verify_parent_tool_commit_ack(
                    ack, expected_request_bytes=f["request"], expected_observation_bytes=obs
                )
                == view
            )
        assert ledger.head_hash() == before
    finally:
        ledger.close()
        store.close()


class ParentRejectingStore(InMemoryLedgerStore):
    def append_row_if_head(self, row, expected_head_hash):
        if row.event.kind.startswith("PARENT_TOOL_"):
            raise OSError("synthetic capacity rejection")
        return super().append_row_if_head(row, expected_head_hash)


def test_parent_tool_store_rejection_cannot_yield_success_ack():
    f = tool_fixture(Ledger(ParentRejectingStore()))
    a = f["authority"]
    with pytest.raises(OSError):
        a.claim_parent_tool_read(f["request"])
    with pytest.raises(ValueError):
        a.issue_parent_tool_commit_ack(
            f["operation"], "CLAIM", issuer_id="issuer", signer=f["issuer"].sign
        )
    assert len(f["ledger"].read()) == 2


class ParentPausingStore(SqliteLedgerStore):
    def __init__(self, path, ready, resume):
        super().__init__(path)
        self.ready, self.resume = ready, resume

    def append_row_if_head(self, row, expected_head_hash):
        if row.event.kind == "PARENT_TOOL_READ_CLAIMED":
            self.ready.set()
            if not self.resume.wait(10):
                raise TimeoutError("revoker not released")
        return super().append_row_if_head(row, expected_head_hash)


def parent_claim_process(database, trust, policies, request, gate, results, pause=None):
    from runtime.autonomy.admission_authority import AdmissionAuthority

    store = ParentPausingStore(database, *pause) if pause else SqliteLedgerStore(database)
    ledger = Ledger(store, writer_id="signed-process-test")
    a = AdmissionAuthority(
        ledger, trust=trust, domain_tag="TEST", now=lambda: NOW, tool_policy_manifests=policies
    )
    try:
        if gate is not None:
            gate.wait(10)
        a.claim_parent_tool_read(request)
        results.put("CLAIMED")
    except ValueError:
        results.put("DENIED")
    except Exception as exc:
        results.put(("ERROR", type(exc).__name__))
    finally:
        ledger.close()
        store.close()


def test_parent_tool_two_processes_share_one_allocation_claim(tmp_path):
    import multiprocessing

    database = tmp_path / "parent-race.db"
    store = SqliteLedgerStore(database)
    f = tool_fixture(Ledger(store, writer_id="signed-process-test"))
    requests = [tool_request(f, changes={"request_id": str(i)}) for i in range(2)]
    f["ledger"].close()
    store.close()
    context = multiprocessing.get_context("spawn")
    gate = context.Barrier(2)
    results = context.Queue()
    processes = [
        context.Process(
            target=parent_claim_process,
            args=(str(database), f["trust"], (f["policy_bytes"],), request, gate, results),
        )
        for request in requests
    ]
    join_processes(processes)
    assert sorted(results.get(timeout=5) for _ in processes) == ["CLAIMED", "DENIED"]
    store = SqliteLedgerStore(database)
    ledger = Ledger(store, writer_id="signed-process-test")
    try:
        assert sum(r.event.kind == "PARENT_TOOL_READ_CLAIMED" for r in ledger.read()) == 1
        assert ledger.verify_chain() == ledger.head_hash()
    finally:
        ledger.close()
        store.close()
        results.close()
        results.join_thread()


def test_parent_tool_revocation_wins_between_validation_and_cas(tmp_path):
    import multiprocessing

    database = tmp_path / "parent-revoke.db"
    store = SqliteLedgerStore(database)
    f = tool_fixture(Ledger(store, writer_id="signed-process-test"))
    revoke = signed(dict(unsigned(f["admission"]), record_kind="ADMISSION_REVOKED"), f["issuer"])
    f["ledger"].close()
    store.close()
    context = multiprocessing.get_context("spawn")
    ready = context.Event()
    resume = context.Event()
    results = context.Queue()
    claimant = context.Process(
        target=parent_claim_process,
        args=(
            str(database),
            f["trust"],
            (f["policy_bytes"],),
            f["request"],
            None,
            results,
            (ready, resume),
        ),
    )
    revoker = context.Process(
        target=signed_process_revoke,
        args=(str(database), f["trust"], revoke, ready, resume, results),
    )
    join_processes([claimant, revoker])
    assert sorted(results.get(timeout=5) for _ in range(2)) == ["DENIED", "REVOKED"]
    store = SqliteLedgerStore(database)
    ledger = Ledger(store, writer_id="signed-process-test")
    try:
        assert not any(r.event.kind == "PARENT_TOOL_READ_CLAIMED" for r in ledger.read())
        assert ledger.read()[-1].event.kind == "ADMISSION_REVOKED"
        assert ledger.verify_chain() == ledger.head_hash()
    finally:
        ledger.close()
        store.close()
        results.close()
        results.join_thread()


@pytest.mark.parametrize("alias_of", ["parent", "root"])
def test_parent_tool_distinct_identity_labels_cannot_alias_ack_signing_key(alias_of):
    from runtime.autonomy.admission_authority import EnrolledIdentity

    f = tool_fixture()
    grant = copy.deepcopy(f["grant"])
    key = f[alias_of].public_key().public_bytes_raw()
    grant["purpose_delegations"][2]["public_key_sha256"] = sha(key)
    trust = replace(
        f["trust"],
        identities=tuple(
            EnrolledIdentity("issuer", key) if x.identity_id == "issuer" else x
            for x in f["trust"].identities
        ),
        grants=(f["base_raw"], tool_signed(grant, f["root"])),
    )
    # Re-sign both CURRENT records under the alias so legacy signature failure
    # cannot accidentally be the reason the new separation control passes.
    from kernel.ledger import Event

    ledger = Ledger(InMemoryLedgerStore())
    for old in f["ledger"].read():
        body = unsigned(old.event.payload)
        ledger.append(Event(1, old.event.kind, signed(body, f[alias_of])), domain_tag="TEST")
    f["ledger"] = ledger
    a = tool_rebuild(f, grant=grant, trust=trust)
    assert a.verify_admission(ledger.read()[1].event.payload)
    before = ledger.head_hash()
    with pytest.raises(ValueError):
        a.claim_parent_tool_read(tool_request(f, grant=grant))
    assert ledger.head_hash() == before
