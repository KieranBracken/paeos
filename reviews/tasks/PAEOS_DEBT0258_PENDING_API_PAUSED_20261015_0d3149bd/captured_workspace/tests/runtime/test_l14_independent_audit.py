"""Unit tests for Canonical Layer L14 Independent Audit."""

from runtime.independent_audit import AuditStatus, IndependentAuditEngine


def test_independent_audit_pass() -> None:
    engine = IndependentAuditEngine()
    report = engine.perform_audit({"runtime/sample.py": "def foo(): pass"})
    assert report.status == AuditStatus.PASSED
    assert report.to_dict()["status"] == "PASSED"


def test_independent_audit_fail_on_eval() -> None:
    engine = IndependentAuditEngine()
    report = engine.perform_audit({"runtime/sample.py": "eval('2+2')"})
    assert report.status == AuditStatus.FAILED
    assert len(report.findings) == 1
    assert report.findings[0].rule_id == "SEC-001"
