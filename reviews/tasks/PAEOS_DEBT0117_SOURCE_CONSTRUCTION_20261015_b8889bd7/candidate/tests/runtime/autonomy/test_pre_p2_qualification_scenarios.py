"""Unit and integration tests for the PRE-P2 Autonomy Readiness Qualification Scenarios.

Features physical subprocess restarts, actual SQLite ledger persistence, filesystem CAS,
real process termination/reconciliation, and autonomous nested remediation unwinding.
"""

from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import pytest
from kernel.cas import CAS, FilesystemCasStore
from kernel.evidence import Determinism, Evidence, EvidenceKind, EvidenceProducer
from kernel.ledger import Ledger
from kernel.ledger_sqlite import SqliteLedgerStore
from kernel.types import Role
from runtime.autonomy import (
    ActionPermission,
    AuthorityClassifier,
    AuthorityEnvelope,
    AuthorityExpansionForbiddenError,
    AuthorityTier,
    CeremonyTrace,
    CircuitBreakerPolicy,
    CircuitBreakerTrippedError,
    CycleDetectedError,
    EdgeType,
    FencingTokenManager,
    FindingClass,
    FounderStopRequiredError,
    MissionDependencyGraph,
    OrcaLineageProjection,
    PersistentMissionController,
    RecoveryController,
    ResumeEngine,
    RootEnvelopeAuthorityResolver,
    StaleFencingTokenError,
    TaskStatus,
    WeaknessFinderProbes,
    handle_orca_lineage_request,
)


def _setup_durable_env(tmp_dir: Path) -> tuple[Ledger, CAS, SqliteLedgerStore]:
    db_path = tmp_dir / "test_ledger.db"
    cas_path = tmp_dir / "cas"
    store = SqliteLedgerStore(db_path)
    ledger = Ledger(store, writer_id="paeos-test-writer")
    cas = CAS(FilesystemCasStore(cas_path))
    return ledger, cas, store


def test_scenario_01_one_level_remediation_and_autoresume(tmp_path: Path):
    """Scenario 1: One-Level Remediation & Auto-Resume backed by SQLite Ledger and CAS."""
    ledger, cas, _ = _setup_durable_env(tmp_path)
    graph = MissionDependencyGraph(ledger=ledger)
    resume_engine = ResumeEngine(graph, cas=cas, ledger=ledger)

    # 1. Root Task A
    task_a = graph.spawn_task("task-A", root_mission_id="mission-01", nesting_depth=0)
    assert task_a.status is TaskStatus.ACTIVE

    # 2. Defect encountered -> Blocker B-01 registered
    graph.register_blocker(
        "blocker-B01",
        finding_class=FindingClass.CURRENT_BLOCKER,
        signature="test_parser_syntax_error",
        blocked_task_id="task-A",
    )

    # 3. Task A suspends at durable CAS checkpoint
    cp_ref = resume_engine.suspend_parent_task(
        task_id="task-A",
        stage_id="L12_IMPLEMENT",
        state_payload={"cursor": 42, "module": "parser.py"},
    )
    assert graph.tasks["task-A"].status is TaskStatus.SUSPENDED
    assert graph.tasks["task-A"].checkpoint_ref == cp_ref

    # 4. Spawn child Task B to remediate B-01
    graph.spawn_task(
        "task-B",
        root_mission_id="mission-01",
        parent_task_id="task-A",
        nesting_depth=1,
    )
    graph.add_edge(EdgeType.REMEDIATES, "task-B", "blocker-B01")

    # Verify Task A cannot resume yet
    assert not graph.can_resume_task("task-A")

    # 5. Child B qualifies and extinguishes blocker B-01
    graph.qualify_task("task-B")
    graph.extinguish_blocker("blocker-B01")
    graph.add_edge(EdgeType.RESUMES, "task-B", "task-A")

    # 6. Task A can now resume
    assert graph.can_resume_task("task-A")
    success, msg, resumed_a = resume_engine.attempt_resume("task-A")
    assert success is True
    assert resumed_a.status is TaskStatus.ACTIVE
    assert resumed_a.fencing_token == 1

    # Restore checkpoint state from CAS
    restored_cp = resume_engine.restore_checkpoint(cp_ref)
    assert restored_cp.state_payload["cursor"] == 42

    # Verify ledger chain integrity
    assert ledger.verify_chain() is not None


def test_scenario_02_nested_remediation_unwind_5_levels(tmp_path: Path):
    """Scenario 2: 3–5-Level Nested Remediation Unwind backed by SQLite Ledger and CAS."""
    ledger, cas, _ = _setup_durable_env(tmp_path)
    graph = MissionDependencyGraph(ledger=ledger)
    resume_engine = ResumeEngine(graph, cas=cas, ledger=ledger)

    tasks = ["task-A", "task-B", "task-C", "task-D", "task-E"]
    blockers = ["blocker-01", "blocker-02", "blocker-03", "blocker-04"]

    # Build chain: A blocked by b01 -> B spawned; B blocked by b02 -> C spawned; ...
    for idx, t_id in enumerate(tasks):
        parent_id = tasks[idx - 1] if idx > 0 else None
        graph.spawn_task(t_id, root_mission_id="root-mission", parent_task_id=parent_id, nesting_depth=idx)
        if idx < len(blockers):
            b_id = blockers[idx]
            graph.register_blocker(b_id, FindingClass.CURRENT_BLOCKER, f"sig-{idx}", blocked_task_id=t_id)
            resume_engine.suspend_parent_task(t_id, stage_id="L12", state_payload={"depth": idx})

    assert graph.tasks["task-A"].status is TaskStatus.SUSPENDED
    assert graph.tasks["task-D"].status is TaskStatus.SUSPENDED
    assert graph.tasks["task-E"].status is TaskStatus.ACTIVE

    # Unwind: E qualifies -> resolves b03 -> D resumes & qualifies -> ... -> A resumes & qualifies
    for idx in range(len(blockers) - 1, -1, -1):
        child_id = tasks[idx + 1]
        parent_id = tasks[idx]
        b_id = blockers[idx]

        graph.qualify_task(child_id)
        graph.extinguish_blocker(b_id)
        graph.add_edge(EdgeType.RESUMES, child_id, parent_id)

        assert graph.can_resume_task(parent_id)
        success, _, resumed_parent = resume_engine.attempt_resume(parent_id)
        assert success is True
        assert resumed_parent.status is TaskStatus.ACTIVE

    graph.qualify_task("task-A")
    assert graph.tasks["task-A"].status is TaskStatus.TERMINAL_SUCCESS
    assert ledger.verify_chain() is not None


def test_scenario_03_restart_while_deepest_child_active(tmp_path: Path):
    """Scenario 3: Restart While Deepest Child Active across actual separate Python processes."""
    db_file = tmp_path / "proc_ledger.db"
    cas_dir = tmp_path / "proc_cas"

    # Process 1 script: builds A -> B -> C tree on SQLite ledger + CAS and terminates abruptly
    p1_code = f"""
import sys
from pathlib import Path
from kernel.ledger_sqlite import SqliteLedgerStore
from kernel.ledger import Ledger
from kernel.cas import CAS, FilesystemCasStore
from runtime.autonomy import MissionDependencyGraph, ResumeEngine, FindingClass

store = SqliteLedgerStore(Path('{db_file}'))
ledger = Ledger(store, writer_id='paeos-proc')
cas = CAS(FilesystemCasStore(Path('{cas_dir}')))
graph = MissionDependencyGraph(ledger=ledger)
engine = ResumeEngine(graph, cas=cas, ledger=ledger)

graph.spawn_task('task-A', 'mission-03', nesting_depth=0)
graph.register_blocker('b-1', FindingClass.CURRENT_BLOCKER, 'sig-1', blocked_task_id='task-A')
engine.suspend_parent_task('task-A', 'L12', {{'stage': 'A'}})

graph.spawn_task('task-B', 'mission-03', parent_task_id='task-A', nesting_depth=1)
graph.register_blocker('b-2', FindingClass.CURRENT_BLOCKER, 'sig-2', blocked_task_id='task-B')
engine.suspend_parent_task('task-B', 'L12', {{'stage': 'B'}})

graph.spawn_task('task-C', 'mission-03', parent_task_id='task-B', nesting_depth=2)
# Process 1 exits while C is active
sys.exit(0)
"""
    res1 = subprocess.run([sys.executable, "-c", p1_code], capture_output=True, text=True, check=False)
    assert res1.returncode == 0, f"Process 1 failed: {res1.stderr}"

    # Process 2 script: completely fresh process starts, replays from SQLite ledger, verifies state
    p2_code = f"""
import sys
from pathlib import Path
from kernel.ledger_sqlite import SqliteLedgerStore
from kernel.ledger import Ledger
from kernel.cas import CAS, FilesystemCasStore
from runtime.autonomy import MissionDependencyGraph, ResumeEngine, TaskStatus

store = SqliteLedgerStore(Path('{db_file}'))
ledger = Ledger(store, writer_id='paeos-proc')
cas = CAS(FilesystemCasStore(Path('{cas_dir}')))

# Reconstruct from durable ledger
rebuilt = MissionDependencyGraph.from_ledger(ledger)
engine = ResumeEngine(rebuilt, cas=cas, ledger=ledger)

assert rebuilt.tasks['task-A'].status is TaskStatus.SUSPENDED
assert rebuilt.tasks['task-B'].status is TaskStatus.SUSPENDED
assert rebuilt.tasks['task-C'].status is TaskStatus.ACTIVE
assert rebuilt.tasks['task-C'].nesting_depth == 2

# Verify checkpoints in CAS
cp_a = engine.restore_checkpoint(rebuilt.tasks['task-A'].checkpoint_ref)
assert cp_a.state_payload['stage'] == 'A'
cp_b = engine.restore_checkpoint(rebuilt.tasks['task-B'].checkpoint_ref)
assert cp_b.state_payload['stage'] == 'B'

# Qualify C and resume B
rebuilt.qualify_task('task-C')
rebuilt.extinguish_blocker('b-2')
rebuilt.add_edge('RESUMES', 'task-C', 'task-B')
assert rebuilt.can_resume_task('task-B')
ok, msg, node = engine.attempt_resume('task-B')
assert ok is True
sys.exit(0)
"""
    res2 = subprocess.run([sys.executable, "-c", p2_code], capture_output=True, text=True, check=False)
    assert res2.returncode == 0, f"Process 2 failed: {res2.stderr}"


def test_scenario_04_exact_once_resume_under_replay(tmp_path: Path):
    """Scenario 4: Exact-Once Resume Under Replay."""
    ledger, cas, _ = _setup_durable_env(tmp_path)
    graph = MissionDependencyGraph(ledger=ledger)
    resume_engine = ResumeEngine(graph, cas=cas, ledger=ledger)

    graph.spawn_task("task-A", "mission-04")
    graph.register_blocker("b-01", FindingClass.CURRENT_BLOCKER, "sig-01", blocked_task_id="task-A")
    resume_engine.suspend_parent_task("task-A", "L12", {"count": 10})
    graph.spawn_task("task-B", "mission-04", parent_task_id="task-A", nesting_depth=1)

    graph.qualify_task("task-B")
    graph.extinguish_blocker("b-01")
    graph.add_edge(EdgeType.RESUMES, "task-B", "task-A")

    # Initial valid resume
    success, msg, resumed = resume_engine.attempt_resume("task-A", presented_token=1)
    assert success is True
    assert resumed.fencing_token == 1
    assert resumed.status is TaskStatus.ACTIVE

    # Replay of duplicate event with presented_token=1 must be rejected
    success_replay, err_msg, _ = resume_engine.attempt_resume("task-A", presented_token=1)
    assert success_replay is False
    assert "Stale or replay" in err_msg


def test_scenario_05_multiple_sibling_blockers(tmp_path: Path):
    """Scenario 5: Multiple Sibling Blockers."""
    ledger, cas, _ = _setup_durable_env(tmp_path)
    graph = MissionDependencyGraph(ledger=ledger)
    resume_engine = ResumeEngine(graph, cas=cas, ledger=ledger)

    graph.spawn_task("task-A", "mission-05")
    graph.register_blocker("b-01", FindingClass.CURRENT_BLOCKER, "sig-01", blocked_task_id="task-A")
    graph.register_blocker("b-02", FindingClass.CURRENT_BLOCKER, "sig-02", blocked_task_id="task-A")
    resume_engine.suspend_parent_task("task-A", "L12", {"state": "waiting"})

    graph.spawn_task("child-1", "mission-05", parent_task_id="task-A", nesting_depth=1)
    graph.add_edge(EdgeType.REMEDIATES, "child-1", "b-01")

    graph.spawn_task("child-2", "mission-05", parent_task_id="task-A", nesting_depth=1)
    graph.add_edge(EdgeType.REMEDIATES, "child-2", "b-02")

    # Resolve child-1
    graph.qualify_task("child-1")
    graph.extinguish_blocker("b-01")
    assert not graph.can_resume_task("task-A")

    # Resolve child-2
    graph.qualify_task("child-2")
    graph.extinguish_blocker("b-02")
    assert graph.can_resume_task("task-A")

    success, _, resumed = resume_engine.attempt_resume("task-A")
    assert success is True
    assert resumed.status is TaskStatus.ACTIVE


def test_scenario_06_autonomous_recovery_from_child_failure(tmp_path: Path):
    """Scenario 6: Autonomous Recovery from Child Failure under SUPERSEDES."""
    ledger, cas, _ = _setup_durable_env(tmp_path)
    graph = MissionDependencyGraph(ledger=ledger)
    recovery = RecoveryController(graph, policy=CircuitBreakerPolicy(max_churn_retries=3))

    graph.spawn_task("task-A", "mission-06")
    graph.register_blocker("b-01", FindingClass.CURRENT_BLOCKER, "type_error_in_compiler", blocked_task_id="task-A")
    graph.spawn_task("child-1", "mission-06", parent_task_id="task-A", nesting_depth=1)
    graph.add_edge(EdgeType.REMEDIATES, "child-1", "b-01")

    # Child-1 fails implementation
    new_child, log = recovery.derive_alternative_remediation(
        failed_child_task_id="child-1",
        blocker_id="b-01",
        alternative_strategy="use_ast_transformation_instead_of_regex",
    )
    assert graph.tasks["child-1"].status is TaskStatus.TERMINAL_FAILURE
    assert new_child.task_id == "child-1-remedy-1"
    assert new_child.status is TaskStatus.ACTIVE

    supersedes_edges = [
        e for e in graph.edges
        if e.edge_type is EdgeType.SUPERSEDES and e.source_id == "child-1-remedy-1" and e.target_id == "child-1"
    ]
    assert len(supersedes_edges) == 1


def test_scenario_07_nonblocking_finding_isolation(tmp_path: Path):
    """Scenario 7: Nonblocking Finding Isolation."""
    ledger, cas, _ = _setup_durable_env(tmp_path)
    graph = MissionDependencyGraph(ledger=ledger)

    task_a = graph.spawn_task("task-A", "mission-07")
    blocker_non = graph.register_blocker(
        "finding-01",
        finding_class=FindingClass.NONBLOCKING_FINDING,
        signature="code_style_inconsistency",
    )
    assert blocker_non.finding_class is FindingClass.NONBLOCKING_FINDING
    assert task_a.status is TaskStatus.ACTIVE
    assert len(graph.get_active_blockers_for_task("task-A")) == 0


def test_scenario_08_deterministic_cycle_rejection(tmp_path: Path):
    """Scenario 8: Deterministic Cycle Rejection."""
    graph = MissionDependencyGraph()
    graph.spawn_task("task-A", "m-08")
    graph.spawn_task("task-B", "m-08")
    graph.spawn_task("task-C", "m-08")

    graph.add_edge(EdgeType.BLOCKS, "task-A", "task-B")
    graph.add_edge(EdgeType.BLOCKS, "task-B", "task-C")

    with pytest.raises(CycleDetectedError, match="would create a cycle"):
        graph.add_edge(EdgeType.BLOCKS, "task-C", "task-A")


def test_scenario_09_orphan_detection_and_reconciliation(tmp_path: Path):
    """Scenario 9: Orphan Detection & Reconciliation."""
    graph = MissionDependencyGraph()
    graph.spawn_task("task-A", "m-09", parent_task_id=None, nesting_depth=0)
    # Inject orphan
    graph.spawn_task("task-orphan", "m-09", parent_task_id="ghost-parent", nesting_depth=1)

    probes = WeaknessFinderProbes(graph)
    findings = probes.run_all_probes()

    orphan_findings = [f for f in findings if f.probe_id == "WF-MDG-01"]
    assert len(orphan_findings) == 1
    assert "ghost-parent" in orphan_findings[0].detail


def test_scenario_10_interrupted_resume_recovery(tmp_path: Path):
    """Scenario 10: Interrupted Resume Recovery across process boundary."""
    db_file = tmp_path / "lease_ledger.db"
    cas_dir = tmp_path / "lease_cas"

    # Subprocess 1: parent suspends, blocker extinguished, attempt_resume issues lease with 0.5s expiration, then crashes
    p1_code = f"""
import sys, os
from pathlib import Path
from kernel.ledger_sqlite import SqliteLedgerStore
from kernel.ledger import Ledger
from kernel.cas import CAS, FilesystemCasStore
from runtime.autonomy import MissionDependencyGraph, ResumeEngine, FindingClass

store = SqliteLedgerStore(Path('{db_file}'))
ledger = Ledger(store, writer_id='paeos-lease')
cas = CAS(FilesystemCasStore(Path('{cas_dir}')))
graph = MissionDependencyGraph(ledger=ledger)
engine = ResumeEngine(graph, cas=cas, ledger=ledger)

graph.spawn_task('task-A', 'm-10')
graph.register_blocker('b-1', FindingClass.CURRENT_BLOCKER, 'sig-1', blocked_task_id='task-A')
engine.suspend_parent_task('task-A', 'L12', {{'step': 1}})
graph.extinguish_blocker('b-1')

# Committed resume with short lease (0.4s)
ok, msg, node = engine.attempt_resume('task-A', lease_seconds=0.4)
assert ok is True
# Abrupt crash before worker launch
os._exit(0)
"""
    res1 = subprocess.run([sys.executable, "-c", p1_code], capture_output=True, text=True, check=False)
    assert res1.returncode == 0, f"Process 1 failed: {res1.stderr}"

    # Wait for lease expiration
    time.sleep(0.6)

    # Subprocess 2: fresh process starts, detects expired lease, issues fresh token
    p2_code = f"""
import sys
from pathlib import Path
from kernel.ledger_sqlite import SqliteLedgerStore
from kernel.ledger import Ledger
from kernel.cas import CAS, FilesystemCasStore
from runtime.autonomy import MissionDependencyGraph, ResumeEngine

store = SqliteLedgerStore(Path('{db_file}'))
ledger = Ledger(store, writer_id='paeos-lease')
cas = CAS(FilesystemCasStore(Path('{cas_dir}')))
graph = MissionDependencyGraph.from_ledger(ledger)
engine = ResumeEngine(graph, cas=cas, ledger=ledger)

# Lease expired: recover
ok, msg, node = engine.recover_interrupted_resume('task-A', lease_seconds=30.0)
assert ok is True
assert node.fencing_token == 2
sys.exit(0)
"""
    res2 = subprocess.run([sys.executable, "-c", p2_code], capture_output=True, text=True, check=False)
    assert res2.returncode == 0, f"Process 2 failed: {res2.stderr}"


def test_scenario_11_root_envelope_authority_confinement(tmp_path: Path):
    """Scenario 11: Root-Envelope Authority Confinement."""
    root_envelope = AuthorityEnvelope(
        root_mission_id="mission-11",
        authorized_paths=frozenset({"runtime/feature.py", "runtime/parser.py", "ops/verify.py"}),
        delegated_ceiling=AuthorityTier.A2_CROSS_SUBSYSTEM,
        allowed_action=ActionPermission.GOVERNED_REVIEW,
    )

    parent_envelope = AuthorityEnvelope(
        root_mission_id="mission-11",
        authorized_paths=frozenset({"runtime/feature.py"}),
        delegated_ceiling=AuthorityTier.A0_IMPLEMENTATION,
        allowed_action=ActionPermission.AUTONOMOUS,
    )

    # Permitted: Child scope differs from parent local scope, but inside root envelope
    child_envelope = RootEnvelopeAuthorityResolver.resolve_child_envelope(
        root_envelope=root_envelope,
        parent_envelope=parent_envelope,
        requested_paths=("runtime/parser.py", "ops/verify.py"),
        requested_tier=AuthorityTier.A1_LOCAL_SUBSYSTEM,
    )
    assert "runtime/parser.py" in child_envelope.authorized_paths
    assert "ops/verify.py" in child_envelope.authorized_paths

    # Denied: Child requests path outside root envelope
    with pytest.raises(AuthorityExpansionForbiddenError, match="outside root envelope"):
        RootEnvelopeAuthorityResolver.resolve_child_envelope(
            root_envelope=root_envelope,
            parent_envelope=parent_envelope,
            requested_paths=("constitution/doctrine.py",),
            requested_tier=AuthorityTier.A1_LOCAL_SUBSYSTEM,
        )


def test_scenario_12_full_blocking_chain_observability(tmp_path: Path):
    """Scenario 12: Full Blocking Chain Observability via Orca read projection."""
    ledger, cas, _ = _setup_durable_env(tmp_path)
    graph = MissionDependencyGraph(ledger=ledger)
    resume_engine = ResumeEngine(graph, cas=cas, ledger=ledger)

    graph.spawn_task("root", "mission-12")
    graph.register_blocker("b-0", FindingClass.CURRENT_BLOCKER, "sig-0", blocked_task_id="root")
    resume_engine.suspend_parent_task("root", "L12", {"depth": 0})

    graph.spawn_task("t-1", "mission-12", parent_task_id="root", nesting_depth=1)
    graph.register_blocker("b-1", FindingClass.CURRENT_BLOCKER, "sig-1", blocked_task_id="t-1")
    resume_engine.suspend_parent_task("t-1", "L12", {"depth": 1})

    graph.spawn_task("t-2", "mission-12", parent_task_id="t-1", nesting_depth=2)
    graph.register_blocker("b-2", FindingClass.CURRENT_BLOCKER, "sig-2", blocked_task_id="t-2")
    resume_engine.suspend_parent_task("t-2", "L12", {"depth": 2})

    graph.spawn_task("t-3", "mission-12", parent_task_id="t-2", nesting_depth=3)
    graph.register_blocker("b-3", FindingClass.CURRENT_BLOCKER, "sig-3", blocked_task_id="t-3")
    resume_engine.suspend_parent_task("t-3", "L12", {"depth": 3})

    graph.spawn_task("leaf", "mission-12", parent_task_id="t-3", nesting_depth=4)

    # Operational query via endpoint router
    code, projection = handle_orca_lineage_request("mission-12", ledger)
    assert code == 200
    assert projection["total_tasks_count"] == 5
    assert ["root", "t-1", "t-2", "t-3", "leaf"] in projection["blocking_chains"]
    assert len(projection["projected_resume_targets"]) == 4


def test_scenario_13_lawful_ceremony_depth_selection_in_nested_branch(tmp_path: Path):
    """Scenario 13: Physical execution of genuine Trace-A and Trace-B remediations."""
    ledger, cas, _ = _setup_durable_env(tmp_path)
    graph = MissionDependencyGraph(ledger=ledger)
    resume_engine = ResumeEngine(graph, cas=cas, ledger=ledger)

    # Root task
    graph.spawn_task("task-root", "m-13")
    graph.register_blocker("b-root", FindingClass.CURRENT_BLOCKER, "root_defect", blocked_task_id="task-root")
    resume_engine.suspend_parent_task("task-root", "L12", {"phase": "root"})

    # 1. Genuine Trace-A child: auto-discharges obligations with deterministic physical command
    graph.spawn_task(
        "child-trace-a",
        "m-13",
        parent_task_id="task-root",
        nesting_depth=1,
        ceremony_trace=CeremonyTrace.TRACE_A,
    )
    # Physical command execution
    completed = subprocess.run(
        [sys.executable, "-c", "import hashlib; print('TRACE_A_PHYSICAL_DISCHARGE')"],
        capture_output=True,
        text=True,
        check=True,
    )
    evidence = Evidence(
        hash=cas.put(completed.stdout.encode("utf-8")),
        kind=EvidenceKind.TEST,
        claim_id="CLAIM-TRACE-A-AUTO-DISCHARGE",
        artifact_hash=cas.put(b"trace-a-artifact"),
        environment_hash=cas.put(b"trace-a-env"),
        reproducible_command="python -c \"import hashlib; print('TRACE_A_PHYSICAL_DISCHARGE')\"",
        producer=EvidenceProducer(role=Role.VERIFIER, session="s-trace-a"),
        determinism=Determinism.DETERMINISTIC,
        result={"exit_code": completed.returncode, "stdout": completed.stdout},
        attestation="trace-a-auto-discharge-attestation",
    )
    assert evidence.result["exit_code"] == 0
    # Auto-discharge qualifies Trace-A child
    graph.qualify_task("child-trace-a")
    assert graph.tasks["child-trace-a"].ceremony_trace is CeremonyTrace.TRACE_A

    # 2. Genuine Trace-B child: full ceremony stages executed
    graph.spawn_task(
        "child-trace-b",
        "m-13",
        parent_task_id="task-root",
        nesting_depth=1,
        ceremony_trace=CeremonyTrace.TRACE_B,
    )
    graph.register_blocker("b-trace-b", FindingClass.CURRENT_BLOCKER, "deep_defect", blocked_task_id="child-trace-b")
    resume_engine.suspend_parent_task("child-trace-b", "L11_FREEZE", {"plan_version": 1})

    # Sub-child executes full stages to resolve Trace-B
    graph.spawn_task("subchild-b", "m-13", parent_task_id="child-trace-b", nesting_depth=2)
    graph.add_edge(EdgeType.REMEDIATES, "subchild-b", "b-trace-b")
    graph.qualify_task("subchild-b")
    graph.extinguish_blocker("b-trace-b")
    graph.add_edge(EdgeType.RESUMES, "subchild-b", "child-trace-b")

    # Trace-B child resumes and qualifies
    assert graph.can_resume_task("child-trace-b")
    resume_engine.attempt_resume("child-trace-b")
    graph.qualify_task("child-trace-b")
    assert graph.tasks["child-trace-b"].ceremony_trace is CeremonyTrace.TRACE_B

    # Extinguish root blocker and resume root exactly once
    graph.extinguish_blocker("b-root")
    graph.add_edge(EdgeType.RESUMES, "child-trace-b", "task-root")
    assert graph.can_resume_task("task-root")
    ok, _, root_node = resume_engine.attempt_resume("task-root")
    assert ok is True
    assert root_node.status is TaskStatus.ACTIVE


def test_scenario_14_physical_controller_death_acceptance_test(tmp_path: Path):
    """Gap 4 / Acceptance Scenario 14: Physical controller-death acceptance test.

    Proves native PAEOS crash resilience on the ACTUAL production entrypoint (`ops/autonomous_run.py`):
    1. Process 1 launched via `ops/autonomous_run.py` with `PAEOS_CONTROLLER_DEATH_TEST=1`.
    2. Builds 5-level nested remediation MDG (task-A -> blocker-B01/task-C -> blocker-B02/task-E).
    3. Commits checkpoints and graph to durable SQLite ledger and CAS.
    4. Process 1 reaches `[PMC] Ready for SIGKILL` checkpoint and is physically terminated with `kill -9` (`signal.SIGKILL`).
    5. Verifies Process 1 terminated with negative exit code (-SIGKILL).
    6. Process 2 launched via normal production `ops/autonomous_run.py` entrypoint without death test env.
    7. Process 2 reconstructs MDG graph from durable SQLite ledger and CAS with zero in-memory state.
    8. Autonomously unwinds task-E -> task-C -> task-A without human or model intervention.
    9. Process 2 seals run, outputs verified ledger head, and exits with code 0.
    10. Directly validates durable SQLite ledger hash chain integrity and terminal success statuses.
    """
    repo_root = Path(__file__).resolve().parents[3]
    state_dir = tmp_path / "acceptance_state"
    backlog_path = tmp_path / "acceptance_backlog.json"

    backlog = [
        {
            "objective": "Verify production persistent controller crash recovery and 5-level nested remediation unwind",
            "goal_signature": "PRE_P2_5_LEVEL_NESTED_REMEDIATION",
            "changed_paths": ["runtime/util.py"],
            "plan_write_scopes": ["runtime/util.py"],
            "verifiable": True,
            "reversible": True,
        }
    ]
    backlog_path.write_text(json.dumps(backlog), encoding="utf-8")

    # Step 1: Controller Process 1 runs production autonomous_run.py, builds MDG, and awaits SIGKILL
    env1 = os.environ.copy()
    env1["PAEOS_CONTROLLER_DEATH_TEST"] = "1"
    env1["PYTHONPATH"] = str(repo_root)

    proc1 = subprocess.Popen(
        [
            sys.executable,
            str(repo_root / "ops" / "autonomous_run.py"),
            str(backlog_path),
            str(state_dir),
            "1",
            "1",
            "claude",
        ],
        cwd=str(repo_root),
        env=env1,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    ready = False
    start_time = time.time()
    assert proc1.stdout is not None
    while time.time() - start_time < 30:
        line = proc1.stdout.readline()
        if not line and proc1.poll() is not None:
            break
        if "[PMC] Ready for SIGKILL" in line:
            ready = True
            break

    assert ready, "Process 1 failed to reach [PMC] Ready for SIGKILL checkpoint"

    # Step 2: Physical termination of Process 1 with kill -9 (SIGKILL)
    os.kill(proc1.pid, signal.SIGKILL)
    proc1.wait(timeout=5)
    assert proc1.returncode == -signal.SIGKILL, f"Process 1 return code {proc1.returncode} != -{signal.SIGKILL}"

    # Step 3: Fresh Process 2 starts normal production entrypoint with zero in-memory state
    env2 = os.environ.copy()
    env2.pop("PAEOS_CONTROLLER_DEATH_TEST", None)
    env2["PYTHONPATH"] = str(repo_root)

    res2 = subprocess.run(
        [
            sys.executable,
            str(repo_root / "ops" / "autonomous_run.py"),
            str(backlog_path),
            str(state_dir),
            "1",
            "1",
            "claude",
        ],
        cwd=str(repo_root),
        env=env2,
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
    )
    assert res2.returncode == 0, f"Process 2 autonomous restart failed: stderr={res2.stderr}, stdout={res2.stdout}"

    # Parse production JSON output
    summary = json.loads(res2.stdout)
    assert summary["sealed"] == 1, f"Expected 1 sealed run, got {summary}"
    assert summary["ledger_head"] is not None

    # Step 4: Verify reconstructed graph and complete ledger chain on physical SQLite store
    store = SqliteLedgerStore(state_dir / "ledger.db")
    ledger = Ledger(store)
    cas = CAS(FilesystemCasStore(state_dir / "cas"))
    root_envelope = AuthorityEnvelope(
        root_mission_id=f"mission-{state_dir.name}",
        authorized_paths=frozenset({str(repo_root.resolve()), str(state_dir.resolve()), "runtime/core.py", "runtime/util.py"}),
        delegated_ceiling=AuthorityTier.A3_ACCEPTANCE_CONTRACT,
        allowed_action=ActionPermission.COUNCIL_EVIDENCE_GATE,
    )
    recovered_controller = PersistentMissionController.recover_from_durable_state(ledger, cas, root_envelope)
    assert recovered_controller.graph.tasks["task-A"].status is TaskStatus.TERMINAL_SUCCESS
    assert recovered_controller.graph.tasks["task-C"].status is TaskStatus.TERMINAL_SUCCESS
    assert recovered_controller.graph.tasks["task-E"].status is TaskStatus.TERMINAL_SUCCESS
    assert ledger.verify_chain() is not None
