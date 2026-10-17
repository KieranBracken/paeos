"""L11 Semantic Freeze Guard.

Enforces that no L11 contract or AuthoritativeCapabilityManifest can be frozen
if capability obligations are missing, dropped, or unlawfully disposed.
Any violation immediately raises L11FreezeDeniedError ('L11_FREEZE_DENIED: ...').
"""

from __future__ import annotations

from typing import Any, Mapping

from paeos.semantic.types import (
    L11FreezeDeniedError,
    SemanticAssuranceError,
    SemanticDispositionKind,
    SemanticObligation,
    SemanticObligationDisposition,
    SemanticScopeNarrowingError,
)


class L11SemanticFreezeGuard:
    """Evaluates semantic completeness before L11 contract/manifest freeze."""

    @staticmethod
    def validate_freeze(
        *,
        manifest_id: str,
        expected_capabilities: tuple[str, ...],
        deferred_debt: tuple[str, ...],
        obligations: tuple[SemanticObligation, ...],
        dispositions: tuple[SemanticObligationDisposition, ...],
        enforce_all_accounted: bool = True,
    ) -> None:
        """Validate L11 contract freeze. Raises L11FreezeDeniedError on violation."""
        if not manifest_id:
            raise L11FreezeDeniedError("L11_FREEZE_DENIED: Manifest ID cannot be empty.")

        disp_map: dict[str, SemanticObligationDisposition] = {}
        for d in dispositions:
            try:
                d.validate()
            except (SemanticAssuranceError, SemanticScopeNarrowingError) as exc:
                raise L11FreezeDeniedError(f"L11_FREEZE_DENIED: Invalid disposition for {d.obligation_id}: {exc}") from exc
            disp_map[d.obligation_id] = d

        expected_cap_set = set(expected_capabilities)
        deferred_debt_set = set(deferred_debt)

        # Check every obligation has an explicit disposition
        for ob in obligations:
            disp = disp_map.get(ob.obligation_id)
            if disp is None:
                raise L11FreezeDeniedError(
                    f"L11_FREEZE_DENIED: Obligation '{ob.obligation_id}' ({ob.description}) has no explicit disposition."
                )

            if disp.disposition in (
                SemanticDispositionKind.UNAUTHORIZED_SCOPE_NARROWING,
                SemanticDispositionKind.MISSING_CAPABILITY,
            ):
                raise L11FreezeDeniedError(
                    f"L11_FREEZE_DENIED: Obligation '{ob.obligation_id}' is in unlawful status '{disp.disposition}'."
                )

            if disp.disposition in (
                SemanticDispositionKind.IMPLEMENTED,
                SemanticDispositionKind.PRESERVED_AS_IS,
            ):
                # Implemented obligations MUST be in the frozen expected capabilities
                if ob.obligation_id not in expected_cap_set:
                    raise L11FreezeDeniedError(
                        f"L11_FREEZE_DENIED: Implemented obligation '{ob.obligation_id}' is missing from manifest expected capabilities."
                    )

            elif disp.disposition == SemanticDispositionKind.AUTHORIZED_DEFERMENT:
                # Deferred obligations MUST be bound in deferred_debt
                if not disp.debt_id or disp.debt_id not in deferred_debt_set:
                    raise L11FreezeDeniedError(
                        f"L11_FREEZE_DENIED: Deferred obligation '{ob.obligation_id}' has debt '{disp.debt_id}' "
                        f"which is missing from manifest deferred_debt {sorted(deferred_debt_set)}."
                    )

        # Check for omissions: every expected capability that corresponds to an obligation must have a disposition
        if enforce_all_accounted:
            ob_ids = {ob.obligation_id for ob in obligations}
            for cap in expected_capabilities:
                if cap.startswith("SCO-") and cap not in ob_ids:
                    raise L11FreezeDeniedError(
                        f"L11_FREEZE_DENIED: Expected capability '{cap}' is not registered in semantic obligations."
                    )
