"""Bidirectional Semantic Delta Analysis Engine.

Performs clean-room delta analysis between expected capability surfaces and
current capability surfaces:
  Delta_missing = EXPECTED_CAPABILITY_SURFACE - CURRENT_CAPABILITY_SURFACE
  Delta_extra   = CURRENT_CAPABILITY_SURFACE - EXPECTED_CAPABILITY_SURFACE

Classifies every delta element and computes the definitive Semantic Requalification Disposition.
"""

from __future__ import annotations

from typing import Mapping

from paeos.semantic.types import (
    SemanticDelta,
    SemanticDeltaClassification,
    SemanticDeltaReport,
    SemanticRequalificationStatus,
)


class SemanticDeltaEngine:
    """Computes and validates bidirectional semantic deltas."""

    @staticmethod
    def analyze(
        *,
        subsystem_id: str,
        expected_surface: tuple[str, ...],
        current_surface: tuple[str, ...],
        delta_classifications: Mapping[str, tuple[SemanticDeltaClassification, str, str | None]] | None = None,
    ) -> SemanticDeltaReport:
        """Compute bidirectional delta and evaluate requalification status."""
        delta_map = delta_classifications or {}
        expected_set = set(expected_surface)
        current_set = set(current_surface)

        missing_names = sorted(expected_set - current_set)
        extra_names = sorted(current_set - expected_set)

        deltas: list[SemanticDelta] = []
        details: list[str] = []
        has_critical_failure = False
        has_deferred = False
        has_ambiguous = False

        # Process Missing Capabilities (EXPECTED - CURRENT)
        for name in missing_names:
            if name in delta_map:
                classification, justification, debt_ref = delta_map[name]
            else:
                classification = SemanticDeltaClassification.MISSING_CAPABILITY
                justification = "Unaccounted omission from current capability surface."
                debt_ref = None

            if classification == SemanticDeltaClassification.AUTHORIZED_DEFERMENT:
                if not debt_ref:
                    classification = SemanticDeltaClassification.UNAUTHORIZED_SCOPE_NARROWING
                    justification = f"Deferred capability {name} missing mandatory signed debt reference."
                    has_critical_failure = True
                else:
                    has_deferred = True
            elif classification == SemanticDeltaClassification.INTENT_AMBIGUOUS:
                has_ambiguous = True
            elif classification in (
                SemanticDeltaClassification.MISSING_CAPABILITY,
                SemanticDeltaClassification.UNAUTHORIZED_SCOPE_NARROWING,
            ):
                has_critical_failure = True

            deltas.append(
                SemanticDelta(
                    delta_name=name,
                    classification=classification,
                    direction="EXPECTED_MINUS_CURRENT",
                    justification=justification,
                    debt_ref=debt_ref,
                )
            )

        # Process Extra Capabilities (CURRENT - EXPECTED)
        for name in extra_names:
            if name in delta_map:
                classification, justification, debt_ref = delta_map[name]
            else:
                classification = SemanticDeltaClassification.IMPLEMENTATION_DETAIL
                justification = "Implementation detail or unclassified additional capability."
                debt_ref = None

            if classification == SemanticDeltaClassification.INTENT_AMBIGUOUS:
                has_ambiguous = True

            deltas.append(
                SemanticDelta(
                    delta_name=name,
                    classification=classification,
                    direction="CURRENT_MINUS_EXPECTED",
                    justification=justification,
                    debt_ref=debt_ref,
                )
            )

        # Determine Final Status
        if has_ambiguous:
            status = SemanticRequalificationStatus.INTENT_RECONSTRUCTION_REQUIRED
            is_clean = False
            details.append("Intent ambiguity requires explicit Founder resolution.")
        elif has_critical_failure:
            status = SemanticRequalificationStatus.SEMANTIC_SCOPE_REMAND
            is_clean = False
            details.append("Critical semantic scope collapse or unauthorized narrowing detected.")
        elif has_deferred:
            status = SemanticRequalificationStatus.SEMANTICALLY_REQUALIFIED_WITH_DEFERRED_OBLIGATIONS
            is_clean = True
            details.append("All missing capabilities are covered by ratified debt entries.")
        else:
            status = SemanticRequalificationStatus.SEMANTICALLY_REQUALIFIED
            is_clean = True
            details.append("Expected and current capability surfaces are semantically congruent.")

        return SemanticDeltaReport(
            subsystem_id=subsystem_id,
            expected_surface=tuple(sorted(expected_surface)),
            current_surface=tuple(sorted(current_surface)),
            missing=tuple(missing_names),
            extra=tuple(extra_names),
            deltas=tuple(deltas),
            is_clean=is_clean,
            status=status,
            details=tuple(details),
        )
