"""B1.D acceptance tests for the information barrier + isolated adversary (PAEOS-8 §10 / FR-3).

The adversary sees only the sealed bundle, never builder context; a self-exfil attempt (a
builder-private ref in the adversary's context) is refused (T1/SI-5).
"""

from __future__ import annotations

import pytest
from kernel.capability import CapabilityBroker
from kernel.cas import CAS, InMemoryCasStore
from kernel.types import ArtifactRef, Role
from nacl.signing import SigningKey
from runtime.claude_code import AgentDispatcher, AgentWrite, RunOutput
from runtime.review import BarrierViolation, InformationBarrierManager, ReviewHarness
from runtime.task_package import Budget, Cost, TaskPackage, TaskStatus

_ARTIFACT = ArtifactRef(hash="a" * 64, type="code")
_EVIDENCE = "e" * 64
_BUILDER_SCRATCH = ArtifactRef(hash="5" * 64, type="builder-scratch")
_BUILDER_PLAN = ArtifactRef(hash="7" * 64, type="builder-plan")


def _bundle() -> tuple[InformationBarrierManager, object]:
    ibm = InformationBarrierManager()
    return ibm, ibm.seal(artifact_refs=(_ARTIFACT,), evidence_refs=(_EVIDENCE,))


class _MockRuntime:
    def __init__(self) -> None:
        self.received: TaskPackage | None = None

    def run(self, package: TaskPackage) -> RunOutput:
        self.received = package
        return RunOutput(
            status=TaskStatus.COMPLETE,
            writes=(AgentWrite("review/adversary_report.md", b"blocking dissent"),),
            evidence=(),
            trace=b"adversary transcript",
            cost=Cost(tokens=5000, wallclock_s=2.0, model_ver="gemini-x"),
        )


# ---- the bundle is all the adversary sees ---------------------------------


def test_adversary_context_is_bundle_only() -> None:
    ibm, bundle = _bundle()
    context = ibm.adversary_context(bundle)  # type: ignore[arg-type]
    hashes = {r.hash for r in context}
    assert hashes == {_ARTIFACT.hash, _EVIDENCE}  # artifact(s) + evidence, nothing else
    assert _BUILDER_SCRATCH.hash not in hashes


def test_isolation_holds_for_bundle_only_context() -> None:
    ibm, bundle = _bundle()
    ibm.verify_isolation(
        ibm.adversary_context(bundle),  # type: ignore[arg-type]
        (_BUILDER_SCRATCH, _BUILDER_PLAN),
    )  # no raise — disjoint


# ---- Adversary self-exfil (T1/SI-5) ---------------------------------------


def test_self_exfil_is_refused() -> None:
    ibm = InformationBarrierManager()
    builder_private = (_BUILDER_SCRATCH,)
    # a context that (maliciously) smuggles a builder-private ref alongside the bundle
    leaky = (_ARTIFACT, _BUILDER_SCRATCH)
    with pytest.raises(BarrierViolation):
        ibm.verify_isolation(leaky, builder_private)


# ---- review harness dispatches an isolated adversary ----------------------


def _harness(runtime: _MockRuntime) -> ReviewHarness:
    cas = CAS(InMemoryCasStore())
    broker = CapabilityBroker(SigningKey.generate())
    dispatcher = AgentDispatcher(broker, cas, runtime, clock=lambda: 0)
    return ReviewHarness(InformationBarrierManager(), dispatcher)


def test_review_dispatches_adversary_scoped_to_bundle() -> None:
    runtime = _MockRuntime()
    harness = _harness(runtime)
    _ibm, bundle = _bundle()
    result = harness.review(
        goal_id="g", run_id="r", session="adversary-1", bundle=bundle,  # type: ignore[arg-type]
        budget=Budget(200000, 900, 1),
    )
    assert result.status is TaskStatus.COMPLETE
    package = runtime.received
    assert package is not None
    assert package.role is Role.ADVERSARY
    # the adversary's context is the bundle only; no builder-private ref present
    assert {r.hash for r in package.context_refs} == {_ARTIFACT.hash, _EVIDENCE}
    assert package.permissions.mcp_servers == ("constitution",)  # not memory / builder
    assert package.permissions.read_scopes == (bundle.bundle_hash,)  # type: ignore[attr-defined]
    assert package.permissions.write_scopes == ("review/adversary_report.md",)  # report only


def test_review_refuses_when_bundle_would_leak_builder_private() -> None:
    # if a builder-private ref somehow appears in the bundle, the harness refuses before dispatch
    ibm = InformationBarrierManager()
    leaky_bundle = ibm.seal(artifact_refs=(_ARTIFACT, _BUILDER_SCRATCH), evidence_refs=(_EVIDENCE,))
    runtime = _MockRuntime()
    harness = _harness(runtime)
    with pytest.raises(BarrierViolation):
        harness.review(
            goal_id="g", run_id="r", session="a", bundle=leaky_bundle,
            budget=Budget(1, 1, 0), builder_private=(_BUILDER_SCRATCH,),
        )
    assert runtime.received is None  # never dispatched
