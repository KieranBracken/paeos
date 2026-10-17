"""TEST-domain integration controls; these do not establish Founder admission."""

from __future__ import annotations

import dataclasses
import json
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

import pytest
from kernel.capability import CapabilityBroker
from kernel.cas import CAS, FilesystemCasStore, InMemoryCasStore
from kernel.ledger import Event, Ledger
from kernel.ledger_sqlite import SqliteLedgerStore
from kernel.types import DomainTag, Role, StageId
from nacl.signing import SigningKey
from runtime.implementation_contract import (
    AcceptanceCommand,
    FrozenImplementationContract,
    canonical_implementation_contract_bytes,
    compute_contract_hash,
)


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()


def rehash(contract, **changes):
    value = dataclasses.replace(contract, **changes)
    fields = dataclasses.asdict(value)
    fields.pop("contract_id")
    fields.pop("contract_hash")
    fields["acceptance_commands"] = value.acceptance_commands
    return dataclasses.replace(value, contract_hash=compute_contract_hash(**fields))


@pytest.fixture
def case(tmp_path):
    from runtime import scope_supersession as api

    assert hasattr(api, "ScopeSupersessionService"), "scope supersession mechanism is absent"
    cas = CAS(FilesystemCasStore(tmp_path / "cas"))
    store = SqliteLedgerStore(tmp_path / "ledger.sqlite")
    ledger = Ledger(store, writer_id="scope-test")
    broker = CapabilityBroker(SigningKey(b"\x15" * 32))
    context_ref = cas.put(b"immutable context")
    derivation_ref = cas.put(b"immutable derivation")
    command = AcceptanceCommand("focused", (sys.executable, "-c", "pass"), ".", 30)
    old = rehash(
        FrozenImplementationContract(
            "contract-old",
            "",
            "goal-1",
            "run-1",
            "TRACE_B",
            "a" * 40,
            ("runtime/old.py",),
            ("evidence/result.json",),
            (command,),
            ("git", "restore", "runtime/old.py"),
            "INTERNAL",
            context_ref,
            derivation_ref,
        )
    )
    new = rehash(
        old, contract_id="contract-new", allowed_paths=("runtime/old.py", "runtime/new.py")
    )
    old_ref = cas.put(canonical_implementation_contract_bytes(old))
    new_ref = cas.put(canonical_implementation_contract_bytes(new))
    evidence = {
        name: cas.put((name + " old evidence").encode())
        for name in ("P1", "PRE-P2", "P2", "unaffected")
    }
    policy = {
        "schema": "paeos.scope-policy/1",
        "authorized_paths": ["runtime/old.py", "runtime/new.py"],
        "protected_paths": ["runtime/new.py"],
        "claims": [
            {
                "id": "P1",
                "source_paths": ["runtime/new.py"],
                "depends_on": [],
                "evidence_refs": [evidence["P1"]],
            },
            {
                "id": "PRE-P2",
                "source_paths": [],
                "depends_on": ["P1"],
                "evidence_refs": [evidence["PRE-P2"]],
            },
            {
                "id": "P2",
                "source_paths": [],
                "depends_on": ["PRE-P2"],
                "evidence_refs": [evidence["P2"]],
            },
            {
                "id": "unaffected",
                "source_paths": ["runtime/elsewhere.py"],
                "depends_on": [],
                "evidence_refs": [evidence["unaffected"]],
            },
        ],
    }
    policy_ref = cas.put(encoded(policy))
    prestate = {
        "schema": "paeos.scope-prestate/1",
        "files": [
            {"path": "runtime/old.py", "sha256": cas.put(b"old source")},
            {"path": "runtime/new.py", "sha256": "ABSENT"},
        ],
    }
    request = api.SupersessionRequest(
        transaction_id="successor-1",
        predecessor_contract_ref=old_ref,
        successor_contract_ref=new_ref,
        source_prestate_ref=cas.put(encoded(prestate)),
        defect_evidence_ref=cas.put(b"independently verified defect"),
        independent_review_ref=cas.put(b"scope review evidence"),
        indexed_authority_record_ref=cas.put(b"indexed human instruction; not a signature"),
        policy_ref=policy_ref,
        expected_head_hash=ledger.head_hash(),
        goal_id="goal-1",
        run_id="run-1",
        session="ratifier-session",
        domain="TEST",
        expiry_seq=100,
    )
    value = SimpleNamespace(
        api=api,
        cas=cas,
        store=store,
        ledger=ledger,
        broker=broker,
        request=request,
        policy=policy,
        prestate=prestate,
        old=old,
        new=new,
        evidence=evidence,
        path=tmp_path / "ledger.sqlite",
    )
    yield value
    ledger.close()
    store.close()


def service(c, *, ledger=None, policy_ref=None):
    return c.api.ScopeSupersessionService(
        cas=c.cas,
        ledger=ledger or c.ledger,
        verifier=c.broker.verifier(),
        goal_id="goal-1",
        run_id="run-1",
        session="ratifier-session",
        domain=DomainTag.TEST,
        policy_ref=policy_ref or c.request.policy_ref,
    )


def token(c, request=None, **changes):
    request = request or c.request
    digest = c.api.request_digest(request)
    args = dict(
        goal_id="goal-1",
        run_id="run-1",
        stage=StageId.PLAN,
        role=Role.RATIFIER,
        session="ratifier-session",
        operations=("scope.supersede:" + digest,),
        issued_seq=0,
        expires_seq=100,
        mission_execution_digest=digest,
    )
    args.update(changes)
    return c.broker.mint(**args)


def reject(c, request=None, authority=None, **service_args):
    request = request or c.request
    before = tuple(c.ledger.read())
    with pytest.raises(c.api.SupersessionError):
        service(c, **service_args).consume(request, authority or token(c, request))
    assert tuple(c.ledger.read()) == before


def test_valid_consumption_preserves_history_and_keeps_activation_pending(case):
    c = case
    c.ledger.append(Event(1, "historical", {"meaning": "preserved"}), domain_tag="TEST")
    old_rows = tuple(c.ledger.read())
    request = dataclasses.replace(c.request, expected_head_hash=c.ledger.head_hash())
    old_bytes = c.cas.get(request.predecessor_contract_ref)
    receipt = service(c).consume(request, token(c, request))
    assert tuple(c.ledger.read()[:-1]) == old_rows
    assert c.cas.get(request.predecessor_contract_ref) == old_bytes
    assert receipt.row.seq == 2
    assert receipt.row.domain_tag == "TEST"
    assert receipt.status == "PENDING_REQUALIFICATION_AND_ACTIVATION"
    assert receipt.required_requalifications == ("P1", "P2", "PRE-P2")
    assert set(receipt.invalidated_evidence_refs) == {
        c.evidence[name] for name in ("P1", "PRE-P2", "P2")
    }
    payload = receipt.row.event.payload
    assert payload["successor_contract_ref"] == request.successor_contract_ref
    assert c.cas.get(payload["request_ref"])
    assert json.loads(c.cas.get(payload["authority_token_ref"]))["bound_to"]["role"] == "RATIFIER"
    assert c.ledger.verify_chain() == receipt.row.row_hash
    assert not hasattr(receipt, "builder_capability")


@pytest.mark.parametrize(
    "changes",
    [{"role": role} for role in (Role.BUILDER, Role.PLANNER, Role.VERIFIER, Role.ADVERSARY)]
    + [
        {"goal_id": "other"},
        {"run_id": "other"},
        {"session": "other"},
        {"stage": StageId.IMPLEMENT},
        {"mission_execution_digest": None},
        {"operations": ("scope.supersede:*",)},
        {"expires_seq": 0},
    ],
)
def test_wrong_authority_binding_is_denied_without_append(case, changes):
    reject(case, authority=token(case, **changes))


def test_forged_foreign_and_absent_authority_are_denied(case):
    c = case
    good = token(c)
    reject(c, authority=dataclasses.replace(good, token="00" * 64))
    foreign = CapabilityBroker(SigningKey(b"\x16" * 32))
    saved = c.broker
    c.broker = foreign
    foreign_token = token(c)
    c.broker = saved
    reject(c, authority=foreign_token)
    with pytest.raises(c.api.SupersessionError):
        service(c).consume(c.request, None)
    assert c.ledger.read() == []


def test_exact_existing_session_identity_accepts_slashes(case):
    c = case
    session = "codex-agent:/root/ratifier"
    request = dataclasses.replace(c.request, session=session)
    consumer = c.api.ScopeSupersessionService(
        cas=c.cas,
        ledger=c.ledger,
        verifier=c.broker.verifier(),
        goal_id="goal-1",
        run_id="run-1",
        session=session,
        domain=DomainTag.TEST,
        policy_ref=request.policy_ref,
    )
    receipt = consumer.consume(request, token(c, request, session=session))
    assert receipt.row.seq == 1


@pytest.mark.parametrize(
    "field",
    ["transaction_id", "policy_ref", "source_prestate_ref", "domain", "session", "expiry_seq"],
)
def test_modifying_any_bound_request_cannot_reuse_authority(case, field):
    c = case
    value = 99 if field == "expiry_seq" else ("PRODUCTION" if field == "domain" else "b" * 64)
    reject(c, dataclasses.replace(c.request, **{field: value}), token(c))


def test_expired_request_and_malformed_identity_fail_closed(case):
    reject(case, dataclasses.replace(case.request, expiry_seq=0))
    reject(case, dataclasses.replace(case.request, transaction_id="../escape"))


@pytest.mark.parametrize(
    "path",
    [
        "../escape",
        "/absolute",
        "runtime/*",
        "runtime/./bad",
        "runtime\\bad",
        "constitution/rule.md",
        "operations/ENGINEERING_LIFECYCLE.md",
        "runtime/sentium.py",
    ],
)
def test_scope_escape_is_rejected_even_with_exact_signed_request(case, path):
    c = case
    new = rehash(c.new, allowed_paths=("runtime/old.py", path))
    # The strict codec may reject a malformed path before this component sees it.
    raw = json.loads(c.cas.get(c.request.successor_contract_ref))
    raw["allowed_paths"] = list(new.allowed_paths)
    raw["contract_hash"] = new.contract_hash
    req = dataclasses.replace(c.request, successor_contract_ref=c.cas.put(encoded(raw)))
    reject(c, req)


@pytest.mark.parametrize(
    "changes",
    [
        {"contract_id": "contract-old"},
        {"allowed_paths": ("runtime/old.py",)},
        {"allowed_paths": ("runtime/new.py",)},
        {"required_artifacts": ()},
        {"rollback_argv": ("true",)},
        {"base_commit": "b" * 40},
        {"goal_id": "other"},
        {"data_class": "PUBLIC"},
    ],
)
def test_successor_cannot_weaken_or_relabel_frozen_contract(case, changes):
    c = case
    new = rehash(c.new, **changes)
    req = dataclasses.replace(
        c.request, successor_contract_ref=c.cas.put(canonical_implementation_contract_bytes(new))
    )
    reject(c, req)


@pytest.mark.parametrize(
    "bad",
    [b"{}", b'{"schema":"x","schema":"y"}', b' {"schema":"paeos.scope-policy/1"}', b"not json"],
)
def test_malformed_policy_is_not_an_authority(case, bad):
    c = case
    ref = c.cas.put(bad)
    reject(c, dataclasses.replace(c.request, policy_ref=ref), policy_ref=ref)


@pytest.mark.parametrize(
    "fault",
    ["unknown", "cycle", "dangling", "duplicate", "missing_p1", "scope_outside", "stale_evidence"],
)
def test_incomplete_or_ambiguous_dependency_policy_is_rejected(case, fault):
    c = case
    policy = json.loads(encoded(c.policy))
    if fault == "unknown":
        policy["qualified"] = True
    if fault == "cycle":
        policy["claims"][0]["depends_on"] = ["P2"]
    if fault == "dangling":
        policy["claims"][0]["depends_on"] = ["missing"]
    if fault == "duplicate":
        policy["claims"].append(policy["claims"][0])
    if fault == "missing_p1":
        policy["claims"] = [policy["claims"][-1]]
    if fault == "scope_outside":
        policy["authorized_paths"] = ["runtime/old.py"]
    if fault == "stale_evidence":
        policy["claims"][0]["evidence_refs"] = ["0" * 64]
    ref = c.cas.put(encoded(policy))
    reject(c, dataclasses.replace(c.request, policy_ref=ref), policy_ref=ref)


@pytest.mark.parametrize("fault", ["missing", "duplicate", "unknown", "bad_hash"])
def test_prestate_is_exact_complete_and_not_claimed_current_source(case, fault):
    c = case
    prestate = json.loads(encoded(c.prestate))
    if fault == "missing":
        prestate["files"].pop()
    if fault == "duplicate":
        prestate["files"].append(prestate["files"][0])
    if fault == "unknown":
        prestate["files"][0]["qualified"] = True
    if fault == "bad_hash":
        prestate["files"][0]["sha256"] = "not-a-hash"
    reject(c, dataclasses.replace(c.request, source_prestate_ref=c.cas.put(encoded(prestate))))


def test_missing_or_corrupt_cas_and_mutated_predecessor_fail_closed(case):
    c = case
    reject(c, dataclasses.replace(c.request, defect_evidence_ref="0" * 64))
    raw = json.loads(c.cas.get(c.request.predecessor_contract_ref))
    raw["allowed_paths"].append("runtime/tampered.py")
    reject(c, dataclasses.replace(c.request, predecessor_contract_ref=c.cas.put(encoded(raw))))
    # Corrupt the test's physical CAS, then demand explicit rehash even if CAS read verification is off.
    ref = c.request.defect_evidence_ref
    path = c.path.parent / "cas" / ref[:2] / ref[2:]
    path.write_bytes(b"corrupted")
    c.cas = CAS(FilesystemCasStore(c.path.parent / "cas"), verify_on_read=False)
    reject(c)


def test_replay_stays_rejected_after_durable_reopen(case):
    c = case
    authority = token(c)
    service(c).consume(c.request, authority)
    before = tuple(c.ledger.read())
    reject(c, authority=authority)
    c.ledger.close()
    c.store.close()
    c.store = SqliteLedgerStore(c.path)
    c.ledger = Ledger(c.store, writer_id="scope-test")
    reject(c, authority=authority)
    assert tuple(c.ledger.read()) == before
    c.ledger.close()
    c.store.close()


def test_stale_head_and_missing_atomic_port_never_fallback_to_append(case):
    c = case
    c.ledger.append(Event(1, "other", {}), domain_tag="TEST")
    reject(c)

    class OrdinaryPort:
        def append(self, *args, **kwargs):
            raise AssertionError("ordinary append is forbidden")

    reject(c, ledger=OrdinaryPort())


def test_two_independent_sqlite_controllers_consume_once(case):
    c = case
    # Real, distinct SQLite connections and ledger objects. The barrier forces both
    # validators through the precheck; only the storage transaction decides the winner.
    barrier = threading.Barrier(2)

    class RacingLedger(Ledger):
        def append_once_if_new(self, *args, **kwargs):
            barrier.wait(timeout=10)
            return super().append_once_if_new(*args, **kwargs)

    stores = [SqliteLedgerStore(c.path), SqliteLedgerStore(c.path)]
    ledgers = [RacingLedger(s, writer_id="scope-test") for s in stores]
    # Share the actual in-memory CAS to avoid unrelated filesystem-CAS tempfile races.
    copied = CAS(InMemoryCasStore())
    for shard in (c.path.parent / "cas").iterdir():
        for path in shard.iterdir():
            copied.put(path.read_bytes())
    c.cas = copied
    authority = token(c)

    def consume(ledger):
        try:
            service(c, ledger=ledger).consume(c.request, authority)
            return "consumed"
        except c.api.SupersessionError:
            return "denied"

    try:
        with ThreadPoolExecutor(2) as pool:
            results = list(pool.map(consume, ledgers))
        assert sorted(results) == ["consumed", "denied"]
        assert len(c.ledger.read()) == 1
        c.ledger.verify_chain()
    finally:
        for ledger in ledgers:
            ledger.close()
        for store in stores:
            store.close()


def test_lost_response_after_real_commit_does_not_allow_reuse(case):
    c = case

    class LostResponseLedger(Ledger):
        def append_once_if_new(self, *args, **kwargs):
            super().append_once_if_new(*args, **kwargs)
            raise TimeoutError("response lost after durable commit")

    other_store = SqliteLedgerStore(c.path)
    other = LostResponseLedger(other_store, writer_id="scope-test")
    authority = token(c)
    try:
        with pytest.raises(TimeoutError):
            service(c, ledger=other).consume(c.request, authority)
        assert len(c.ledger.read()) == 1
        reject(c, authority=authority)
    finally:
        other.close()
        other_store.close()
