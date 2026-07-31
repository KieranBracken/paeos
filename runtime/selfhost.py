"""Self-hosting entry — parse a backlog and run it through the live soft loop (PAEOS-8 §12 R4).

The launchable form of B2.B: read a JSON backlog of `Intake`s, wire the `SelfHostRunner` over a
**durable** ledger (SQLite, DEBT-0003) and the **live** `ClaudeCodeRuntime` (B2.A), run each item,
and report the outcomes. The one live step (the `claude` CLI) is inside `ClaudeCodeRuntime`; here we
only compose it. `cli/paeos.py self-host` calls `run_backlog`; tests inject a scripted runtime.

Backlog JSON (a list of intakes):
    {"objective": str, "changed_paths": [str], "plan_write_scopes": [str],
     "goal_signature": str, "verifiable": bool, "reversible": bool,
     "builder_evidence": [{"claim_id": str, "kind": "TEST", "command": str,
                           "artifact_hash": str, "exit_code": int, "stdout": str}]}

Evidence is declared per intake for a *staged* run; a fully-live run flows evidence from the agent
via the court MCP (B2.B Observation 1) — the last live-integration refinement toward autonomous R4.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from kernel.cas import CAS, content_hash
from kernel.evidence import Determinism, Evidence, EvidenceKind, EvidenceProducer
from kernel.ledger import JsonValue, Ledger
from kernel.types import Role, WeightClass
from nacl.signing import SigningKey

from runtime.claude_code import AgentRuntime
from runtime.evolution import EvolutionLayer
from runtime.memory import ScarStore
from runtime.orchestrator import Intake, RunOutcome, SelfHostRunner, SoftLoop
from runtime.task_package import Budget

__all__ = ["DEFAULT_BUDGETS", "outcome_summary", "parse_backlog", "run_backlog"]

DEFAULT_BUDGETS: dict[WeightClass, Budget] = {
    WeightClass.ROUTINE: Budget(400_000, 1800, 2),
    WeightClass.SUBSTANTIAL: Budget(1_000_000, 5400, 3),
    WeightClass.KERNEL_TOUCHING: Budget(2_000_000, 10800, 3),
}

_DEFAULT_ENV_HASH = content_hash(b"paeos-selfhost-env")


def parse_backlog(raw: object) -> list[Intake]:
    """Parse a JSON backlog (from `json.loads`) into `Intake`s. ValueError if malformed."""
    if not isinstance(raw, list):
        raise ValueError("backlog must be a JSON list of intakes")
    return [_parse_intake(item) for item in raw]


def _parse_intake(item: object) -> Intake:
    obj = _as_object(item, "intake")
    evidence = tuple(_parse_evidence(e) for e in _as_list(obj.get("builder_evidence", [])))
    return Intake(
        objective=_req_str(obj, "objective"),
        changed_paths=_str_tuple(obj.get("changed_paths", [])),
        plan_write_scopes=_str_tuple(obj.get("plan_write_scopes", [])),
        builder_evidence=evidence,
        goal_signature=_as_str(obj.get("goal_signature")) or "",
        verifiable=_as_bool(obj.get("verifiable")),
        reversible=_as_bool(obj.get("reversible")),
    )


def _parse_evidence(raw: object) -> Evidence:
    obj = _as_object(raw, "evidence")
    command = _req_str(obj, "command")
    claim_id = _req_str(obj, "claim_id")
    result: dict[str, JsonValue] = {
        "exit_code": _as_int(obj.get("exit_code")),
        "stdout": _as_str(obj.get("stdout")) or "",
    }
    return Evidence(
        hash=content_hash(f"{claim_id}:{command}".encode()),
        kind=EvidenceKind[_as_str(obj.get("kind")) or "TEST"],
        claim_id=claim_id,
        artifact_hash=_req_str(obj, "artifact_hash"),
        environment_hash=_as_str(obj.get("environment_hash")) or _DEFAULT_ENV_HASH,
        reproducible_command=command,
        producer=EvidenceProducer(role=Role.BUILDER, session="backlog"),
        determinism=Determinism.DETERMINISTIC,
        result=result,
        attestation="pending-kernel-sig",
    )


def run_backlog(
    backlog: list[Intake],
    *,
    ledger: Ledger,
    signing_key: SigningKey,
    cas: CAS,
    agent_runtime: AgentRuntime,
    budget_by_class: Mapping[WeightClass, Budget] | None = None,
    repo_root: Path | None = None,
) -> list[RunOutcome]:
    """Run every intake through one shared soft loop; the Evolution Layer authors L3 memory.

    L1/L3 separation (IP-0005/0006, B2.G): the loop produces only an **L1** execution note on a
    remand and never writes a scar. The **Evolution Layer** is the **sole author of L3 memory**, at
    Stage 17, run by run — so scars still accumulate across the backlog (each authored scar is
    injectable into later runs) without the operational loop ever authoring or committing memory.
    """
    scar_store = ScarStore()
    loop = SoftLoop(
        ledger=ledger,
        signing_key=signing_key,
        cas=cas,
        agent_runtime=agent_runtime,
        budget_by_class=budget_by_class if budget_by_class is not None else DEFAULT_BUDGETS,
        scar_store=scar_store,
        repo_root=repo_root,
    )
    runner = SelfHostRunner(loop)
    evolution = EvolutionLayer(scar_store=scar_store)  # the sole L3 author (Stage 17)
    outcomes: list[RunOutcome] = []
    for intake in backlog:
        (outcome,) = runner.run_backlog([intake])
        evolution.run(
            outcome, goal_signature=intake.goal_signature, changed_paths=intake.changed_paths
        )
        outcomes.append(outcome)
    return outcomes


def outcome_summary(outcomes: list[RunOutcome]) -> list[dict[str, JsonValue]]:
    """A JSON-printable summary of a backlog run."""
    return [
        {
            "goal_id": o.goal_id,
            "status": o.status.value,
            "detail": o.detail,
            "seal_hash": o.seal.seal_hash if o.seal is not None else None,
        }
        for o in outcomes
    ]


# ---- small JSON coercion helpers ------------------------------------------


def _as_object(value: object, what: str) -> Mapping[str, object]:
    if not isinstance(value, dict):
        raise ValueError(f"{what} must be a JSON object")
    return {str(k): v for k, v in value.items()}


def _as_list(value: object) -> list[object]:
    if not isinstance(value, list):
        raise ValueError("expected a JSON list")
    return list(value)


def _str_tuple(value: object) -> tuple[str, ...]:
    return tuple(v for v in _as_list(value) if isinstance(v, str))


def _req_str(obj: Mapping[str, object], key: str) -> str:
    value = obj.get(key)
    if not isinstance(value, str):
        raise ValueError(f"field {key!r} must be a string")
    return value


def _as_str(value: object) -> str | None:
    return value if isinstance(value, str) else None


def _as_int(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        return 0
    return value


def _as_bool(value: object) -> bool:
    return value if isinstance(value, bool) else True
