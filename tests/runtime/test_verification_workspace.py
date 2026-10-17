"""Tests for isolated verification proof views (Gate E Task 6)."""

from __future__ import annotations

from pathlib import Path

from kernel.types import ArtifactRef
from runtime.implementation_contract import (
    AcceptanceCommand,
    FrozenImplementationContract,
    compute_contract_hash,
)


def test_create_verification_views(tmp_path: Path) -> None:
    from runtime.verification_workspace import (
        VerificationViews,
        create_verification_views,
    )

    cmd = AcceptanceCommand("pytest-focused", ("pytest", "-q"), ".", 30, (0,))
    contract_hash = compute_contract_hash(
        goal_id="G-001",
        run_id="R-001",
        ceremony_trace="TRACE_A",
        base_commit="a" * 40,
        allowed_paths=("src/foo.py",),
        required_artifacts=("reviews/tasks/FOO_review.md",),
        acceptance_commands=(cmd,),
        rollback_argv=("git", "restore", "."),
        data_class="INTERNAL",
        context_manifest_hash="c" * 64,
        derivation_register_hash="d" * 64,
    )
    contract = FrozenImplementationContract(
        contract_id="IC-001",
        contract_hash=contract_hash,
        goal_id="G-001",
        run_id="R-001",
        ceremony_trace="TRACE_A",
        base_commit="a" * 40,
        allowed_paths=("src/foo.py",),
        required_artifacts=("reviews/tasks/FOO_review.md",),
        acceptance_commands=(cmd,),
        rollback_argv=("git", "restore", "."),
        data_class="INTERNAL",
        context_manifest_hash="c" * 64,
        derivation_register_hash="d" * 64,
    )

    bundle = ArtifactRef("verifier_bundle", "e" * 64)
    views = create_verification_views(contract, bundle, base_dir=tmp_path)

    assert isinstance(views, VerificationViews)
    assert views.baseline.exists()
    assert views.candidate.exists()
    assert views.verifier.exists()
    assert views.baseline_head == "a" * 40
    assert len(views.verifier_manifest_hash) == 64
