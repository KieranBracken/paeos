"""PAEOS CLI control plane — drive a goal through the lifecycle (PAEOS-8 §10 B0.12).

The operator's interface to the kernel. It *composes* the kernel modules — it enforces nothing
itself; the kernel does. Every privileged action acquires a capability token first, runs through
the reference-monitor gate, and (on success) appends to the single-writer ledger, wrapped in a
`traced` log + meter row. Commands: create-goal, advance, ledger, replay, seal, inspect.

  create-goal → append `goal_created` (RAW)
  advance     → Gate.propose_transition (authority→goal→evidence→validation, + classifier at
                step 5) → on COMMITTED, append `transition_committed`
  seal        → verify a token authorising `request_seal`, then SealAuthority.seal
  ledger      → dump the event log
  replay      → rebuild the goal projection + verify_against_head
  inspect     → the current stage of a goal

Persistence note: this runs on an in-process ledger. Cross-invocation durability needs the
durable ledger backend (DEBT-0003); until then the CLI drives a goal within one process (the
`demo` command and the end-to-end test exercise the full flow).
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import uuid
from collections.abc import Iterable, Sequence
from dataclasses import replace
from hashlib import sha256
from pathlib import Path

from kernel.capability import CapabilityBroker, CapabilityError
from kernel.cas import CAS, InMemoryCasStore
from kernel.classifier import classify_paths
from kernel.evidence import Determinism, Evidence, EvidenceKind, EvidenceProducer
from kernel.gates import PROPOSE_TRANSITION_OP, Gate
from kernel.ledger import Event, InMemoryLedgerStore, Ledger, LedgerRow
from kernel.observability import Meter, get_logger, traced
from kernel.projections import Projection, replay, verify_against_head
from kernel.seal import SealAuthority, SealRecord
from kernel.types import (
    CapabilityToken,
    Claim,
    Hash,
    Outcome,
    Role,
    StageId,
    TransitionRequest,
    TransitionResult,
    ValidationClaim,
    WeightClass,
)
from nacl.signing import SigningKey

GOAL_CREATED = "goal_created"
TRANSITION_COMMITTED = "transition_committed"
REQUEST_SEAL_OP = "request_seal"


class Unauthenticated(Exception):
    """A privileged operation was attempted without an authorising capability token."""


class GoalNotAtStage(Exception):
    """An advance was requested from a stage the goal is not currently in."""


class GoalStates:
    """Projector: folds the ledger into {goal_id: current_stage}."""

    def initial(self) -> dict[str, str]:
        return {}

    def fold(self, state: dict[str, str], row: LedgerRow) -> dict[str, str]:
        event = row.event
        if event.kind == GOAL_CREATED:
            goal = event.payload["goal_id"]
            assert isinstance(goal, str)
            return {**state, goal: StageId.RAW.value}
        if event.kind == TRANSITION_COMMITTED:
            goal = event.payload["goal_id"]
            to_state = event.payload["to_state"]
            assert isinstance(goal, str) and isinstance(to_state, str)
            return {**state, goal: to_state}
        return state

    def digest(self, state: dict[str, str]) -> str:
        blob = json.dumps(state, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
        return sha256(blob.encode("ascii")).hexdigest()


class ControlPlane:
    """Wires the kernel spine into an operator-driveable control plane."""

    def __init__(self, ledger: Ledger, signing_key: SigningKey, *, cas: CAS | None = None) -> None:
        self._ledger = ledger
        self._cas = cas if cas is not None else CAS(InMemoryCasStore())
        self._broker = CapabilityBroker(signing_key)
        self._seal_authority = SealAuthority(signing_key, ledger)
        self._meter = Meter()
        self._log = get_logger("paeos.cli")
        self._evidence: dict[Hash, Evidence] = {}

    @property
    def meter(self) -> Meter:
        return self._meter

    def _current_seq(self) -> int:
        head = self._ledger.head()
        return head.seq if head is not None else 0

    # ---- commands ----

    def create_goal(self, description: str, weight_class: WeightClass) -> str:
        goal_id = "g-" + uuid.uuid4().hex[:12]
        with traced("create_goal", logger=self._log, meter=self._meter, goal=goal_id):
            self._ledger.append(
                Event(
                    1,
                    GOAL_CREATED,
                    {
                        "goal_id": goal_id,
                        "description": description,
                        "weight_class": weight_class.value,
                    },
                )
            )
        return goal_id

    def acquire_token(
        self,
        *,
        goal_id: str,
        run_id: str,
        stage: StageId,
        role: Role,
        session: str,
        operations: tuple[str, ...],
        ttl: int = 30,
    ) -> CapabilityToken:
        issued = self._current_seq()
        with traced(
            "acquire_capability", logger=self._log, meter=self._meter, goal=goal_id, role=role.value
        ):
            return self._broker.mint(
                goal_id=goal_id,
                run_id=run_id,
                stage=stage,
                role=role,
                session=session,
                operations=operations,
                issued_seq=issued,
                expires_seq=issued + ttl,
            )

    def register_evidence(self, evidence: Evidence) -> Hash:
        """Store evidence so the gate can resolve it by hash; also put it in the CAS."""
        self._evidence[evidence.hash] = evidence
        self._cas.put(evidence.hash.encode("ascii"))
        return evidence.hash

    def store_artifact(self, data: bytes) -> Hash:
        """Put a content-addressed artifact in the CAS; return its hash."""
        return self._cas.put(data)

    def has_artifact(self, artifact_hash: Hash) -> bool:
        return self._cas.has(artifact_hash)

    def advance(
        self,
        *,
        token: CapabilityToken,
        goal_id: str,
        run_id: str,
        from_state: StageId,
        to_state: StageId,
        weight_class: WeightClass,
        artifact_under_review: Hash,
        validation: ValidationClaim,
        changed_paths: Sequence[str] = (),
        powers_exercised: dict[str, Role] | None = None,
    ) -> TransitionResult:
        current = self.inspect(goal_id)
        if current != from_state.value:
            raise GoalNotAtStage(f"goal {goal_id} is at {current}, not {from_state.name}")
        evidence_refs = tuple(ref for claim in validation.claims for ref in claim.evidence_refs)
        classifier = (lambda _req: classify_paths(changed_paths)) if changed_paths else None
        gate = Gate(self._broker, self._evidence.__getitem__, classify_change=classifier)
        request = TransitionRequest(
            authority=token,
            goal_id=goal_id,
            run_id=run_id,
            from_state=from_state,
            to_state=to_state,
            evidence=evidence_refs,
            validation=validation,
        )
        with traced(
            "propose_transition",
            logger=self._log,
            meter=self._meter,
            goal=goal_id,
            to=to_state.value,
        ):
            result = gate.propose_transition(
                request,
                weight_class=weight_class,
                current_seq=self._current_seq(),
                artifact_under_review=artifact_under_review,
                powers_exercised=powers_exercised,
            )
        if result.outcome is Outcome.COMMITTED:
            seq = self._ledger.append(
                Event(
                    1,
                    TRANSITION_COMMITTED,
                    {
                        "goal_id": goal_id,
                        "run_id": run_id,
                        "from_state": from_state.value,
                        "to_state": to_state.value,
                    },
                )
            )
            return replace(result, committed_seq=seq)
        self._log.warning(
            "transition_denied", goal=goal_id, outcome=result.outcome.value, reason=result.reason
        )
        return result

    def seal(
        self,
        *,
        token: CapabilityToken | None,
        goal_id: str,
        run_id: str,
        artifact_bundle: Hash,
        verdict_ref: Hash,
        adversary_ref: Hash,
    ) -> SealRecord:
        if token is None:
            raise Unauthenticated("seal requires a capability token")
        try:
            self._broker.verify(
                token,
                goal_id=goal_id,
                run_id=run_id,
                stage=token.bound_to.stage,
                role=token.bound_to.role,
                operation=REQUEST_SEAL_OP,
                current_seq=self._current_seq(),
            )
        except CapabilityError as exc:
            raise Unauthenticated(f"seal not authorised: {exc}") from exc
        with traced("request_seal", logger=self._log, meter=self._meter, goal=goal_id):
            return self._seal_authority.seal(
                goal_id=goal_id,
                run_id=run_id,
                artifact_bundle=artifact_bundle,
                verdict_ref=verdict_ref,
                adversary_ref=adversary_ref,
            )

    # ---- read models ----

    def ledger_events(self) -> list[LedgerRow]:
        return self._ledger.read()

    def inspect(self, goal_id: str) -> str | None:
        return replay(self._ledger, GoalStates()).state.get(goal_id)

    def goal_states(self) -> dict[str, str]:
        return replay(self._ledger, GoalStates()).state

    def replay_and_verify(self) -> Projection[dict[str, str]]:
        projection = replay(self._ledger, GoalStates())
        verify_against_head(self._ledger, GoalStates(), projection)
        return projection


# ---- helpers + a scripted demo (the "end-to-end CLI script") --------------


def make_deterministic_evidence(claim_id: str, artifact_hash: Hash, command: str) -> Evidence:
    """Build a deterministic Evidence whose result the kernel can reproduce."""
    ev_hash = sha256(f"{claim_id}:{artifact_hash}:{command}".encode()).hexdigest()
    proc = subprocess.run(command.split(), capture_output=True, text=True, check=False)
    return Evidence(
        hash=ev_hash,
        kind=EvidenceKind.TEST,
        claim_id=claim_id,
        artifact_hash=artifact_hash,
        environment_hash="env" + "0" * 61,
        reproducible_command=command,
        producer=EvidenceProducer(role=Role.BUILDER, session="demo"),
        determinism=Determinism.DETERMINISTIC,
        result={"exit_code": proc.returncode, "stdout": proc.stdout},
        attestation="kernel-sig",
    )


def _print(obj: object) -> None:
    print(json.dumps(obj, indent=2, sort_keys=True))


def run_demo() -> ControlPlane:
    """Drive a goal through several Derivation-chamber stages and print the ledger. Returns the
    plane so callers/tests can inspect it."""
    plane = ControlPlane(Ledger(InMemoryLedgerStore()), SigningKey.generate())
    goal = plane.create_goal("demo goal", WeightClass.SUBSTANTIAL)
    run = "r-1"
    artifact = "a" * 64
    chain: Iterable[tuple[StageId, StageId]] = (
        (StageId.RAW, StageId.RE_DERIVE),
        (StageId.RE_DERIVE, StageId.INTAKE),
        (StageId.INTAKE, StageId.TRIAGE),
    )
    for from_state, to_state in chain:
        token = plane.acquire_token(
            goal_id=goal,
            run_id=run,
            stage=from_state,
            role=Role.BUILDER,
            session="demo",
            operations=(PROPOSE_TRANSITION_OP,),
        )
        evidence = make_deterministic_evidence("advances", artifact, "echo ok")
        plane.register_evidence(evidence)
        validation = ValidationClaim(
            gate_id="G-Derive",
            claims=(Claim(id="advances", statement="derives", evidence_refs=(evidence.hash,)),),
            producer=Role.BUILDER,
            produced_against=artifact,
        )
        result = plane.advance(
            token=token,
            goal_id=goal,
            run_id=run,
            from_state=from_state,
            to_state=to_state,
            weight_class=WeightClass.SUBSTANTIAL,
            artifact_under_review=artifact,
            validation=validation,
        )
        _print({"advance": f"{from_state.name}->{to_state.name}", "outcome": result.outcome.value})
    _print({"goal_state": plane.inspect(goal), "ledger_len": len(plane.ledger_events())})
    return plane


def _calibrate(canary_dir: str) -> int:
    """Run the standing canary calibration against the live Court. Exit 0 if calibrated, else 3."""
    from runtime.calibration import calibrate

    report = calibrate(canary_dir)
    _print(
        {
            "calibration": "PASS" if report.passed else "QUARANTINE",
            "results": [
                {"canary": r.canary_id, "passed": r.passed, "detail": r.detail}
                for r in report.results
            ],
        }
    )
    return 0 if report.passed else 3


def _amend(proposal_path: str, *, keys_path: str, cas_dir: str) -> int:
    """Prepare an amendment for the human ratification gate. Applies NOTHING (§7.4).

    Exit: 0 AWAITING_RATIFICATION (ready for founder sign-off) · 4 NOT_AN_AMENDMENT (use soft loop)
    · 5 ADVERSARY_INCOMPLETE (not ready)."""
    from kernel.cas import CAS, FilesystemCasStore
    from kernel.keystore import load_or_create_signing_key
    from runtime.amendment import AmendmentStatus, parse_proposal, prepare_amendment
    from runtime.integrations import ClaudeCodeRuntime

    proposal = parse_proposal(json.loads(Path(proposal_path).read_text(encoding="utf-8")))
    packet = prepare_amendment(
        proposal,
        signing_key=load_or_create_signing_key(keys_path),
        cas=CAS(FilesystemCasStore(Path(cas_dir))),
        adversary_runtime=ClaudeCodeRuntime(),  # LIVE — the isolated ratification adversary
    )
    _print(
        {
            "proposal": packet.proposal.proposal_id,
            "classification": packet.classification,
            "status": packet.status.value,
            "applied": packet.applied,  # always False — the runtime never amends the TCB
            "adversary_trace": packet.adversary_trace_ref,
            "detail": packet.detail,
        }
    )
    return {
        AmendmentStatus.AWAITING_RATIFICATION: 0,
        AmendmentStatus.NOT_AN_AMENDMENT: 4,
        AmendmentStatus.ADVERSARY_INCOMPLETE: 5,
    }[packet.status]


def _self_host(backlog_path: str, *, db_path: str, keys_path: str, canary_dir: str) -> int:
    """Run a backlog through the LIVE soft loop (real claude sessions — needs auth + env)."""
    from kernel.cas import (
        CAS,
        FilesystemCasStore,
    )
    from kernel.keystore import load_or_create_signing_key
    from kernel.ledger_sqlite import SqliteLedgerStore
    from runtime.calibration import calibrate
    from runtime.integrations import ClaudeCodeRuntime
    from runtime.orchestrator import RunStatus
    from runtime.selfhost import outcome_summary, parse_backlog, run_backlog

    # Standing FR-2/FR-3 tripwire (PAEOS-7 §5.3): a blunted Court must never seal. A canary miss
    # QUARANTINES — no backlog work runs, no seal is possible.
    calibration = calibrate(canary_dir)
    if not calibration.passed:
        _print(
            {
                "quarantine": "canary calibration failed — refusing to run",
                "misses": [
                    {"canary": r.canary_id, "detail": r.detail} for r in calibration.misses
                ],
            }
        )
        return 3

    backlog = parse_backlog(json.loads(Path(backlog_path).read_text(encoding="utf-8")))
    state_dir = Path(db_path).parent
    ledger = Ledger(SqliteLedgerStore(db_path))
    signing_key = load_or_create_signing_key(keys_path)
    cas = CAS(FilesystemCasStore(state_dir / "cas"))
    outcomes = run_backlog(
        backlog,
        ledger=ledger,
        signing_key=signing_key,
        cas=cas,
        # LIVE — the real claude CLI. Seed each session workspace from the repo (edit objectives +
        # constitution) and materialize injected context from the CAS (B2.I/B2.J); headless writes
        # auto-apply (acceptEdits).
        agent_runtime=ClaudeCodeRuntime(workspace_source=Path.cwd(), artifact_resolver=cas.get),
        # B2.N: verify each reproducible_command against a workspace with the change applied.
        repo_root=Path.cwd(),
    )
    _print(outcome_summary(outcomes))
    return 0 if all(o.status is RunStatus.SEALED for o in outcomes) else 2


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="paeos", description="PAEOS control plane")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("demo", help="drive a goal through several stages end-to-end")
    sh = sub.add_parser("self-host", help="run a JSON backlog through the live soft loop (R4)")
    sh.add_argument("backlog", help="path to a JSON backlog of intakes")
    sh.add_argument("--db", default="ops/state/ledger.db", help="durable ledger path (SQLite)")
    sh.add_argument("--keys", default="ops/keys/kernel_ed25519.key", help="kernel signing key path")
    sh.add_argument("--canaries", default="constitution/canaries", help="canary dir (tripwire)")
    cal = sub.add_parser("calibrate", help="run the standing canary calibration (FR-2 tripwire)")
    cal.add_argument("--canaries", default="constitution/canaries", help="canary directory")
    am = sub.add_parser("amend", help="prepare a constitutional amendment for the human gate")
    am.add_argument("proposal", help="path to a JSON amendment proposal")
    am.add_argument("--keys", default="ops/keys/kernel_ed25519.key", help="kernel signing key path")
    am.add_argument("--cas", default="ops/state/cas", help="CAS directory for the diff + review")
    args = parser.parse_args(argv)
    if args.command == "demo":
        run_demo()
        return 0
    if args.command == "calibrate":
        return _calibrate(args.canaries)
    if args.command == "amend":
        return _amend(args.proposal, keys_path=args.keys, cas_dir=args.cas)
    if args.command == "self-host":
        return _self_host(
            args.backlog, db_path=args.db, keys_path=args.keys, canary_dir=args.canaries
        )
    return 1


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
