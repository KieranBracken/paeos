"""Canonical, self-contained prompts for substantive PAEOS audit review."""

from __future__ import annotations

import re

AUDIT_PHASE_MARKER = "AUDIT_PHASE: SUBSTANTIVE_EVIDENCE_REVIEW"
PHYSICAL_RECEIPT_PHASE_MARKER = (
    "PHYSICAL_RECEIPT_PHASE: POST_RESPONSE_CALLER_VALIDATION"
)
PROVENANCE_ABSENCE_MARKER = (
    "PROVENANCE_ABSENCE_POLICY: DO_NOT_BLOCK_SUBSTANTIVE_REPORT"
)
EVIDENCE_BEGIN_MARKER = "-----BEGIN PAEOS EMBEDDED EVIDENCE-----"
EVIDENCE_END_MARKER = "-----END PAEOS EMBEDDED EVIDENCE-----"

_HEX_RE = re.compile(r"^[0-9a-f]+$")
_PATH_ONLY_RE = re.compile(
    r"^(?:review\s+)?(?:file://)?/(?:private|tmp|Users)/\S+$",
    re.IGNORECASE,
)
_SELF_REFERENTIAL_RECEIPT_RE = re.compile(
    r"\byour\b[^\n.]{0,80}\breceipt\b[^\n.]{0,30}\b(?:must|shall|required)\b",
    re.IGNORECASE,
)


class AuditorPromptError(ValueError):
    """Raised when a substantive audit prompt is incomplete or ambiguous."""


def _validate_digest(value: str, *, name: str, length: int) -> None:
    if len(value) != length or _HEX_RE.fullmatch(value) is None:
        raise AuditorPromptError(f"{name} must be {length} lowercase hexadecimal characters")


def _validate_counts(counts: tuple[int, int, int], *, name: str) -> None:
    if len(counts) != 3 or any(
        isinstance(value, bool) or not isinstance(value, int) or value < 0
        for value in counts
    ):
        raise AuditorPromptError(f"{name} counts must be three non-negative integers")


def _accounting_line(
    label: str,
    counts: tuple[int, int, int],
) -> str:
    first, second, third = counts
    if label == "Worker":
        return (
            f"Worker: Admitted: {first} | Rejected: {second} | "
            f"Remediated: {third}"
        )
    return f"Court: Sealed: {first} | Remanded: {second} | Remediated: {third}"


def build_substantive_audit_prompt(
    candidate_sha: str,
    evidence_sha256: str,
    evidence_content: str,
    worker_counts: tuple[int, int, int],
    court_counts: tuple[int, int, int],
) -> str:
    """Build one canonical audit request containing all substantive evidence bytes."""

    _validate_digest(candidate_sha, name="candidate SHA", length=40)
    _validate_digest(evidence_sha256, name="evidence SHA-256", length=64)
    _validate_counts(worker_counts, name="worker")
    _validate_counts(court_counts, name="Court")
    evidence = evidence_content.strip()
    if not evidence:
        raise AuditorPromptError("embedded evidence must not be empty")

    prompt = f"""# PAEOS L14/L17 Substantive Audit Request

{AUDIT_PHASE_MARKER}
{PHYSICAL_RECEIPT_PHASE_MARKER}
{PROVENANCE_ABSENCE_MARKER}

Candidate SHA: {candidate_sha}
Evidence Bundle SHA-256: {evidence_sha256}
{_accounting_line("Worker", worker_counts)}
{_accounting_line("Court", court_counts)}

Independently review only the embedded evidence below. Treat builder prose as claims, not proof.
Do not modify code, invoke tools, advance a gate, promote a branch, or self-ratify.

The caller captures and validates physical provider/model/family provenance only after your
response returns. Do not claim your physical identity. Do not block the substantive report merely
because that future receipt is absent from this request. Your report will qualify only if the
caller later proves an exact report-bound A-08 receipt from a family different from the builder.

Return exactly one substantive status from PASS, REMAND_WITH_AMENDMENTS, or
BLOCKED_UNQUALIFIABLE. Include these machine-readable lines with factual explanations:

Candidate SHA: <candidate-sha-from-header>
Evidence Bundle SHA-256: <evidence-bundle-sha256-from-header>
L14_STATUS: <status>
INVARIANT: <finding>
REPRODUCTION: <finding>
{_accounting_line("Worker", worker_counts)}
{_accounting_line("Court", court_counts)}

Add a `### Audit Findings` section with at least one concrete evidence-based finding. End your
response with the exact final line `AUDIT_COMPLETE: true`; do not emit any text after that marker.


{EVIDENCE_BEGIN_MARKER}
{evidence}
{EVIDENCE_END_MARKER}
"""
    validate_substantive_audit_prompt(prompt, candidate_sha, evidence_sha256)
    return prompt


def validate_substantive_audit_prompt(
    content: str,
    candidate_sha: str,
    evidence_sha256: str,
) -> None:
    """Fail closed unless a prompt has one unambiguous two-phase evidence binding."""

    _validate_digest(candidate_sha, name="candidate SHA", length=40)
    _validate_digest(evidence_sha256, name="evidence SHA-256", length=64)
    if not content.strip():
        raise AuditorPromptError("audit prompt must not be empty")

    try:
        begin = content.index(EVIDENCE_BEGIN_MARKER)
        end = content.rindex(EVIDENCE_END_MARKER)
    except ValueError as exc:
        raise AuditorPromptError("audit prompt must contain evidence delimiters") from exc
    if end <= begin:
        raise AuditorPromptError("embedded evidence delimiters are out of order")
    outside_evidence = content[:begin] + content[end + len(EVIDENCE_END_MARKER) :]
    required_once = (
        AUDIT_PHASE_MARKER,
        PHYSICAL_RECEIPT_PHASE_MARKER,
        PROVENANCE_ABSENCE_MARKER,
        f"Candidate SHA: {candidate_sha}",
        f"Evidence Bundle SHA-256: {evidence_sha256}",
    )
    for marker in required_once:
        if outside_evidence.count(marker) != 1:
            raise AuditorPromptError(f"audit prompt must contain marker exactly once: {marker}")
    if outside_evidence.count(EVIDENCE_BEGIN_MARKER) or outside_evidence.count(
        EVIDENCE_END_MARKER
    ):
        raise AuditorPromptError("evidence delimiters must not appear outside the evidence block")
    begin += len(EVIDENCE_BEGIN_MARKER)
    instructions = content[:begin]
    if _SELF_REFERENTIAL_RECEIPT_RE.search(instructions):
        raise AuditorPromptError("future receipt cannot be required in the audit request")
    evidence = content[begin:end].strip()
    if not evidence:
        raise AuditorPromptError("embedded evidence must not be empty")
    if _PATH_ONLY_RE.fullmatch(evidence):
        raise AuditorPromptError("embedded evidence must contain bytes, not only a host-local path")
