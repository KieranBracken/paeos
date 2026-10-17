"""Canonical per-layer lifecycle evidence derivation and run auditor (Gate G Task 1)."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from kernel.cas import CAS, is_valid_hash
from kernel.ledger import LedgerRow

from runtime.court_reconciliation import reconcile_court_counts


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
    cas: CAS | None = None,
    repository: Path,
) -> LifecycleAuditReport:
    layer_map: dict[int, list[int]] = {i: [] for i in range(1, 20)}
    artifact_map: dict[int, list[str]] = {i: [] for i in range(1, 20)}
    evidence_map: dict[int, list[str]] = {i: [] for i in range(1, 20)}
    receipt_map: dict[int, list[str]] = {i: [] for i in range(1, 20)}
    payload_map: dict[int, list[dict[str, object]]] = {i: [] for i in range(1, 20)}

    verified_head = rows[-1].row_hash if rows else "0" * 64
    for row in rows:
        payload = (
            getattr(row.event, "payload", {})
            if hasattr(row, "event")
            else getattr(row, "payload", {})
        )

        if payload.get("run_id") == run_id:
            layer_num = payload.get("layer")
            if isinstance(layer_num, int) and 1 <= layer_num <= 19:
                layer_map[layer_num].append(row.seq)
                payload_map[layer_num].append(payload)
                art_hash = payload.get("artifact_hash")
                if isinstance(art_hash, str):
                    artifact_map[layer_num].append(str(art_hash))
                for key in (
                    "evidence_hash",
                    "court_evidence_hash",
                    "l13_evidence_hash",
                    "constitutional_review_hash",
                    "l17_review_hash",
                ):
                    value = payload.get(key)
                    if isinstance(value, str):
                        evidence_map[layer_num].append(value)
                for key in ("model_receipt_hash", "auditor_receipt_hash", "l14_receipt_hash"):
                    value = payload.get(key)
                    if isinstance(value, str):
                        receipt_map[layer_num].append(value)

    court_counts = reconcile_court_counts(rows)

    layers_list: list[LayerEvidence] = []
    blocking_codes: list[str] = []

    for i in range(1, 20):
        seqs = tuple(layer_map[i])
        arts = tuple(artifact_map[i])
        evidences = tuple(evidence_map[i])
        receipts = tuple(receipt_map[i])
        reason = "NO_COMMITTED_EVIDENCE"
        disp = LayerDisposition.UNPROVEN
        if seqs and not arts:
            reason = "MISSING_ARTIFACT"
        elif seqs and any(not is_valid_hash(value) for value in arts):
            reason = "INVALID_ARTIFACT_HASH"
        elif seqs and i in (13, 17) and not any(is_valid_hash(value) for value in evidences):
            reason = "REQUIRED_AUDIT_EVIDENCE_MISSING"
        elif seqs and i == 14:
            families = {
                str(payload.get("builder_family"))
                for payload in payload_map[i]
                if payload.get("builder_family")
            }
            auditor_families = {
                str(payload.get("auditor_family"))
                for payload in payload_map[i]
                if payload.get("auditor_family")
            }
            if not any(is_valid_hash(value) for value in receipts):
                reason = "REQUIRED_AUDIT_EVIDENCE_MISSING"
            elif not families or not auditor_families or families & auditor_families:
                reason = "BUILDER_AUDITOR_DECORRELATION_UNPROVEN"
            elif cas is None:
                reason = "CAS_UNAVAILABLE"
            elif any(not cas.has(value) for value in arts + receipts):
                reason = "CAS_EVIDENCE_MISSING"
            else:
                disp = LayerDisposition.EXECUTED
                reason = "STAGE_COMPLETED"
        elif seqs and cas is None:
            reason = "CAS_UNAVAILABLE"
        elif seqs and cas is not None and any(not cas.has(value) for value in arts):
            reason = "CAS_ARTIFACT_MISSING"
        elif (
            seqs
            and i in (13, 17)
            and cas is not None
            and any(not cas.has(value) for value in evidences)
        ):
            reason = "CAS_EVIDENCE_MISSING"
        elif seqs:
            disp = LayerDisposition.EXECUTED
            reason = "STAGE_COMPLETED"
        if disp is LayerDisposition.UNPROVEN:
            disp = LayerDisposition.UNPROVEN
        if disp is LayerDisposition.UNPROVEN:
            blocking_codes.append("UNPROVEN_LAYERS_PRESENT")
            if reason in {
                "REQUIRED_AUDIT_EVIDENCE_MISSING",
                "BUILDER_AUDITOR_DECORRELATION_UNPROVEN",
            }:
                blocking_codes.append(reason)

        layers_list.append(
            LayerEvidence(
                layer=i,
                disposition=disp,
                ledger_sequences=seqs,
                artifact_hashes=arts,
                evidence_hashes=evidences,
                model_receipt_hashes=receipts,
                reason_code=reason,
            )
        )

    # Deduplicate blocking codes
    unique_blocking = tuple(sorted(set(blocking_codes)))

    return LifecycleAuditReport(
        run_id=run_id,
        trace="TRACE_A",
        layers=tuple(layers_list),
        sealed=court_counts.sealed,
        remanded=court_counts.remanded,
        remediated=court_counts.remediated,
        blocking_reason_codes=unique_blocking,
        verified_ledger_head=verified_head,
    )
