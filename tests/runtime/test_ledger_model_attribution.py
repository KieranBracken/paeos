"""Ledger model attribution (MEDIUM-003 remediation, Entry 142): executed stages append
STAGE_COMPLETED rows carrying the model that actually ran them, so posteriori session-log
cross-checks can verify the claim.
"""

from __future__ import annotations

from pathlib import Path

from kernel.ledger import Event, InMemoryLedgerStore, Ledger
from runtime.task_package import Cost, TaskResult, TaskStatus
from runtime.orchestrator import SoftLoop  # any class carrying _record_stage


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
