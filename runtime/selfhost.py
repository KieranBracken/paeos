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

import re
from collections.abc import Mapping
from pathlib import Path

from kernel.cas import CAS, content_hash
from kernel.evidence import Determinism, Evidence, EvidenceKind, EvidenceProducer
from kernel.ledger import JsonValue, Ledger
from kernel.types import Role, WeightClass
from nacl.signing import SigningKey

from runtime.claude_code import AgentRuntime
from runtime.evolution import EvolutionLayer

# RB-0008: autonomous friction detection — record structural gaps as DEBT/RB items on disk.
from runtime.friction import FrictionCategory, classify_friction, record_friction
from runtime.memory import ScarStore
from runtime.orchestrator import Intake, RunOutcome, SelfHostRunner, SoftLoop
from runtime.sidecar_scorer import SidecarStageScorer
from runtime.task_package import Budget

__all__ = [
    "DEFAULT_BUDGETS",
    "infer_write_scopes",
    "outcome_summary",
    "parse_backlog",
    "run_backlog",
]

DEFAULT_BUDGETS: dict[WeightClass, Budget] = {
    # Entry 143 recalibration (RB-0029): measured real cost of a 6-stage GLM-5.3 run
    # (5 planner stages + IMPLEMENT, high thinking) was 1,233,214 tokens (~205k/stage).
    # The previous 400k ROUTINE ceiling made every run halt at the adversary charge —
    # no intake could ever seal. Ceilings now sized from that measurement.
    # RB-0030 (run 5, g-19803efbff21): full-repo workspace seeding blew this up to
    # 2.8M tokens for 3 stages. Seeding is now scoped to write_scopes (RB-0030
    # remediation), cutting per-stage context ~90%; ceilings raised once more as
    # headroom so a healthy run never halts at the adversary charge again.
    WeightClass.ROUTINE: Budget(4_000_000, 5400, 2),
    WeightClass.SUBSTANTIAL: Budget(8_000_000, 10800, 3),
    WeightClass.KERNEL_TOUCHING: Budget(12_000_000, 21600, 3),
}

_DEFAULT_ENV_HASH = content_hash(b"paeos-selfhost-env")

VALID_TOP_DIRS: tuple[str, ...] = (
    "architecture/",
    "backlog/",
    "cli/",
    "constitution/",
    "derivation/",
    "design/",
    "docs/",
    "genesis/",
    "kernel/",
    "ledger/",
    "methodology/",
    "operations/",
    "ops/",
    "plan/",
    "prompts/",
    "proposals/",
    "reviews/",
    "runtime/",
    "sakg/",
    "skills/",
    "spec/",
    "templates/",
    "tests/",
)


def infer_write_scopes(
    objective: str,
    accept: tuple[str, ...],
    explicit_changed: tuple[str, ...],
    explicit_scopes: tuple[str, ...],
) -> tuple[str, ...]:
    """Infer required write scopes from declared deliverables and explicit scopes (DEBT-0023)."""
    found = set(explicit_changed) | set(explicit_scopes)
    text = objective + " " + " ".join(accept)
    for word in re.findall(r"[a-zA-Z0-9_.-]+/[a-zA-Z0-9_./*-]+", text):
        top = word.split("/")[0] + "/"
        if top in VALID_TOP_DIRS:
            found.add(top)

    top_level = {p for p in found if p in VALID_TOP_DIRS}
    non_redundant = set()
    for p in found:
        top = p.split("/")[0] + "/"
        if top in top_level and p != top:
            continue
        non_redundant.add(p)

    return tuple(sorted(non_redundant))


def parse_backlog(raw: object) -> list[Intake]:
    """Parse a JSON backlog (from `json.loads`) into `Intake`s. ValueError if malformed."""
    if not isinstance(raw, list):
        raise ValueError("backlog must be a JSON list of intakes")
    return [_parse_intake(item) for item in raw]


def _parse_intake(item: object) -> Intake:
    obj = _as_object(item, "intake")
    objective = _req_str(obj, "objective")
    accept = _str_tuple(obj.get("accept", []))
    changed_paths = _str_tuple(obj.get("changed_paths", []))
    plan_write_scopes = _str_tuple(obj.get("plan_write_scopes", []))
    evidence = tuple(_parse_evidence(e) for e in _as_list(obj.get("builder_evidence", [])))

    inferred_scopes = infer_write_scopes(objective, accept, changed_paths, plan_write_scopes)
    inferred_changed = tuple(sorted(set(changed_paths) | set(inferred_scopes)))

    return Intake(
        objective=objective,
        changed_paths=inferred_changed,
        plan_write_scopes=inferred_scopes,
        builder_evidence=evidence,
        goal_signature=_as_str(obj.get("goal_signature")) or "",
        verifiable=_as_bool(obj.get("verifiable")),
        reversible=_as_bool(obj.get("reversible")),
    )


def _parse_evidence(raw: object) -> Evidence:
    obj = _as_object(raw, "evidence")
    command = _req_str(obj, "command")
    claim_id = _req_str(obj, "claim_id")
    artifact_hash = _req_str(obj, "artifact_hash")
    if artifact_hash == "live":
        # Live-intake sentinel (Entry 142): the artifact does not exist yet, so its hash is
        # unknowable at authoring time. The kernel REBINDS it to the real artifact hash before
        # adjudication (orchestrator R4 live-binding) — the court still re-runs the command, so
        # anti-forgery is intact. Any other value must be a real hash; fabricated defaults are
        # forbidden (CRITICAL-002).
        artifact_hash = "0" * 64
    result: dict[str, JsonValue] = {
        "exit_code": _as_int(obj.get("exit_code")),
        "stdout": _as_str(obj.get("stdout")) or "",
    }
    return Evidence(
        hash=content_hash(f"{claim_id}:{command}".encode()),
        kind=EvidenceKind[_as_str(obj.get("kind")) or "TEST"],
        claim_id=claim_id,
        artifact_hash=artifact_hash,  # the rebound local — NOT a re-read (Entry 143 bugfix:
        # the previous `_req_str(obj, "artifact_hash")` discarded the "live" sentinel
        # conversion and passed the literal string "live" through as the hash)
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
        # DEBT-0057: explicitly non-persistent (hermetic) — no repository-relative default.
        sidecar_scorer=SidecarStageScorer(None),
        repo_root=repo_root,
    )
    runner = SelfHostRunner(loop)
    evolution = EvolutionLayer(scar_store=scar_store)  # the sole L3 author (Stage 17)
    from collections import deque

    queue = deque(backlog)
    outcomes: list[RunOutcome] = []
    while queue:
        intake = queue.popleft()
        (outcome,) = runner.run_backlog([intake])
        evolution.run(
            outcome, goal_signature=intake.goal_signature, changed_paths=intake.changed_paths
        )
        # RB-0008: autonomous friction detection — classify and record structural gaps.
        if repo_root is not None:
            sig = intake.goal_signature
            has_matching_scar = bool(loop.scar_store.match_scars(sig)) if sig else False
            friction = classify_friction(
                outcome, intake.changed_paths, has_matching_scar=has_matching_scar
            )
            if friction.category is not FrictionCategory.NONE:
                record_friction(friction, repo_root)
            if friction.high_leverage_intake is not None:
                from dataclasses import replace
                outcome = replace(outcome, high_leverage_intake=friction.high_leverage_intake)
                queue.appendleft(friction.high_leverage_intake)
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
