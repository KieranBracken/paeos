"""Tests for canonical two-phase substantive audit prompts."""

from __future__ import annotations

import pytest


def test_builder_embeds_evidence_and_separates_post_response_provenance() -> None:
    from paeos.model_router.audit_prompt import (
        build_substantive_audit_prompt,
        validate_substantive_audit_prompt,
    )

    prompt = build_substantive_audit_prompt(
        candidate_sha="a" * 40,
        evidence_sha256="e" * 64,
        evidence_content="sealed diff bytes",
        worker_counts=(0, 1, 0),
        court_counts=(0, 0, 0),
    )

    assert "AUDIT_PHASE: SUBSTANTIVE_EVIDENCE_REVIEW" in prompt
    assert "PHYSICAL_RECEIPT_PHASE: POST_RESPONSE_CALLER_VALIDATION" in prompt
    assert "PROVENANCE_ABSENCE_POLICY: DO_NOT_BLOCK_SUBSTANTIVE_REPORT" in prompt
    assert "Worker: Admitted: 0 | Rejected: 1 | Remediated: 0" in prompt
    assert "Court: Sealed: 0 | Remanded: 0 | Remediated: 0" in prompt
    assert "sealed diff bytes" in prompt
    validate_substantive_audit_prompt(prompt, "a" * 40, "e" * 64)


def test_validator_rejects_noncanonical_prompt() -> None:
    from paeos.model_router.audit_prompt import (
        AuditorPromptError,
        validate_substantive_audit_prompt,
    )

    with pytest.raises(AuditorPromptError):
        validate_substantive_audit_prompt(
            "review /private/tmp/bundle; receipt required",
            "a" * 40,
            "e" * 64,
        )


def test_builder_rejects_path_only_evidence() -> None:
    from paeos.model_router.audit_prompt import (
        AuditorPromptError,
        build_substantive_audit_prompt,
    )

    with pytest.raises(AuditorPromptError, match="host-local path"):
        build_substantive_audit_prompt(
            candidate_sha="a" * 40,
            evidence_sha256="e" * 64,
            evidence_content="/private/tmp/paeos-audit-bundle.md",
            worker_counts=(0, 1, 0),
            court_counts=(0, 0, 0),
        )


def test_validator_rejects_self_referential_receipt_requirement() -> None:
    from paeos.model_router.audit_prompt import (
        EVIDENCE_BEGIN_MARKER,
        AuditorPromptError,
        build_substantive_audit_prompt,
        validate_substantive_audit_prompt,
    )

    prompt = build_substantive_audit_prompt(
        candidate_sha="a" * 40,
        evidence_sha256="e" * 64,
        evidence_content="sealed diff bytes",
        worker_counts=(0, 1, 0),
        court_counts=(0, 0, 0),
    ).replace(
        EVIDENCE_BEGIN_MARKER,
        "Your future physical receipt must be included in this request.\n\n"
        + EVIDENCE_BEGIN_MARKER,
    )

    with pytest.raises(AuditorPromptError, match="future receipt"):
        validate_substantive_audit_prompt(prompt, "a" * 40, "e" * 64)


def test_validator_rejects_duplicate_phase_markers() -> None:
    from paeos.model_router.audit_prompt import (
        AuditorPromptError,
        build_substantive_audit_prompt,
        validate_substantive_audit_prompt,
    )

    prompt = build_substantive_audit_prompt(
        candidate_sha="a" * 40,
        evidence_sha256="e" * 64,
        evidence_content="sealed diff bytes",
        worker_counts=(0, 1, 0),
        court_counts=(0, 0, 0),
    )

    with pytest.raises(AuditorPromptError, match="exactly once"):
        validate_substantive_audit_prompt(
            prompt + "\nAUDIT_PHASE: SUBSTANTIVE_EVIDENCE_REVIEW\n",
            "a" * 40,
            "e" * 64,
        )


@pytest.mark.parametrize(
    ("candidate_sha", "evidence_sha256", "evidence_content"),
    [
        ("short", "e" * 64, "sealed diff bytes"),
        ("a" * 40, "not-a-digest", "sealed diff bytes"),
        ("a" * 40, "e" * 64, "   "),
    ],
)
def test_builder_rejects_invalid_bindings_or_empty_evidence(
    candidate_sha: str,
    evidence_sha256: str,
    evidence_content: str,
) -> None:
    from paeos.model_router.audit_prompt import (
        AuditorPromptError,
        build_substantive_audit_prompt,
    )

    with pytest.raises(AuditorPromptError):
        build_substantive_audit_prompt(
            candidate_sha=candidate_sha,
            evidence_sha256=evidence_sha256,
            evidence_content=evidence_content,
            worker_counts=(0, 1, 0),
            court_counts=(0, 0, 0),
        )
