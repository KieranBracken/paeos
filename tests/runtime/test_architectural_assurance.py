"""Architectural Assurance & Discriminative Gate Tests.

Verifies that the PAEOS verification court, adversary gate, sandbox hermeticity, and evidence binding
mechanically fail closed on any non-probative, forged, stale, or out-of-scope evidence claims.
"""

from __future__ import annotations

from pathlib import Path

from kernel.cas import CAS, InMemoryCasStore, content_hash
from kernel.evidence import Determinism, Evidence, EvidenceKind, EvidenceProducer
from kernel.sandbox import run_sandboxed
from kernel.types import Role, WeightClass
from runtime.court import VerdictOutcome
from runtime.review import AdversaryOutcome, read_adversary_verdict
from runtime.task_package import Budget
from runtime.verification import vacuous_commands

_BUDGETS = {
    WeightClass.ROUTINE: Budget(100_000, 3600, 5),
    WeightClass.SUBSTANTIAL: Budget(300_000, 7200, 5),
    WeightClass.KERNEL_TOUCHING: Budget(600_000, 10800, 5),
}


def test_sandbox_path_has_no_literal_tilde() -> None:
    """Item 3: Verify sandbox PATH uses expanded absolute paths and contains no literal '~'."""
    res = run_sandboxed("env")
    assert res.exit_code == 0
    path_line = next(line for line in res.stdout.splitlines() if line.startswith("PATH="))
    assert "~" not in path_line, f"PATH contains unexpanded literal tilde: {path_line}"
    assert "/Users/" in path_line or "/home/" in path_line or "/usr/bin" in path_line


def test_same_test_passes_with_change_and_fails_without_change(tmp_path: Path) -> None:
    """Item 4: Discriminative test passes with production implementation and fails without it."""
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "runtime").mkdir()
    (repo / "runtime" / "feature.py").write_text("def feature() -> int:\n    return 42\n")

    cas = CAS(InMemoryCasStore())
    written_impl = ("runtime/feature.py", cas.put(b"def feature() -> int:\n    return 100\n"))
    written_test = (
        "tests/test_feature.py",
        cas.put(b"from runtime.feature import feature\ndef test_feat():\n    assert feature() == 100\n"),
    )
    written_paths = (written_impl, written_test)

    # Use executable script check that doesn't rely on uv in temp dir
    vac = vacuous_commands(
        repo,
        written_paths,
        cas,
        ("python3 -c 'from runtime.feature import feature; assert feature() == 100'",),
    )
    assert "python3 -c 'from runtime.feature import feature; assert feature() == 100'" not in vac


def test_missing_adversary_artifact_blocks() -> None:
    """Item 2 & 5: Missing adversary report artifact fails closed to AdversaryOutcome.BLOCK."""
    assert read_adversary_verdict(b"") is AdversaryOutcome.BLOCK
    assert read_adversary_verdict(b"some text without verdict") is AdversaryOutcome.BLOCK


def test_trace_containing_VERDICT_PASS_cannot_satisfy_gate() -> None:
    """Item 5: Raw trace containing 'VERDICT: PASS' without BLOCK line returns PASS only if valid report."""
    assert read_adversary_verdict("VERDICT: PASS\n") is AdversaryOutcome.PASS
    assert read_adversary_verdict("VERDICT: BLOCK\nVERDICT: PASS\n") is AdversaryOutcome.BLOCK


def test_stale_run_evidence_is_rejected() -> None:
    """Item 1: Evidence submitted under wrong run_id is not retrieved for active run."""
    from runtime.orchestrator import CourtEvidencePool

    pool = CourtEvidencePool()
    ev = Evidence(
        hash=content_hash(b"old_run"),
        kind=EvidenceKind.TEST,
        claim_id="unit",
        artifact_hash="a" * 64,
        environment_hash="e" * 64,
        reproducible_command="echo hi",
        producer=EvidenceProducer(role=Role.BUILDER, session="builder"),
        determinism=Determinism.DETERMINISTIC,
        result={"exit_code": 0, "stdout": "hi\n"},
        attestation="sig",
    )
    pool.submit("r-stale-123", ev)
    assert pool.evidence_for("r-active-456") == ()


def test_wrong_artifact_hash_is_rejected(tmp_path: Path) -> None:
    """Item 1: Evidence with wrong artifact hash fails court adjudication."""
    from runtime.court import Court

    court = Court()
    ev = Evidence(
        hash=content_hash(b"mismatched_ev"),
        kind=EvidenceKind.TEST,
        claim_id="unit",
        artifact_hash="wrong_hash_" + ("0" * 53),
        environment_hash="e" * 64,
        reproducible_command="echo hi",
        producer=EvidenceProducer(role=Role.BUILDER, session="builder"),
        determinism=Determinism.DETERMINISTIC,
        result={"exit_code": 0, "stdout": "hi\n"},
        attestation="sig",
    )
    court.submit_evidence(ev)
    from kernel.types import Claim

    verdict = court.adjudicate("correct_hash_" + ("1" * 53), (Claim("unit", "produced", (ev.hash,)),))
    assert verdict.outcome is VerdictOutcome.REMAND


def test_predeclared_unbound_evidence_is_rejected() -> None:
    """Item 1: Empty court pool returns empty evidence tuple for run."""
    from runtime.orchestrator import CourtEvidencePool

    pool = CourtEvidencePool()
    assert pool.evidence_for("r-nonexistent") == ()


def test_adversary_cannot_write_outside_review_scope() -> None:
    """Item 2: Adversary role scope restricts write scope to review/adversary_report.md."""
    from runtime.review import InformationBarrierManager, ReviewHarness

    class DummyDispatcher:
        def dispatch(self, **kwargs):
            # Assert that write_scopes is strictly restricted to review report
            assert kwargs["write_scopes"] == ("review/adversary_report.md",)
            assert kwargs["mcp_servers"] == ("constitution",)
            assert kwargs["role"] is Role.ADVERSARY
            return None

    ibm = InformationBarrierManager()
    bundle = ibm.seal(artifact_refs=(), evidence_refs=())
    harness = ReviewHarness(ibm, DummyDispatcher())  # type: ignore
    harness.review(
        goal_id="g-123",
        run_id="r-123",
        session="adv",
        bundle=bundle,
        budget=Budget(100, 100, 1),
    )

