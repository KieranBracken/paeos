"""Canonical Layer L09 Multi-Perspective Critique engine.

Evaluates candidate solutions across 8 canonical stances:
Security, Performance, Simplicity, Maintainability, Testability,
Backward Compatibility, Constitutional Alignment, and Functionality.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import Enum, auto
from typing import Any, Sequence

from kernel.cas import is_valid_hash


class CritiqueStance(Enum):
    SECURITY = auto()
    PERFORMANCE = auto()
    SIMPLICITY = auto()
    MAINTAINABILITY = auto()
    TESTABILITY = auto()
    BACKWARD_COMPATIBILITY = auto()
    CONSTITUTIONAL_ALIGNMENT = auto()
    FUNCTIONALITY = auto()


@dataclass(frozen=True)
class StanceEvaluation:
    stance: CritiqueStance
    passed: bool
    score: float
    reason: str


@dataclass(frozen=True)
class CritiqueReport:
    evaluations: list[StanceEvaluation]
    passed_all: bool
    summary: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "passed_all": self.passed_all,
            "summary": self.summary,
            "evaluations": [
                {
                    "stance": e.stance.name,
                    "passed": e.passed,
                    "score": e.score,
                    "reason": e.reason,
                }
                for e in self.evaluations
            ],
        }


class MultiPerspectiveCritiqueEngine:
    """Evaluates proposed architecture changes against the 8 canonical stances."""

    def __init__(self, required_stances: list[CritiqueStance] | None = None) -> None:
        if required_stances is None:
            self._stances = list(CritiqueStance)
        else:
            self._stances = required_stances

    def evaluate(self, proposal: dict[str, Any]) -> CritiqueReport:
        evaluations: list[StanceEvaluation] = []
        all_passed = True

        if not proposal:
            for stance in self._stances:
                evaluations.append(
                    StanceEvaluation(
                        stance=stance,
                        passed=False,
                        score=0.0,
                        reason=f"Stance {stance.name} failed: Proposal is empty with zero specifications.",
                    )
                )
            return CritiqueReport(
                evaluations=evaluations,
                passed_all=False,
                summary="Critique failed: Proposal is empty.",
            )

        # Collect full proposal textual surface for semantic analysis
        proposal_text = " ".join(
            str(v)
            for k, v in proposal.items()
            if isinstance(v, (str, list, tuple, dict))
        ).lower()

        stance_anti_patterns: dict[CritiqueStance, tuple[list[str], float, str]] = {
            CritiqueStance.SECURITY: (
                [
                    "bypass_auth",
                    "disable_security",
                    "unauthenticated",
                    "eval(",
                    "exec(",
                    "sandbox_escape",
                    "token_bypass",
                    "skip_verification",
                    "unauthorized",
                ],
                0.2,
                "Security vulnerability or authorization bypass anti-pattern detected",
            ),
            CritiqueStance.CONSTITUTIONAL_ALIGNMENT: (
                [
                    "violate_constitution",
                    "suppress_dissent",
                    "consensus_as_evidence",
                    "bypass_court",
                    "self_certification",
                    "override_invariants",
                    "ignore_remand",
                ],
                0.1,
                "Constitutional violation or self-certification anti-pattern detected",
            ),
            CritiqueStance.TESTABILITY: (
                [
                    "skip_tests",
                    "suppress_tests",
                    "no_tests",
                    "mock_all",
                    "disable_canaries",
                    "drop_tests",
                    "ignore_test_failures",
                ],
                0.3,
                "Test suppression or mock override anti-pattern detected",
            ),
            CritiqueStance.PERFORMANCE: (
                [
                    "infinite_loop",
                    "busy_wait",
                    "unbounded_memory",
                    "o_n_squared_scan",
                    "leak_memory",
                ],
                0.3,
                "Performance regression or unbounded resource usage anti-pattern detected",
            ),
            CritiqueStance.SIMPLICITY: (
                [
                    "overengineering",
                    "unnecessary_abstraction",
                    "circular_dependency",
                    "cyclomatic_explosion",
                ],
                0.4,
                "Excessive structural complexity anti-pattern detected",
            ),
            CritiqueStance.MAINTAINABILITY: (
                [
                    "spaghetti_code",
                    "monkeypatch",
                    "untyped_magic",
                    "temporary_hack",
                    "unmaintained",
                ],
                0.4,
                "Maintainability or architectural decay anti-pattern detected",
            ),
            CritiqueStance.BACKWARD_COMPATIBILITY: (
                [
                    "breaking_change",
                    "drop_api",
                    "incompatible_schema",
                    "corrupt_state",
                    "unsupported_migration",
                ],
                0.3,
                "Backward compatibility breach or schema corruption risk detected",
            ),
            CritiqueStance.FUNCTIONALITY: (
                [
                    "noop_implementation",
                    "unimplemented_stub",
                    "broken_feature",
                    "dummy_payload",
                ],
                0.2,
                "Defective functionality or unimplementable stub anti-pattern detected",
            ),
        }

        for stance in self._stances:
            anti_patterns, fail_score, fail_desc = stance_anti_patterns.get(
                stance, ([], 0.0, "Unknown stance deficit")
            )
            detected_kw = next((kw for kw in anti_patterns if kw in proposal_text), None)
            if detected_kw:
                # Anti-patterns cannot be overridden by caller-supplied stance_overrides!
                score = fail_score
                reason = f"{fail_desc}: '{detected_kw}'."
                passed = False
            else:
                score = 1.0
                reason = f"Stance {stance.name} satisfied criteria: no anti-patterns detected."
                passed = True

            if not passed:
                all_passed = False

            evaluations.append(
                StanceEvaluation(
                    stance=stance,
                    passed=passed,
                    score=score,
                    reason=reason,
                )
            )

        summary = (
            f"Critique passed across all {len(evaluations)} stances."
            if all_passed
            else f"Critique failed: {[e.stance.name for e in evaluations if not e.passed]} failed baseline criteria."
        )

        return CritiqueReport(
            evaluations=evaluations,
            passed_all=all_passed,
            summary=summary,
        )


class CouncilVoteStance(str, Enum):
    """Voting stance for Council and Debate deliberation (Doctrine §7, SCO-014)."""
    APPROVE = "APPROVE"
    REJECT = "REJECT"
    DISSENT = "DISSENT"
    ABSTAIN = "ABSTAIN"


@dataclass(frozen=True, slots=True)
class CouncilVote:
    """Individual vote and opinion submitted by a Council member."""
    voter_id: str
    stance: CouncilVoteStance
    model_family: str
    argument: str
    risks_identified: tuple[str, ...] = ()
    suggested_alternatives: tuple[str, ...] = ()
    dissent_cas_hash: str = ""


@dataclass(frozen=True, slots=True)
class CouncilVoteRecord:
    """Formal structured record of a Council deliberation with preserved dissension."""
    vote_id: str
    proposal_id: str
    topic: str
    votes: tuple[CouncilVote, ...]
    consensus_reached: bool
    dissenting_opinions: tuple[CouncilVote, ...]
    vote_cas_hash: str = ""
    is_consensus_used_as_evidence: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "vote_id": self.vote_id,
            "proposal_id": self.proposal_id,
            "topic": self.topic,
            "consensus_reached": self.consensus_reached,
            "is_consensus_used_as_evidence": self.is_consensus_used_as_evidence,
            "vote_cas_hash": self.vote_cas_hash,
            "votes": [
                {
                    "voter_id": v.voter_id,
                    "stance": v.stance.value,
                    "model_family": v.model_family,
                    "argument": v.argument,
                    "risks_identified": list(v.risks_identified),
                    "suggested_alternatives": list(v.suggested_alternatives),
                    "dissent_cas_hash": v.dissent_cas_hash,
                }
                for v in self.votes
            ],
            "dissenting_opinions": [
                {
                    "voter_id": d.voter_id,
                    "stance": d.stance.value,
                    "model_family": d.model_family,
                    "argument": d.argument,
                    "dissent_cas_hash": d.dissent_cas_hash,
                }
                for d in self.dissenting_opinions
            ],
        }


class CouncilDissensionViolationError(Exception):
    """Raised when Council deliberation violates constitutional dissension preservation or consensus invariants."""


def record_council_deliberation(
    vote_id: str,
    proposal_id: str,
    topic: str,
    votes: Sequence[CouncilVote],
    cas: Any | None = None,
    approval_threshold: float = 0.66,
    substitute_as_test_evidence: bool = False,
) -> CouncilVoteRecord:
    """Record a Council deliberation, writing dissenting opinions to CAS.
    
    Constitutional Invariants (Doctrine §7):
      1. Dissension Preservation: Any vote with stance DISSENT or REJECT must be preserved in dissenting_opinions.
      2. Dissent CAS Invariant: Dissenting arguments are hashed and stored into CAS.
      3. Consensus is NOT Evidence: A Council vote cannot substitute for empirical test execution.
    """
    if substitute_as_test_evidence:
        raise CouncilDissensionViolationError(
            "CONSENSUS_AS_EVIDENCE_FORBIDDEN: Adaptation Doctrine §7 strictly forbids substituting Council consensus for empirical test/verifier evidence"
        )

    processed_votes: list[CouncilVote] = []
    dissenting_list: list[CouncilVote] = []

    for v in votes:
        cas_hash = v.dissent_cas_hash
        if v.stance in (CouncilVoteStance.DISSENT, CouncilVoteStance.REJECT):
            if cas is None:
                raise CouncilDissensionViolationError(
                    "DISSENT_CAS_STORAGE_REQUIRED: CAS store is required to preserve dissenting opinions into durable CAS"
                )
            if not cas_hash:
                payload = json.dumps({
                    "voter_id": v.voter_id,
                    "stance": v.stance.value,
                    "argument": v.argument,
                    "risks": list(v.risks_identified),
                    "alternatives": list(v.suggested_alternatives),
                }, sort_keys=True).encode("utf-8")
                cas_hash = cas.put(payload)
            else:
                if not cas.has(cas_hash):
                    raise CouncilDissensionViolationError(
                        f"DISSENT_CAS_UNGROUNDED: Pre-supplied dissent CAS hash '{cas_hash}' is not grounded in CAS store"
                    )
            vote_with_cas = CouncilVote(
                voter_id=v.voter_id,
                stance=v.stance,
                model_family=v.model_family,
                argument=v.argument,
                risks_identified=v.risks_identified,
                suggested_alternatives=v.suggested_alternatives,
                dissent_cas_hash=cas_hash,
            )
            processed_votes.append(vote_with_cas)
            dissenting_list.append(vote_with_cas)
        else:
            processed_votes.append(v)

    # Compute consensus
    approve_count = sum(1 for v in processed_votes if v.stance == CouncilVoteStance.APPROVE)
    total_votes = len(processed_votes)
    consensus_reached = (approve_count / total_votes >= approval_threshold) if total_votes > 0 else False

    record = CouncilVoteRecord(
        vote_id=vote_id,
        proposal_id=proposal_id,
        topic=topic,
        votes=tuple(processed_votes),
        consensus_reached=consensus_reached,
        dissenting_opinions=tuple(dissenting_list),
        is_consensus_used_as_evidence=substitute_as_test_evidence,
    )

    if cas is not None:
        serialized = json.dumps(record.to_dict(), sort_keys=True).encode("utf-8")
        record_cas_hash = cas.put(serialized)
        record = CouncilVoteRecord(
            vote_id=record.vote_id,
            proposal_id=record.proposal_id,
            topic=record.topic,
            votes=record.votes,
            consensus_reached=record.consensus_reached,
            dissenting_opinions=record.dissenting_opinions,
            vote_cas_hash=record_cas_hash,
            is_consensus_used_as_evidence=record.is_consensus_used_as_evidence,
        )

    return record


def verify_council_deliberation_invariants(
    record: CouncilVoteRecord,
    cas: Any | None = None,
) -> list[str]:
    """Verify that a Council deliberation satisfies constitutional executable-law invariants.
    
    Checks:
      1. Minimum Quorum: At least 3 votes.
      2. Dissension Completeness: All DISSENT / REJECT votes are captured in dissenting_opinions.
      3. Anti-Suppression: Dissenting arguments cannot be empty strings.
      4. Dissent CAS Invariant: Dissenting votes must have a valid durable CAS content hash.
      5. Dissent CAS Existence & Authenticity: When CAS is provided, stored dissent payloads must exist and match.
      6. Consensus Is Not Evidence: Cannot be flagged as substitute for empirical evidence.
    """
    violations: list[str] = []

    if len(record.votes) < 3:
        violations.append(
            f"COUNCIL_QUORUM_VIOLATION: Council deliberation must have at least 3 votes, found {len(record.votes)}"
        )

    # Check that any DISSENT/REJECT is in dissenting_opinions and has durable CAS hash
    dissent_voter_ids = {d.voter_id for d in record.dissenting_opinions}
    for v in record.votes:
        if v.stance in (CouncilVoteStance.DISSENT, CouncilVoteStance.REJECT):
            if v.voter_id not in dissent_voter_ids:
                violations.append(
                    f"DISSENT_SUPPRESSION_VIOLATION: Voter {v.voter_id} voted {v.stance.value} but was omitted from dissenting_opinions"
                )
            if not v.argument.strip():
                violations.append(
                    f"DISSENT_EMPTY_ARGUMENT: Voter {v.voter_id} registered dissent without substantive argument"
                )
            if not v.dissent_cas_hash or not is_valid_hash(v.dissent_cas_hash):
                violations.append(
                    f"DISSENT_CAS_HASH_MISSING: Dissenting vote from voter {v.voter_id} lacks valid durable CAS content hash"
                )

    for d in record.dissenting_opinions:
        if not d.dissent_cas_hash or not is_valid_hash(d.dissent_cas_hash):
            violations.append(
                f"DISSENT_CAS_HASH_MISSING: Dissenting opinion from voter {d.voter_id} lacks valid durable CAS content hash"
            )

    if cas is not None:
        for d in record.dissenting_opinions:
            if d.dissent_cas_hash and is_valid_hash(d.dissent_cas_hash):
                if not cas.has(d.dissent_cas_hash):
                    violations.append(
                        f"DISSENT_CAS_NOT_FOUND: Dissent CAS hash {d.dissent_cas_hash} for voter {d.voter_id} not found in CAS store"
                    )
                else:
                    try:
                        raw = cas.get(d.dissent_cas_hash)
                        content = json.loads(raw.decode("utf-8")) if isinstance(raw, (bytes, bytearray)) else raw
                        if isinstance(content, dict):
                            if content.get("voter_id") != d.voter_id or content.get("argument") != d.argument:
                                violations.append(
                                    f"DISSENT_CAS_CONTENT_MISMATCH: Stored CAS payload does not match voter {d.voter_id} dissent"
                                )
                    except Exception as exc:
                        violations.append(
                            f"DISSENT_CAS_PAYLOAD_CORRUPT: Failed to parse dissent CAS payload for voter {d.voter_id}: {exc}"
                        )

    if record.is_consensus_used_as_evidence:
        violations.append(
            "CONSENSUS_AS_EVIDENCE_FORBIDDEN: Adaptation Doctrine §7 strictly forbids substituting Council consensus for empirical test/verifier evidence"
        )

    return violations

