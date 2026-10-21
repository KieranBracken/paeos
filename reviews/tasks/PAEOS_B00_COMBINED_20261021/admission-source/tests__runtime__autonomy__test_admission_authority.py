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
