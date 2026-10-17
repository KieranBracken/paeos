"""Unit tests for Canonical Layer L10 Adversarial Review."""

from runtime.adversary import AdversarialReviewEngine, AdversaryVerdict


def test_adversarial_review_pass() -> None:
    engine = AdversarialReviewEngine()
    report = engine.evaluate_review({"has_security_flaw": False})
    assert report.verdict == AdversaryVerdict.PASS
    assert report.to_dict()["verdict"] == "PASS"


def test_adversarial_review_fail() -> None:
    engine = AdversarialReviewEngine()
    report = engine.evaluate_review({"has_security_flaw": True})
    assert report.verdict == AdversaryVerdict.FAIL
    assert report.to_dict()["verdict"] == "FAIL"
