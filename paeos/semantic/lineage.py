"""Obligation Lineage DAG and parent-to-child inheritance tracker.

Ensures that child tasks inherit all parent capability obligations and cannot silently drop
or discard obligations without a lawful, signed disposition.
"""

from __future__ import annotations

from typing import Mapping

from paeos.semantic.types import (
    SemanticAssuranceError,
    SemanticDispositionKind,
    SemanticObligation,
    SemanticObligationDisposition,
    SemanticScopeNarrowingError,
)


class SemanticLineageDAG:
    """Tracks capability obligation inheritance across parent missions and child tasks."""

    def __init__(self) -> None:
        self._obligations: dict[str, tuple[SemanticObligation, ...]] = {}
        self._dispositions: dict[str, dict[str, SemanticObligationDisposition]] = {}
        self._parent_map: dict[str, str] = {}

    def register_task_obligations(
        self,
        task_id: str,
        obligations: tuple[SemanticObligation, ...],
        dispositions: tuple[SemanticObligationDisposition, ...] = (),
        parent_task_id: str | None = None,
    ) -> None:
        """Register obligations and dispositions for a task."""
        if not task_id:
            raise SemanticAssuranceError("task_id must not be empty")

        # Validate dispositions
        disp_map: dict[str, SemanticObligationDisposition] = {}
        for d in dispositions:
            d.validate()
            if d.obligation_id in disp_map:
                raise SemanticAssuranceError(f"Duplicate disposition for obligation {d.obligation_id}")
            disp_map[d.obligation_id] = d

        # If parent_task_id is given, validate inheritance
        if parent_task_id:
            self.validate_child_spawn(
                parent_task_id=parent_task_id,
                child_task_id=task_id,
                child_obligations=obligations,
                child_dispositions=dispositions,
            )
            self._parent_map[task_id] = parent_task_id

        self._obligations[task_id] = obligations
        self._dispositions[task_id] = disp_map

    def get_task_obligations(self, task_id: str) -> tuple[SemanticObligation, ...]:
        """Return registered obligations for task_id."""
        return self._obligations.get(task_id, ())

    def get_task_dispositions(self, task_id: str) -> dict[str, SemanticObligationDisposition]:
        """Return registered dispositions for task_id."""
        return dict(self._dispositions.get(task_id, {}))

    def validate_child_spawn(
        self,
        parent_task_id: str,
        child_task_id: str,
        child_obligations: tuple[SemanticObligation, ...],
        child_dispositions: tuple[SemanticObligationDisposition, ...] = (),
    ) -> None:
        """Verify that the child task does not silently drop or narrow any parent obligation."""
        parent_obs = self._obligations.get(parent_task_id)
        if parent_obs is None:
            # Parent not tracked or has no obligations
            return

        child_ob_ids = {ob.obligation_id for ob in child_obligations}
        child_disp_map = {d.obligation_id: d for d in child_dispositions}

        # Every parent obligation must either be present in child obligations or have an approved disposition
        for p_ob in parent_obs:
            if p_ob.obligation_id in child_ob_ids:
                continue

            # Obligation omitted from child. Check disposition
            disp = child_disp_map.get(p_ob.obligation_id)
            if disp is None:
                raise SemanticScopeNarrowingError(
                    f"UNAUTHORIZED_SCOPE_NARROWING: Child task '{child_task_id}' silently dropped "
                    f"parent obligation '{p_ob.obligation_id}' ({p_ob.description}) without lawful disposition."
                )

            # Check if disposition is lawful for an omitted obligation
            if disp.disposition not in (
                SemanticDispositionKind.AUTHORIZED_DEFERMENT,
                SemanticDispositionKind.AUTHORIZED_SUPERSESSION,
                SemanticDispositionKind.PRESERVED_AS_IS,
            ):
                raise SemanticScopeNarrowingError(
                    f"UNAUTHORIZED_SCOPE_NARROWING: Child task '{child_task_id}' dropped obligation "
                    f"'{p_ob.obligation_id}' under unlawful disposition '{disp.disposition}'."
                )
