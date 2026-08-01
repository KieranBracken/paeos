"""Live fully-autonomous self-hosting run — Phase 3 Milestone 1.

The culminating composition: a live `claude` session (launched by `ClaudeCodeRuntime` with
`--mcp-config`) reaches the **CourtServer** MCP tool, which writes the session's own probative
evidence into the **court pool**; the `SoftLoop` pulls that evidence via the `EvidenceSource`
port and adjudicates it; the whole loop is pulled by the `ContinuousScheduler` (Stage-19 RESTART)
and bounded by the `EconomicGovernor` (K11 budget conservation).

    claude --mcp-config → court_server.py → FileCourtEvidencePool → EvidenceSource → seal

This is a **deployment** entry point (needs `claude` auth + real tokens), not unit-tested — the
adapters it composes are (`runtime/transports/`, `runtime/scheduler.py`, `runtime/integrations`).
The core runtime it drives imports zero vendor SDK; only `runtime/transports/mcp/` touches MCP.

Usage:  python ops/autonomous_run.py <backlog.json> <state_dir>
"""

from __future__ import annotations

import json
import sys
import uuid
from pathlib import Path

from kernel.cas import CAS, FilesystemCasStore
from kernel.keystore import load_or_create_signing_key
from kernel.ledger import Ledger
from kernel.ledger_sqlite import SqliteLedgerStore
from runtime.evolution import EvolutionLayer
from runtime.integrations import ClaudeCodeRuntime
from runtime.orchestrator import Intake, RunOutcome, RunStatus, SoftLoop
from runtime.scheduler import ContinuousScheduler, EconomicGovernor, GlobalBudget
from runtime.selfhost import DEFAULT_BUDGETS, parse_backlog
from runtime.transports.mcp.transport import McpWorkerTransport


def build_scheduler(
    state_dir: Path, repo_root: Path, *, global_budget: GlobalBudget
) -> tuple[ContinuousScheduler, EvolutionLayer, Ledger]:
    """Wire the live autonomous loop over `state_dir`, driving builds against `repo_root`."""
    state_dir.mkdir(parents=True, exist_ok=True)

    # The evidence pool + the --mcp-config that launches the court server against THIS pool. The
    # live builder session submits to it via the `submit_evidence` MCP tool; we read it back here.
    transport = McpWorkerTransport(state_dir / "court")
    config_file = state_dir / "mcp-config.json"
    config_file.write_text(json.dumps(transport.mcp_config()), encoding="utf-8")

    cas = CAS(FilesystemCasStore(state_dir / "cas"))
    runtime = ClaudeCodeRuntime(
        workspace_source=repo_root,  # B2.J: seed the constitution + write scopes into the sandbox
        artifact_resolver=cas.get,
        mcp_config_path=config_file,
    )
    ledger = Ledger(SqliteLedgerStore(state_dir / "ledger.db"))
    signing_key = load_or_create_signing_key(state_dir / "seal.key")
    loop = SoftLoop(
        ledger=ledger,
        signing_key=signing_key,
        cas=cas,
        agent_runtime=runtime,
        budget_by_class=DEFAULT_BUDGETS,
        repo_root=repo_root,  # B2.N: the court verifies each command in a workspace WITH the change
    )
    evolution = EvolutionLayer(scar_store=loop.scar_store)  # sole L3 author (Stage 17)

    def run_one(intake: Intake) -> RunOutcome:
        run_id = "r-" + uuid.uuid4().hex[:8]  # unique per run: keys this run's court pool + prompt
        outcome = loop.run(
            objective=intake.objective,
            changed_paths=intake.changed_paths,
            plan_write_scopes=intake.plan_write_scopes,
            builder_evidence=(),  # autonomous: the builder SUBMITS its own evidence via the court
            goal_signature=intake.goal_signature,
            verifiable=intake.verifiable,
            reversible=intake.reversible,
            run_id=run_id,
            evidence_source=transport,  # the EvidenceSource port — MCP is just one implementation
        )
        evolution.run(
            outcome, goal_signature=intake.goal_signature, changed_paths=intake.changed_paths
        )
        return outcome

    governor = EconomicGovernor(global_budget)
    scheduler = ContinuousScheduler(
        run_one, governor=governor, budget_by_class=DEFAULT_BUDGETS
    )
    return scheduler, evolution, ledger


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if len(argv) != 2:
        print("usage: python ops/autonomous_run.py <backlog.json> <state_dir>", file=sys.stderr)
        return 64
    backlog_path, state_dir = Path(argv[0]), Path(argv[1])
    repo_root = Path.cwd()

    backlog = parse_backlog(json.loads(backlog_path.read_text(encoding="utf-8")))
    scheduler, _evolution, ledger = build_scheduler(
        state_dir,
        repo_root,
        # A contained ceiling: enough for a few full-weight runs; halts (not spins) when exhausted.
        global_budget=GlobalBudget(tokens=4_000_000, wallclock_s=36_000, runs=6),
    )
    report = scheduler.run(backlog)

    sealed = [o for o in report.outcomes if o.status is RunStatus.SEALED]
    summary = {
        "runs": len(report.outcomes),
        "sealed": len(sealed),
        "stop_reason": report.stop_reason.value,
        "remaining_tokens": report.remaining.tokens,
        "outcomes": [
            {
                "goal_id": o.goal_id,
                "status": o.status.value,
                "detail": o.detail,
                "seal_hash": (o.seal.seal_hash if o.seal is not None else None),
            }
            for o in report.outcomes
        ],
        "ledger_head": ledger.verify_chain(),  # K3: the seal is on a verified hash chain
    }
    print(json.dumps(summary, indent=2))
    # Genuine success only if at least one run reached a real, adversary-PASS seal.
    return 0 if sealed else 2


if __name__ == "__main__":
    raise SystemExit(main())
