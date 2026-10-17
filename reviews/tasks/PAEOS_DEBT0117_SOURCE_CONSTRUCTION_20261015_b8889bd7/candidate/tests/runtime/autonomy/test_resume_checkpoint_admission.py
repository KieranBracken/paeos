"""Checkpoint admission must precede every ordinary resume mutation."""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from dataclasses import replace
from types import SimpleNamespace

import pytest
from kernel.cas import CAS, FilesystemCasStore
from kernel.ledger import Ledger
from kernel.ledger_sqlite import SqliteLedgerStore
from runtime.autonomy.authority import FindingClass
from runtime.autonomy.mdg import MissionDependencyGraph, TaskStatus
from runtime.autonomy.resume_engine import ResumeEngine, TaskCheckpoint


@pytest.fixture(params=["filesystem", "memory"])
def env(tmp_path, request):
    store = SqliteLedgerStore(tmp_path / "ledger.db")
    ledger = Ledger(store, writer_id="checkpoint-admission-test")
    cas_root = tmp_path / "cas"
    cas = CAS(FilesystemCasStore(cas_root)) if request.param == "filesystem" else None
    graph = MissionDependencyGraph(ledger=ledger)
    engine = ResumeEngine(graph, cas=cas, ledger=ledger)
    graph.spawn_task("parent", root_mission_id="root")
    try:
        yield SimpleNamespace(
            graph=graph, engine=engine, ledger=ledger, cas=cas, cas_root=cas_root
        )
    finally:
        ledger.close()
        store.close()


def _checkpoint():
    return TaskCheckpoint("parent", "root", "L12_IMPLEMENT", 1.0, {"cursor": 7})


def _store_raw(env, raw):
    if env.cas is not None:
        return env.cas.put(raw)
    ref = hashlib.sha256(raw).hexdigest()
    env.engine._checkpoints[ref] = raw
    return ref


def _snapshot(env):
    return deepcopy(
        {
            "tasks": env.graph.tasks,
            "blockers": env.graph.blockers,
            "edges": env.graph.edges,
            "fencing": env.engine.fencing._tokens,
            "current_token": env.engine.fencing.current_token("parent"),
            "leases": env.engine._task_leases,
            "ledger_head": env.ledger.head(),
            "ledger_rows": env.ledger.read(),
        }
    )


def _assert_rejected_without_mutation(env, presented_token=1):
    before = _snapshot(env)
    success, reason, node = env.engine.attempt_resume(
        "parent", presented_token=presented_token
    )
    assert success is False
    assert isinstance(reason, str) and reason
    assert node is None
    assert _snapshot(env) == before
    assert MissionDependencyGraph.from_ledger(env.ledger).tasks == env.graph.tasks


def test_valid_checkpoint_resumes_once_and_records_lease_and_graph(env):
    ref = env.engine.store_checkpoint(_checkpoint())
    env.graph.suspend_task("parent", ref)
    before = env.ledger.head()

    success, reason, node = env.engine.attempt_resume("parent", presented_token=1)

    assert success is True
    assert reason
    assert node == env.graph.tasks["parent"]
    assert node.status is TaskStatus.ACTIVE
    assert node.checkpoint_ref == ref
    assert node.fencing_token == 1
    assert env.engine.fencing.current_token("parent") == 1
    assert env.engine._task_leases["parent"][0] == 1
    events = [row.event for row in env.ledger.read(before.seq + 1)]
    assert [event.kind for event in events] == ["MDG_LEASE_RECORD", "MDG_TASK_RESUMED"]
    assert events[0].payload["fencing_token"] == 1
    assert MissionDependencyGraph.from_ledger(env.ledger).tasks == env.graph.tasks

    _assert_rejected_without_mutation(env)
    _assert_rejected_without_mutation(env, presented_token=None)
    _assert_rejected_without_mutation(env, presented_token=2)


@pytest.mark.parametrize("checkpoint_ref", [None, ""])
def test_absent_checkpoint_reference_cannot_resume(env, checkpoint_ref):
    env.graph.suspend_task("parent", checkpoint_ref)
    _assert_rejected_without_mutation(env)


def test_missing_checkpoint_blob_cannot_resume(env):
    ref = hashlib.sha256(b"checkpoint never stored").hexdigest()
    env.graph.suspend_task("parent", ref)
    _assert_rejected_without_mutation(env)


def test_changed_checkpoint_bytes_cannot_resume(env):
    ref = env.engine.store_checkpoint(_checkpoint())
    env.graph.suspend_task("parent", ref)
    if env.cas is not None:
        (env.cas_root / ref[:2] / ref[2:]).write_bytes(b"changed checkpoint bytes")
    else:
        env.engine._checkpoints[ref] = b"changed checkpoint bytes"
    _assert_rejected_without_mutation(env)


@pytest.mark.parametrize("raw", [b"\xff", b"{", b"[]", b"null"])
def test_malformed_checkpoint_payload_cannot_resume(env, raw):
    env.graph.suspend_task("parent", _store_raw(env, raw))
    _assert_rejected_without_mutation(env)


@pytest.mark.parametrize(
    "missing", ["task_id", "root_mission_id", "stage_id", "captured_at_unix", "state_payload"]
)
def test_checkpoint_missing_required_field_cannot_resume(env, missing):
    payload = {
        "task_id": "parent",
        "root_mission_id": "root",
        "stage_id": "L12_IMPLEMENT",
        "captured_at_unix": 1.0,
        "state_payload": {"cursor": 7},
    }
    del payload[missing]
    env.graph.suspend_task("parent", _store_raw(env, json.dumps(payload).encode()))
    _assert_rejected_without_mutation(env)


@pytest.mark.parametrize("identity", [{"task_id": "other-task"}, {"root_mission_id": "other-root"}])
def test_validly_hashed_wrong_identity_checkpoint_cannot_resume(env, identity):
    checkpoint = replace(_checkpoint(), **identity)
    ref = env.engine.store_checkpoint(checkpoint)
    assert env.engine.restore_checkpoint(ref) == checkpoint
    env.graph.suspend_task("parent", ref)
    _assert_rejected_without_mutation(env)


def test_remaining_sibling_blocker_still_prevents_resume(env):
    env.engine.suspend_parent_task("parent", "L12_IMPLEMENT", {"cursor": 7})
    for blocker_id in ("first", "second"):
        env.graph.register_blocker(
            blocker_id, FindingClass.CURRENT_BLOCKER, blocker_id, blocked_task_id="parent"
        )
    env.graph.extinguish_blocker("first")
    _assert_rejected_without_mutation(env)

    env.graph.extinguish_blocker("second")
    assert env.engine.attempt_resume("parent", presented_token=1)[0] is True


@pytest.mark.parametrize("presented_token", [0, -1])
def test_stale_token_still_rejected_before_resume(env, presented_token):
    env.engine.suspend_parent_task("parent", "L12_IMPLEMENT", {"cursor": 7})
    _assert_rejected_without_mutation(env, presented_token=presented_token)
    assert env.engine.attempt_resume("parent", presented_token=1)[0] is True
