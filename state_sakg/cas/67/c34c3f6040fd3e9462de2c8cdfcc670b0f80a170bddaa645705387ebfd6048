"""MCP substrate — capability-gated servers over the kernel (PAEOS-8 §10 B1.A / 7.6 §8).

Task B1.A. An agent reaches a kernel capability *only* through an MCP server, and only if its
capability token's operation allow-list grants it (deny-by-default, FR-4). Each server exposes
**exactly** the methods 7.6 §8 lists — no more — so the attack surface is the contract, nothing
else. Two invariants are structural, not policed:

  * **`ledger.append` is not exposed.** `LedgerServer` has `read` and `verify_chain` and *no* write
    method; agents emit events only via the kernel's single-writer `record_event` (SI-6, T7).
  * **The constitution is read-only** (FR-1) — it has no write method to expose.

Gating reuses the kernel `CapabilityBroker` (no kernel change): a call verifies the token
(unforgeable signature + TTL) and that its allow-list contains the method's operation. The
constitution/ledger/artifacts servers wrap the sealed Phase-0 modules; the memory/court servers
wrap backend Protocols that B1.F (scars) and B1.E (court) fill — this task owns the *contract +
gating*, the backends land with their tasks.

This module is Z2 (`mcp/`), untrusted: it cannot widen authority, only check it.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol

from kernel.capability import CapabilityBroker, CapabilityError, CapabilityToken
from kernel.cas import CAS
from kernel.constitution import Clause, ClauseLineage, Constitution
from kernel.evidence import Evidence
from kernel.ledger import Ledger, LedgerRow
from kernel.types import Hash, Ts

__all__ = [
    "ArtifactsServer",
    "ConstitutionServer",
    "CourtBackend",
    "CourtServer",
    "LedgerServer",
    "MemoryServer",
    "ScarBackend",
    "Unauthorized",
]

# Clock: returns the current logical seq (ledger head) for TTL checks.
Clock = Callable[[], Ts]


class Unauthorized(Exception):
    """An MCP call was made without a token authorising the method (deny-by-default)."""


def _authorize(broker: CapabilityBroker, token: CapabilityToken, operation: str, now: Ts) -> None:
    """Verify the token is genuine, in-TTL, and grants `operation`. Raise Unauthorized otherwise.

    The token is checked against its *own* binding (so the goal/run/stage/role match trivially);
    the effective gates are the unforgeable signature, the TTL, and the operation allow-list — the
    checks an MCP boundary needs.
    """
    b = token.bound_to
    try:
        broker.verify(
            token,
            goal_id=b.goal_id,
            run_id=b.run_id,
            stage=b.stage,
            role=b.role,
            operation=operation,
            current_seq=now,
        )
    except CapabilityError as exc:
        raise Unauthorized(f"MCP operation {operation!r} denied: {exc}") from exc


# ---- constitution (read-only; FR-1) ---------------------------------------

_OP_CONSTITUTION = "mcp:constitution"


class ConstitutionServer:
    """Serves Z0 read-only (7.6 §8). No write method exists to expose (FR-1)."""

    def __init__(self, constitution: Constitution, broker: CapabilityBroker, clock: Clock) -> None:
        self._c = constitution
        self._broker = broker
        self._now = clock

    def get_clause(self, token: CapabilityToken, clause_id: str) -> Clause:
        _authorize(self._broker, token, _OP_CONSTITUTION, self._now())
        return self._c.get_clause(clause_id)

    def query(self, token: CapabilityToken, pattern: str) -> list[Clause]:
        _authorize(self._broker, token, _OP_CONSTITUTION, self._now())
        return self._c.query(pattern)

    def lineage(self, token: CapabilityToken, content_hash: str) -> ClauseLineage:
        _authorize(self._broker, token, _OP_CONSTITUTION, self._now())
        return self._c.lineage(content_hash)


# ---- ledger (read-only over MCP; append is NOT exposed, SI-6) --------------

_OP_LEDGER_READ = "mcp:ledger:read"


class LedgerServer:
    """Serves ledger reads (7.6 §8). **`append` is intentionally absent** — agents never write the
    ledger through MCP; the kernel's single-writer `record_event` is the only append path (SI-6)."""

    def __init__(self, ledger: Ledger, broker: CapabilityBroker, clock: Clock) -> None:
        self._ledger = ledger
        self._broker = broker
        self._now = clock

    def read(
        self, token: CapabilityToken, start: int = 1, end: int | None = None
    ) -> list[LedgerRow]:
        _authorize(self._broker, token, _OP_LEDGER_READ, self._now())
        return self._ledger.read(start, end)

    def verify_chain(self, token: CapabilityToken) -> str:
        _authorize(self._broker, token, _OP_LEDGER_READ, self._now())
        return self._ledger.verify_chain()


# ---- artifacts (CAS) ------------------------------------------------------

_OP_ARTIFACTS_READ = "mcp:artifacts:read"
_OP_ARTIFACTS_WRITE = "mcp:artifacts:write"


class ArtifactsServer:
    """Serves the content-addressed store (7.6 §8): put/get; immutable, content-addressed."""

    def __init__(self, cas: CAS, broker: CapabilityBroker, clock: Clock) -> None:
        self._cas = cas
        self._broker = broker
        self._now = clock

    def put(self, token: CapabilityToken, content: bytes) -> Hash:
        _authorize(self._broker, token, _OP_ARTIFACTS_WRITE, self._now())
        return self._cas.put(content)

    def get(self, token: CapabilityToken, artifact_hash: Hash) -> bytes:
        _authorize(self._broker, token, _OP_ARTIFACTS_READ, self._now())
        return self._cas.get(artifact_hash)


# ---- memory (scars) — backend filled by B1.F ------------------------------

_OP_MEMORY_READ = "mcp:memory:read"
_OP_MEMORY_WRITE = "mcp:memory:write"


class ScarBackend(Protocol):
    """The scar store B1.F implements. Types for scars/precedents/drafts land with B1.F; here they
    are `object` so this task does not invent them (CER-6)."""

    def match_scars(self, signature: str) -> list[object]: ...
    def get_precedent(self, precedent_id: str) -> object: ...
    def propose_scar(self, draft: object) -> object: ...


class MemoryServer:
    """Serves scar memory (7.6 §8). `:read` and `:write` are separate grants; `propose_scar` is a
    *gated transition*, not a direct write (T3/A-10)."""

    def __init__(self, backend: ScarBackend, broker: CapabilityBroker, clock: Clock) -> None:
        self._backend = backend
        self._broker = broker
        self._now = clock

    def match_scars(self, token: CapabilityToken, signature: str) -> list[object]:
        _authorize(self._broker, token, _OP_MEMORY_READ, self._now())
        return self._backend.match_scars(signature)

    def get_precedent(self, token: CapabilityToken, precedent_id: str) -> object:
        _authorize(self._broker, token, _OP_MEMORY_READ, self._now())
        return self._backend.get_precedent(precedent_id)

    def propose_scar(self, token: CapabilityToken, draft: object) -> object:
        _authorize(self._broker, token, _OP_MEMORY_WRITE, self._now())
        return self._backend.propose_scar(draft)


# ---- court — backend filled by B1.E ---------------------------------------

_OP_COURT_READ = "mcp:court:read"
_OP_COURT_WRITE = "mcp:court:write"


class CourtBackend(Protocol):
    """The Verification Court B1.E implements. `submit_evidence` is inert until the kernel
    adjudicates (SI-2). The verdict type lands with B1.E; `object` here."""

    def submit_evidence(self, evidence: Evidence) -> object: ...
    def get_verdict(self, artifact_hash: Hash) -> object: ...


class CourtServer:
    """Serves the court (7.6 §8): submit evidence (inert until adjudicated), read a verdict."""

    def __init__(self, backend: CourtBackend, broker: CapabilityBroker, clock: Clock) -> None:
        self._backend = backend
        self._broker = broker
        self._now = clock

    def submit_evidence(self, token: CapabilityToken, evidence: Evidence) -> object:
        _authorize(self._broker, token, _OP_COURT_WRITE, self._now())
        return self._backend.submit_evidence(evidence)

    def get_verdict(self, token: CapabilityToken, artifact_hash: Hash) -> object:
        _authorize(self._broker, token, _OP_COURT_READ, self._now())
        return self._backend.get_verdict(artifact_hash)
