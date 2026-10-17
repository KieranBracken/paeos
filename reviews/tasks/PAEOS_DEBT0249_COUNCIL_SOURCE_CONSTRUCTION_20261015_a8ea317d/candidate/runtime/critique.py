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



def _dissent_payload(vote: CouncilVote) -> dict[str, Any]:
    return {
        "voter_id": vote.voter_id,
        "stance": vote.stance.value,
        "argument": vote.argument,
        "risks": list(vote.risks_identified),
        "alternatives": list(vote.suggested_alternatives),
    }


def _valid_dissent_vote(vote: CouncilVote) -> bool:
    return (
        isinstance(vote.voter_id, str) and bool(vote.voter_id.strip())
        and isinstance(vote.stance, CouncilVoteStance)
        and isinstance(vote.argument, str) and bool(vote.argument.strip())
        and all(isinstance(items, tuple)
                and all(isinstance(item, str) and item.strip() for item in items)
                for items in (vote.risks_identified, vote.suggested_alternatives))
    )


def _valid_dissent_payload(content: Any) -> bool:
    return (
        isinstance(content, dict)
        and set(content) == {"voter_id", "stance", "argument", "risks", "alternatives"}
        and all(isinstance(content[k], str) and content[k].strip()
                for k in ("voter_id", "stance", "argument"))
        and content["stance"] in ("DISSENT", "REJECT")
        and all(isinstance(content[k], list)
                and all(isinstance(item, str) and item.strip() for item in content[k])
                for k in ("risks", "alternatives"))
    )


def _dissent_cas_violations(vote: CouncilVote, cas: Any) -> list[str]:
    if not _valid_dissent_vote(vote):
        return [f"DISSENT_CAS_PAYLOAD_CORRUPT: Invalid dissent fields for voter {vote.voter_id}"]
    key = vote.dissent_cas_hash
    if not isinstance(key, str) or not is_valid_hash(key):
        return [f"DISSENT_CAS_HASH_MISSING: Voter {vote.voter_id} lacks valid durable CAS content hash"]
    try:
        if not cas.has(key):
            return [f"DISSENT_CAS_NOT_FOUND: Dissent CAS hash {key} for voter {vote.voter_id} not found in CAS store"]
        content = json.loads(cas.get(key))
        if not _valid_dissent_payload(content):
            return [f"DISSENT_CAS_PAYLOAD_CORRUPT: Invalid dissent payload for voter {vote.voter_id}"]
        if content != _dissent_payload(vote):
            return [f"DISSENT_CAS_CONTENT_MISMATCH: Stored CAS payload does not match voter {vote.voter_id} dissent"]
    except Exception as exc:
        return [f"DISSENT_CAS_PAYLOAD_CORRUPT: Failed to read dissent CAS payload for voter {vote.voter_id}: {exc}"]
    return []


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

    voter_ids = [v.voter_id for v in votes]
    if len(voter_ids) != len(set(voter_ids)):
        raise CouncilDissensionViolationError("COUNCIL_DUPLICATE_VOTER: Council voter IDs must be unique")

    processed_votes: list[CouncilVote] = []
    dissenting_list: list[CouncilVote] = []

    for v in votes:
        cas_hash = v.dissent_cas_hash
        if v.stance in (CouncilVoteStance.DISSENT, CouncilVoteStance.REJECT):
            if cas is None:
                raise CouncilDissensionViolationError(
                    "DISSENT_CAS_STORAGE_REQUIRED: CAS store is required to preserve dissenting opinions into durable CAS"
                )
            if not _valid_dissent_vote(v):
                raise CouncilDissensionViolationError("DISSENT_CAS_PAYLOAD_CORRUPT: Invalid dissent fields")
            payload = _dissent_payload(v)
            if not _valid_dissent_payload(payload):
                raise CouncilDissensionViolationError(
                    "DISSENT_CAS_PAYLOAD_CORRUPT: Dissent fields must have valid types and substantive content"
                )
            if not cas_hash:
                cas_hash = cas.put(json.dumps(payload, sort_keys=True).encode("utf-8"))
            else:
                errors = _dissent_cas_violations(v, cas)
                if errors:
                    raise CouncilDissensionViolationError(
                        "DISSENT_CAS_UNGROUNDED: Pre-supplied dissent hash is not bound to this vote; " + "; ".join(errors)
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
      5. CAS Existence & Authenticity: A CAS store must ground complete dissent and record payloads.
      6. Consensus Is Not Evidence: Cannot be flagged as substitute for empirical evidence.
    """
    violations: list[str] = []

    if len(record.votes) < 3:
        violations.append(
            f"COUNCIL_QUORUM_VIOLATION: Council deliberation must have at least 3 votes, found {len(record.votes)}"
        )

    voter_ids = [v.voter_id for v in record.votes]
    if len(voter_ids) != len(set(voter_ids)):
        violations.append("COUNCIL_DUPLICATE_VOTER: Council voter IDs must be unique")

    expected_dissent = tuple(v for v in record.votes
                             if v.stance in (CouncilVoteStance.DISSENT, CouncilVoteStance.REJECT))
    dissent_ids = [d.voter_id for d in record.dissenting_opinions]
    if len(dissent_ids) != len(set(dissent_ids)):
        violations.append("DISSENT_DUPLICATE_ENTRY: Dissent entries must be unique")
    # Compare the dataclasses themselves: the historic serialized dissent view
    # intentionally omits risks and alternatives and cannot establish this binding.
    if (len(record.dissenting_opinions) != len(expected_dissent)
            or any(d not in expected_dissent for d in record.dissenting_opinions)
            or any(v not in record.dissenting_opinions for v in expected_dissent)):
        violations.append("DISSENT_SUPPRESSION_VIOLATION: Dissenting opinions must exactly match the complete DISSENT/REJECT vote view")

    for v in expected_dissent:
        if not isinstance(v.argument, str) or not v.argument.strip():
            violations.append(f"DISSENT_EMPTY_ARGUMENT: Voter {v.voter_id} registered dissent without substantive argument")

    # Validate both views, including when an inconsistent view is itself grounded.
    for dissent in (*expected_dissent, *record.dissenting_opinions):
        key = dissent.dissent_cas_hash
        if not isinstance(key, str) or not is_valid_hash(key):
            violations.append(f"DISSENT_CAS_HASH_MISSING: Voter {dissent.voter_id} lacks valid durable CAS content hash")
        elif cas is not None:
            violations.extend(_dissent_cas_violations(dissent, cas))

    if cas is None:
        violations.append("COUNCIL_CAS_STORAGE_REQUIRED: CAS store is required to verify grounded Council binding")
    else:
        key = record.vote_cas_hash
        if not isinstance(key, str) or not is_valid_hash(key):
            violations.append("VOTE_CAS_HASH_MISSING: Council record lacks valid durable CAS content hash")
        else:
            try:
                if not cas.has(key):
                    violations.append("VOTE_CAS_NOT_FOUND: Council record CAS payload is absent")
                else:
                    payload = record.to_dict()
                    payload["vote_cas_hash"] = ""
                    expected = json.dumps(payload, sort_keys=True).encode("utf-8")
                    if cas.get(key) != expected:
                        violations.append("VOTE_CAS_CONTENT_MISMATCH: Council record does not match canonical stored payload")
            except Exception as exc:
                violations.append(f"VOTE_CAS_PAYLOAD_CORRUPT: Failed to read Council record payload: {exc}")

    if record.is_consensus_used_as_evidence:
        violations.append(
            "CONSENSUS_AS_EVIDENCE_FORBIDDEN: Adaptation Doctrine §7 strictly forbids substituting Council consensus for empirical test/verifier evidence"
        )

    return violations

