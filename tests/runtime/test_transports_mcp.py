"""B1.A acceptance tests for the MCP substrate (PAEOS-8 §10 / 7.6 §8).

Each server exposes only its 7.6 methods, capability-gated; `ledger.append` is not exposed;
an unauthorized/forged/expired token is denied (Adversary T1); a token for one server cannot
reach another.
"""

from __future__ import annotations

from dataclasses import replace

import pytest
from kernel.capability import CapabilityBroker, CapabilityToken
from kernel.cas import CAS, InMemoryCasStore
from kernel.constitution import Constitution
from kernel.evidence import Determinism, Evidence, EvidenceKind, EvidenceProducer
from kernel.ledger import Event, InMemoryLedgerStore, Ledger
from kernel.types import Role, StageId
from nacl.signing import SigningKey
from runtime.transports.mcp.servers import (
    ArtifactsServer,
    ConstitutionServer,
    CourtServer,
    LedgerServer,
    MemoryServer,
    Unauthorized,
)

_NOW = 20  # within [issued=10, expires=40]


def _clock() -> int:
    return _NOW


class _StubScars:
    def match_scars(self, signature: str) -> list[object]:
        return [{"sig": signature}]

    def get_precedent(self, precedent_id: str) -> object:
        return {"id": precedent_id}

    def propose_scar(self, draft: object) -> object:
        return {"accepted": draft}


class _StubCourt:
    def submit_evidence(self, evidence: Evidence) -> object:
        return {"submitted": evidence.hash}

    def get_verdict(self, artifact_hash: str) -> object:
        return {"verdict": "PASS", "for": artifact_hash}


def _broker() -> CapabilityBroker:
    return CapabilityBroker(SigningKey.generate())


def _token(broker: CapabilityBroker, ops: tuple[str, ...]) -> CapabilityToken:
    return broker.mint(
        goal_id="g", run_id="r", stage=StageId.IMPLEMENT, role=Role.BUILDER, session="s",
        operations=ops, issued_seq=10, expires_seq=40,
    )


# ---- constitution (read-only) ---------------------------------------------


def _constitution() -> Constitution:
    return Constitution({"D": "[c1] deny by default is the rule"})


def test_constitution_authorized_read() -> None:
    broker = _broker()
    server = ConstitutionServer(_constitution(), broker, _clock)
    token = _token(broker, ("mcp:constitution",))
    assert server.get_clause(token, "D#c1").ordinal == 1
    assert len(server.query(token, "deny")) == 1


def test_constitution_denies_token_without_grant() -> None:
    broker = _broker()
    server = ConstitutionServer(_constitution(), broker, _clock)
    token = _token(broker, ("mcp:ledger:read",))  # wrong grant
    with pytest.raises(Unauthorized):
        server.get_clause(token, "D#c1")


def test_constitution_has_no_write_method() -> None:
    methods = {m for m in dir(ConstitutionServer) if not m.startswith("_")}
    assert not (methods & {"put", "write", "set", "append", "update", "delete"})


# ---- ledger (append NOT exposed) ------------------------------------------


def _ledger() -> Ledger:
    ledger = Ledger(InMemoryLedgerStore())
    ledger.append(Event(1, "seed", {"x": 1}))
    return ledger


def test_ledger_append_is_not_exposed() -> None:
    # the single most important MCP invariant: agents cannot append through MCP (SI-6, T7)
    assert not hasattr(LedgerServer, "append")
    surface = {m for m in dir(LedgerServer) if not m.startswith("_")}
    assert surface == {"read", "verify_chain"}


def test_ledger_read_gated() -> None:
    broker = _broker()
    server = LedgerServer(_ledger(), broker, _clock)
    token = _token(broker, ("mcp:ledger:read",))
    assert len(server.read(token)) == 1
    assert server.verify_chain(token)
    with pytest.raises(Unauthorized):
        LedgerServer(_ledger(), broker, _clock).read(_token(broker, ("mcp:constitution",)))


# ---- artifacts ------------------------------------------------------------


def test_artifacts_read_write_grants_are_separate() -> None:
    broker = _broker()
    server = ArtifactsServer(CAS(InMemoryCasStore()), broker, _clock)
    writer = _token(broker, ("mcp:artifacts:write", "mcp:artifacts:read"))
    h = server.put(writer, b"blob")
    assert server.get(writer, h) == b"blob"
    reader = _token(broker, ("mcp:artifacts:read",))
    with pytest.raises(Unauthorized):
        server.put(reader, b"nope")  # read grant cannot write


# ---- memory / court (stub backends) ---------------------------------------


def test_memory_read_and_write_gated() -> None:
    broker = _broker()
    server = MemoryServer(_StubScars(), broker, _clock)
    reader = _token(broker, ("mcp:memory:read",))
    assert server.match_scars(reader, "sigX") == [{"sig": "sigX"}]
    with pytest.raises(Unauthorized):
        server.propose_scar(reader, {"draft": 1})  # needs :write
    writer = _token(broker, ("mcp:memory:write",))
    assert server.propose_scar(writer, {"draft": 1}) == {"accepted": {"draft": 1}}


def test_court_submit_and_verdict_gated() -> None:
    broker = _broker()
    server = CourtServer(_StubCourt(), broker, _clock)
    ev = Evidence(
        hash="e" * 64, kind=EvidenceKind.TEST, claim_id="c", artifact_hash="a" * 64,
        environment_hash="v" * 64, reproducible_command="echo ok",
        producer=EvidenceProducer(role=Role.BUILDER, session="s"),
        determinism=Determinism.DETERMINISTIC, result={"exit_code": 0}, attestation="sig",
    )
    writer = _token(broker, ("mcp:court:write",))
    assert server.submit_evidence(writer, ev) == {"submitted": ev.hash}
    reader = _token(broker, ("mcp:court:read",))
    with pytest.raises(Unauthorized):
        server.submit_evidence(reader, ev)  # needs :write


# ---- Adversary T1: forged / expired / cross-server ------------------------


def test_forged_token_is_denied() -> None:
    broker = _broker()
    server = ConstitutionServer(_constitution(), broker, _clock)
    forged = replace(_token(broker, ("mcp:constitution",)), token="00" * 64)
    with pytest.raises(Unauthorized):
        server.get_clause(forged, "D#c1")


def test_expired_token_is_denied() -> None:
    broker = _broker()
    server = ConstitutionServer(_constitution(), broker, lambda: 99)  # past expiry 40
    token = _token(broker, ("mcp:constitution",))
    with pytest.raises(Unauthorized):
        server.get_clause(token, "D#c1")


def test_token_for_one_server_cannot_reach_another() -> None:
    broker = _broker()
    con_token = _token(broker, ("mcp:constitution",))
    ledger_server = LedgerServer(_ledger(), broker, _clock)
    artifacts_server = ArtifactsServer(CAS(InMemoryCasStore()), broker, _clock)
    with pytest.raises(Unauthorized):
        ledger_server.read(con_token)
    with pytest.raises(Unauthorized):
        artifacts_server.get(con_token, "a" * 64)
