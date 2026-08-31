"""Canonical per-layer lifecycle evidence derivation and run auditor (Gate G Task 1)."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from kernel.ledger import LedgerRow


class LayerDisposition(StrEnum):
    EXECUTED = "EXECUTED"
    DISCHARGED_TRACE_A = "DISCHARGED_TRACE_A"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    REMANDED = "REMANDED"
    UNPROVEN = "UNPROVEN"


@dataclass(frozen=True, slots=True)
class LayerEvidence:
    layer: int
    disposition: LayerDisposition
    ledger_sequences: tuple[int, ...]
    artifact_hashes: tuple[str, ...]
    evidence_hashes: tuple[str, ...]
    model_receipt_hashes: tuple[str, ...]
    reason_code: str


@dataclass(frozen=True, slots=True)
class LifecycleAuditReport:
    run_id: str
    trace: str
    layers: tuple[LayerEvidence, ...]
    sealed: int
    remanded: int
    remediated: int
    blocking_reason_codes: tuple[str, ...]
    verified_ledger_head: str


def audit_run(
    run_id: str,
    *,
    rows: Sequence[LedgerRow],
    cas: object = None,
    repository: Path,
) -> LifecycleAuditReport:
    layer_map: dict[int, list[int]] = {i: [] for i in range(1, 20)}
    artifact_map: dict[int, list[str]] = {i: [] for i in range(1, 20)}

    verified_head = rows[-1].row_hash if rows else "0" * 64
    sealed = 0
    remanded = 0
    remediated = 0

    for row in rows:
        etype = row.event.kind if hasattr(row, "event") else getattr(row, "event_type", "")
        payload = (
            getattr(row.event, "payload", {})
            if hasattr(row, "event")
            else getattr(row, "payload", {})
        )

        if payload.get("run_id") == run_id:
            layer_num = payload.get("layer")
            if isinstance(layer_num, int) and 1 <= layer_num <= 19:
                layer_map[layer_num].append(row.seq)
                art_hash = payload.get("artifact_hash")
                if art_hash:
                    artifact_map[layer_num].append(str(art_hash))

        if etype == "COURT_SEALED":
            sealed += 1
        elif etype == "COURT_REMANDED":
            remanded += 1
        elif etype == "COURT_REMEDIATED":
            remediated += 1

    layers_list: list[LayerEvidence] = []
    blocking_codes: list[str] = []

    for i in range(1, 20):
        seqs = tuple(layer_map[i])
        arts = tuple(artifact_map[i])
        if seqs:
            disp = LayerDisposition.EXECUTED
            reason = "STAGE_COMPLETED"
        else:
            disp = LayerDisposition.UNPROVEN
            reason = "NO_COMMITTED_EVIDENCE"
            blocking_codes.append("UNPROVEN_LAYERS_PRESENT")

        layers_list.append(
            LayerEvidence(
                layer=i,
                disposition=disp,
                ledger_sequences=seqs,
                artifact_hashes=arts,
                evidence_hashes=(),
                model_receipt_hashes=(),
                reason_code=reason,
            )
        )

    # Deduplicate blocking codes
    unique_blocking = tuple(sorted(set(blocking_codes)))

    return LifecycleAuditReport(
        run_id=run_id,
        trace="TRACE_A",
        layers=tuple(layers_list),
        sealed=sealed,
        remanded=remanded,
        remediated=remediated,
        blocking_reason_codes=unique_blocking,
        verified_ledger_head=verified_head,
    )
