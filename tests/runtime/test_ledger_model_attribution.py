"""Ledger model attribution (MEDIUM-003 remediation, Entry 142): executed stages append
STAGE_COMPLETED rows carrying the model that actually ran them, so posteriori session-log
cross-checks can verify the claim.
"""

from __future__ import annotations

from pathlib import Path

from kernel.ledger import InMemoryLedgerStore, Ledger
from paeos.model_router.auditor_receipt import (
    AUDITOR_RECEIPT_SCHEMA,
    AuditorReceiptContract,
    PhysicalAuditorReceipt,
    persist_auditor_receipt,
)
from paeos.model_router.types import ModelFamily, ProviderId
from runtime.orchestrator import SoftLoop  # any class carrying _record_stage
from runtime.task_package import Cost, TaskResult, TaskStatus


def _result(model_ver: str) -> TaskResult:
    return TaskResult(
        task_id="t-attr1",
        status=TaskStatus.COMPLETE,
        artifacts=(),
        evidence=(),
        trace_ref="c" * 64,
        written_paths=(),
        cost=Cost(tokens=42, wallclock_s=1.0, model_ver=model_ver),
    )


def test_stage_completed_row_records_model(tmp_path: Path) -> None:
    ledger = Ledger(InMemoryLedgerStore())
    loop = SoftLoop.__new__(SoftLoop)  # only _record_stage is under test
    loop._ledger = ledger

    from kernel.types import StageId

    loop._record_stage("r-attr", "g-attr", StageId.ADVERSARIAL_REVIEW, "adversary", _result("cline-pass/glm-5.3"))

    rows = ledger.read(1, None)
    assert len(rows) == 1
    payload = rows[0].event.payload
    assert rows[0].event.kind == "STAGE_COMPLETED"
    assert payload["model_ver"] == "cline-pass/glm-5.3"
    assert payload["stage"] == "ADVERSARIAL_REVIEW"
    assert payload["status"] == "COMPLETE"
    assert payload["tokens"] == 42
    ledger.verify_chain()  # the appended row keeps the chain verifiable


def test_l14_ledger_metadata_uses_actual_auditor_identity(tmp_path: Path) -> None:
    """L14 ledger attribution must come from the validated receipt, never the Builder contract."""
    from runtime.orchestrator import _auditor_ledger_metadata

    contract = AuditorReceiptContract(
        audit_id="audit-attr",
        candidate_sha256="a" * 64,
        evidence_bundle_sha256="b" * 64,
        review_scope_sha256="c" * 64,
        builder_provider="openai",
        builder_model_id="openai:gpt-5.6-sol",
        builder_family=ModelFamily.GPT,
    )
    receipt = PhysicalAuditorReceipt(
        schema=AUDITOR_RECEIPT_SCHEMA,
        audit_id=contract.audit_id,
        invocation_id="audit-attr:invocation",
        session_id="audit-attr-session",
        candidate_sha256=contract.candidate_sha256,
        evidence_bundle_sha256=contract.evidence_bundle_sha256,
        review_scope_sha256=contract.review_scope_sha256,
        builder_provider=contract.builder_provider,
        builder_model_id=contract.builder_model_id,
        builder_family=contract.builder_family,
        configured_provider_id=ProviderId.GOOGLE,
        configured_model_id="gemini-3.6-flash",
        actual_provider_id=ProviderId.GOOGLE,
        actual_model_id="gemini-3.6-flash",
        actual_family=ModelFamily.GEMINI,
        transport_id="paeos-model-router:google:gemini-3.6-flash:test",
        provider_attempt_count=1,
        fallback_chain=("google:gemini-3.6-flash",),
        transport_request_sha256="d" * 64,
        transport_response_sha256="e" * 64,
        transcript_sha256="f" * 64,
        captured_at_unix=1_788_132_345.0,
        a08_verdict="PASS",
    )
    receipt_path = tmp_path / "receipt.json"
    persist_auditor_receipt(receipt, receipt_path)

    metadata = _auditor_ledger_metadata(receipt_path, contract)

    assert metadata == {
        "auditor_provider": "google",
        "auditor_model": "gemini-3.6-flash",
        "auditor_family": "gemini",
    }
