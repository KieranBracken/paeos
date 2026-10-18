"""Structured Schema and Solver for Architect Cognition Multi-Candidate Derivation (L05/L07).

Satisfies ELH-15 / SCO-013 (Adaptation Doctrine §7, line 386):
"Architect derives formal architecture candidate(s) from root causes."
Enforces quantitative Pareto dominance and multi-candidate generation.
Single-candidate foregone conclusions and unverified derivations are rejected.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping, Sequence


class RootCauseCategory(str, Enum):
    """Categorization of root cause defects."""
    STRUCTURAL_INVARIANT_VIOLATION = "STRUCTURAL_INVARIANT_VIOLATION"
    RESOURCE_EXHAUSTION = "RESOURCE_EXHAUSTION"
    INTERFACE_MISMATCH = "INTERFACE_MISMATCH"
    CONCURRENCY_STALE_STATE = "CONCURRENCY_STALE_STATE"
    AUTHORITY_EXPANSION = "AUTHORITY_EXPANSION"
    SEMANTIC_DRIFT = "SEMANTIC_DRIFT"
    DEFECTIVE_ASSUMPTION = "DEFECTIVE_ASSUMPTION"


@dataclass(frozen=True, slots=True)
class RootCauseRecord:
    """Formal root-cause record from verified failure evidence."""
    defect_id: str
    category: RootCauseCategory
    description: str
    impacted_invariants: tuple[str, ...]
    evidence_cas_hash: str


@dataclass(frozen=True, slots=True)
class ArchitectureCandidate:
    """An architectural candidate derived by the Architect to remediate root causes."""
    candidate_id: str
    name: str
    description: str
    target_components: tuple[str, ...]
    structural_mutations: tuple[str, ...]
    invariants_preserved: tuple[str, ...]
    tradeoff_scores: Mapping[str, float] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ParetoEvaluation:
    """Pareto optimality evaluation for a set of candidates."""
    candidate_id: str
    is_pareto_optimal: bool
    dominated_by: tuple[str, ...] = ()
    tradeoff_vector: Mapping[str, float] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ArchitectDerivationPacket:
    """Formal multi-candidate derivation packet produced by Architect cognition."""
    derivation_id: str
    mission_id: str
    root_causes: tuple[RootCauseRecord, ...]
    candidates: tuple[ArchitectureCandidate, ...]
    pareto_frontier: tuple[ParetoEvaluation, ...]
    selected_candidate_id: str
    selection_rationale: str
    packet_sha256: str = ""

    def compute_sha256(self) -> str:
        """Deterministic content hash over derivation components."""
        data = {
            "derivation_id": self.derivation_id,
            "mission_id": self.mission_id,
            "root_causes": [
                {
                    "defect_id": rc.defect_id,
                    "category": rc.category.value,
                    "impacted_invariants": list(rc.impacted_invariants),
                    "evidence_cas_hash": rc.evidence_cas_hash,
                }
                for rc in self.root_causes
            ],
            "candidates": [
                {
                    "candidate_id": c.candidate_id,
                    "name": c.name,
                    "description": c.description,
                    "target_components": list(c.target_components),
                    "invariants_preserved": list(c.invariants_preserved),
                    "structural_mutations": list(c.structural_mutations),
                    "scores": dict(c.tradeoff_scores),
                }
                for c in self.candidates
            ],
            "pareto_frontier": [
                {
                    "candidate_id": p.candidate_id,
                    "is_pareto_optimal": p.is_pareto_optimal,
                    "dominated_by": sorted(p.dominated_by),
                    "tradeoff_vector": {k: float(v) for k, v in sorted(p.tradeoff_vector.items())},
                }
                for p in self.pareto_frontier
            ],
            "selected_candidate_id": self.selected_candidate_id,
            "selection_rationale": self.selection_rationale,
        }
        encoded = json.dumps(data, sort_keys=True).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()


class ArchitectDerivationError(Exception):
    """Raised when an architect derivation packet violates constitutional derivation rules."""


def compute_pareto_frontier(
    candidates: Sequence[ArchitectureCandidate],
    criteria: Sequence[str],
) -> list[ParetoEvaluation]:
    """Compute Pareto-optimal frontier across multiple criteria (higher score is better).
    
    Candidate A dominates Candidate B iff:
      - A is >= B in all criteria, AND
      - A is > B in at least one criterion.
    """
    evaluations: list[ParetoEvaluation] = []
    
    for c_i in candidates:
        for crit in criteria:
            if crit not in c_i.tradeoff_scores:
                raise ArchitectDerivationError(
                    f"Candidate {c_i.candidate_id} missing score for required criterion '{crit}'"
                )

    for c_i in candidates:
        scores_i = c_i.tradeoff_scores
        dominated_by: list[str] = []
        
        for c_j in candidates:
            if c_i.candidate_id == c_j.candidate_id:
                continue
            scores_j = c_j.tradeoff_scores
            
            # Check if j dominates i
            strictly_better_in_at_least_one = False
            at_least_as_good_in_all = True
            
            for crit in criteria:
                val_i = scores_i[crit]
                val_j = scores_j[crit]
                if not (math.isfinite(val_i) and math.isfinite(val_j)):
                    at_least_as_good_in_all = False
                    break
                if val_j < val_i:
                    at_least_as_good_in_all = False
                    break
                if val_j > val_i:
                    strictly_better_in_at_least_one = True
                    
            if at_least_as_good_in_all and strictly_better_in_at_least_one:
                dominated_by.append(c_j.candidate_id)
                
        evaluations.append(
            ParetoEvaluation(
                candidate_id=c_i.candidate_id,
                is_pareto_optimal=len(dominated_by) == 0,
                dominated_by=tuple(dominated_by),
                tradeoff_vector=dict(scores_i),
            )
        )
        
    return evaluations


def verify_architect_derivation(
    packet: ArchitectDerivationPacket,
    criteria: Sequence[str] | None = None,
    cas: Any = None,
) -> list[str]:
    """Verify that an Architect derivation packet satisfies all executable-law requirements.
    
    Invariants checked:
      1. Minimum Candidates Invariant: At least 2 distinct candidates must be derived (prevents mono-candidate railroading).
      2. Root Cause Invariant: At least 1 verified root cause must be specified with CAS evidence hash.
      3. Invariant Preservation: Every candidate must declare preserved architectural invariants.
      4. Pareto Optimality Invariant: The selected candidate must be Pareto-optimal (cannot select a strictly dominated candidate).
      5. Selection Validity: The selected candidate ID must exist in candidate list.
      6. Content Hash Verification: packet.packet_sha256 must match recomputed deterministic SHA-256.
      7. CAS Grounding: Root cause evidence hashes must exist in CAS store when provided.
      8. Finite Tradeoff Scores: All candidate tradeoff scores must be finite numeric values.
      9. Mandatory Criteria: Tradeoff evaluation criteria must be non-empty.
    """
    violations: list[str] = []

    # 0. Packet hash verification
    if not packet.packet_sha256:
        violations.append(
            "PACKET_HASH_MISSING: Derivation packet must declare a non-empty packet_sha256"
        )
    else:
        computed_sha = packet.compute_sha256()
        if packet.packet_sha256 != computed_sha:
            violations.append(
                f"PACKET_HASH_MISMATCH: Declared packet_sha256 {packet.packet_sha256} does not match computed {computed_sha}"
            )

    # 1. Multi-candidate requirement
    if len(packet.candidates) < 2:
        violations.append(
            f"MULTI_CANDIDATE_VIOLATION: Architect must derive at least 2 distinct candidates, found {len(packet.candidates)}"
        )
    candidate_ids = {c.candidate_id for c in packet.candidates}
    if len(candidate_ids) < len(packet.candidates):
        violations.append(
            f"DUPLICATE_CANDIDATE_VIOLATION: Candidate IDs must be unique, found {len(packet.candidates) - len(candidate_ids)} duplicates"
        )

    # Check for semantic candidate duplicates (identical tradeoff vectors and components)
    candidate_fingerprints = set()
    for c in packet.candidates:
        # Check finite scores
        for crit_name, score_val in c.tradeoff_scores.items():
            if not isinstance(score_val, (int, float)) or not math.isfinite(score_val):
                violations.append(
                    f"NON_FINITE_TRADEOFF_SCORE: Candidate {c.candidate_id} criterion '{crit_name}' has non-finite score {score_val}"
                )
        fp = (
            tuple(sorted(c.target_components)),
            tuple(sorted(c.invariants_preserved)),
            tuple(sorted((k, float(v)) for k, v in c.tradeoff_scores.items() if math.isfinite(v))),
        )
        if fp in candidate_fingerprints:
            violations.append(
                f"SEMANTIC_DUPLICATE_CANDIDATE_VIOLATION: Candidate {c.candidate_id} is semantically identical to another candidate; architect must derive substantively distinct alternatives"
            )
        candidate_fingerprints.add(fp)

    # 2. Root cause requirement & CAS existence check
    if not packet.root_causes:
        violations.append("ROOT_CAUSE_VIOLATION: Derivation must be grounded in at least one verified root cause")
    for rc in packet.root_causes:
        if not rc.evidence_cas_hash or rc.evidence_cas_hash.startswith("mock_"):
            violations.append(f"ROOT_CAUSE_EVIDENCE_VACUOUS: Root cause {rc.defect_id} lacks authentic CAS evidence hash")
        elif cas is not None:
            has_evidence = False
            if hasattr(cas, "has") and callable(cas.has):
                has_evidence = cas.has(rc.evidence_cas_hash)
            elif hasattr(cas, "__contains__"):
                has_evidence = rc.evidence_cas_hash in cas
            if not has_evidence:
                violations.append(
                    f"ROOT_CAUSE_CAS_NOT_FOUND: Evidence CAS hash {rc.evidence_cas_hash} for defect {rc.defect_id} not found in CAS"
                )

    # 3. Candidate existence & invariant preservation
    if packet.selected_candidate_id not in candidate_ids:
        violations.append(
            f"SELECTION_NOT_FOUND: Selected candidate {packet.selected_candidate_id} not in candidate set"
        )

    for c in packet.candidates:
        if not c.invariants_preserved:
            violations.append(f"INVARIANT_PRESERVATION_MISSING: Candidate {c.candidate_id} declares no preserved invariants")
        if not c.description or not c.description.strip():
            violations.append(f"CANDIDATE_DESCRIPTION_MISSING: Candidate {c.candidate_id} must declare non-empty description")
        if not c.structural_mutations:
            violations.append(f"CANDIDATE_MUTATIONS_MISSING: Candidate {c.candidate_id} must declare non-empty structural_mutations")

    if not packet.selection_rationale or not packet.selection_rationale.strip():
        violations.append("SELECTION_RATIONALE_MISSING: Derivation packet must declare non-empty selection_rationale")

    # 4. Mandatory criteria & Pareto optimality check
    active_criteria = list(criteria) if criteria else []
    if not active_criteria and packet.candidates:
        all_keys = set()
        for c in packet.candidates:
            all_keys.update(c.tradeoff_scores.keys())
        if all_keys:
            active_criteria = sorted(all_keys)

    if not active_criteria:
        violations.append(
            "CRITERIA_REQUIRED: Architect derivation must declare non-empty tradeoff criteria for Pareto evaluation"
        )
    else:
        for c in packet.candidates:
            for crit in active_criteria:
                if crit not in c.tradeoff_scores:
                    violations.append(
                        f"CANDIDATE_TRADEOFF_SCORE_MISSING: Candidate {c.candidate_id} is missing tradeoff score for criterion '{crit}'"
                    )

    has_missing_scores = any("CANDIDATE_TRADEOFF_SCORE_MISSING" in v for v in violations)
    expected_evals: dict[str, ParetoEvaluation] = {}
    if active_criteria and len(packet.candidates) >= 2 and not has_missing_scores:
        computed_evals = compute_pareto_frontier(packet.candidates, active_criteria)
        expected_evals = {ev.candidate_id: ev for ev in computed_evals}
        if packet.selected_candidate_id not in expected_evals:
            violations.append(
                f"PARETO_SELECTION_MISSING: Selected candidate {packet.selected_candidate_id} not found in Pareto frontier"
            )
        elif not expected_evals[packet.selected_candidate_id].is_pareto_optimal:
            violations.append(
                f"PARETO_DOMINANCE_VIOLATION: Selected candidate {packet.selected_candidate_id} is strictly dominated on Pareto frontier"
            )

    if not packet.pareto_frontier:
        violations.append("PARETO_FRONTIER_MISSING: Derivation packet must declare an explicit non-empty pareto_frontier")
    elif expected_evals:
        declared_ids = {ev.candidate_id for ev in packet.pareto_frontier}
        expected_ids = set(expected_evals.keys())
        if declared_ids != expected_ids:
            missing = expected_ids - declared_ids
            violations.append(
                f"PARETO_FRONTIER_INCOMPLETE: pareto_frontier missing candidate(s): {sorted(missing)}"
            )

        for ev in packet.pareto_frontier:
            exp_ev = expected_evals.get(ev.candidate_id)
            if exp_ev is None:
                violations.append(f"PARETO_FRONTIER_MISMATCH: Unknown candidate {ev.candidate_id} in pareto_frontier")
                continue
            if ev.is_pareto_optimal != exp_ev.is_pareto_optimal:
                violations.append("PARETO_FRONTIER_MISMATCH: packet.pareto_frontier does not match recomputed Pareto frontier")
            if set(ev.dominated_by) != set(exp_ev.dominated_by):
                violations.append(
                    f"PARETO_DOMINATED_BY_MISMATCH: Candidate {ev.candidate_id} dominated_by {ev.dominated_by} != expected {exp_ev.dominated_by}"
                )
            for crit in active_criteria:
                if crit not in ev.tradeoff_vector:
                    violations.append(
                        f"PARETO_TRADEOFF_VECTOR_MISSING: Candidate {ev.candidate_id} tradeoff_vector is missing criterion '{crit}'"
                    )
                elif crit in exp_ev.tradeoff_vector:
                    if abs(ev.tradeoff_vector[crit] - exp_ev.tradeoff_vector[crit]) > 1e-6:
                        violations.append(
                            f"PARETO_TRADEOFF_VECTOR_MISMATCH: Candidate {ev.candidate_id} tradeoff_vector[{crit}] does not match expected score"
                        )

    return violations
