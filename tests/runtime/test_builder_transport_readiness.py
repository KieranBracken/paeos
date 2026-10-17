from __future__ import annotations

import json
from hashlib import sha256
from pathlib import Path

import pytest
from nacl.signing import SigningKey
from runtime.builder_transport import (
    REQUIRED_CANARIES,
    REQUIRED_LIFECYCLE,
    BuilderTransportNotReady,
    BuilderTransportReadiness,
    canonical_qualification_bytes,
)


def _hash(label: str) -> str:
    return sha256(label.encode()).hexdigest()


def _payload(*, now: int = 1_000) -> dict[str, object]:
    return {
        "schema": "paeos-builder-transport-qualification/1",
        "qualification_scope": "standalone-provider-probe",
        "qualification_id": "btq-test-1",
        "supervisor_identity_sha256": _hash("supervisor"),
        "request_sha256": _hash("request"),
        "response_sha256": _hash("response"),
        "artifact_sha256": _hash("artifact"),
        "evidence_sha256": _hash("evidence"),
        "provider": "codex",
        "model": "gpt-5.6-sol",
        "family": "gpt",
        "observed_at": now,
        "expires_at": now + 3_600,
        "lifecycle": list(REQUIRED_LIFECYCLE),
        "canaries": sorted(REQUIRED_CANARIES),
        "fallback_used": False,
        "manual_chat_bridge": False,
    }


def _write_signed(path: Path, payload: dict[str, object], key: SigningKey) -> None:
    envelope = {
        "payload": payload,
        "signature": key.sign(canonical_qualification_bytes(payload)).signature.hex(),
    }
    path.write_text(json.dumps(envelope, sort_keys=True, separators=(",", ":")), encoding="utf-8")
    path.chmod(0o600)


def test_signed_physical_qualification_is_accepted(tmp_path: Path) -> None:
    key = SigningKey.generate()
    qualification = tmp_path / "qualification.json"
    _write_signed(qualification, _payload(), key)

    result = BuilderTransportReadiness(qualification, key.verify_key, clock=lambda: 1_100).require()

    assert result.provider == "codex"
    assert result.model == "gpt-5.6-sol"
    assert result.lifecycle == tuple(REQUIRED_LIFECYCLE)


def test_missing_qualification_is_not_ready(tmp_path: Path) -> None:
    with pytest.raises(BuilderTransportNotReady, match="qualification"):
        BuilderTransportReadiness(
            tmp_path / "missing.json", SigningKey.generate().verify_key, clock=lambda: 1_100
        ).require()


def test_forged_or_tampered_qualification_is_rejected(tmp_path: Path) -> None:
    signer = SigningKey.generate()
    qualification = tmp_path / "qualification.json"
    _write_signed(qualification, _payload(), signer)
    document = json.loads(qualification.read_text(encoding="utf-8"))
    document["payload"]["response_sha256"] = _hash("tampered")
    qualification.write_text(json.dumps(document), encoding="utf-8")

    with pytest.raises(BuilderTransportNotReady, match="signature"):
        BuilderTransportReadiness(
            qualification, SigningKey.generate().verify_key, clock=lambda: 1_100
        ).require()


@pytest.mark.parametrize(
    "field,value",
    [
        ("fallback_used", True),
        ("manual_chat_bridge", True),
        ("provider", "openrouter"),
        ("model", "openrouter/free"),
        ("family", "nemotron"),
        ("qualification_scope", "arbitrary-worker-success"),
        ("lifecycle", ["STARTING", "COMPLETED"]),
        ("canaries", []),
    ],
)
def test_qualification_cannot_be_goodharted_or_substituted(
    tmp_path: Path, field: str, value: object
) -> None:
    key = SigningKey.generate()
    qualification = tmp_path / "qualification.json"
    payload = _payload()
    payload[field] = value
    _write_signed(qualification, payload, key)

    with pytest.raises(BuilderTransportNotReady):
        BuilderTransportReadiness(qualification, key.verify_key, clock=lambda: 1_100).require()


def test_expired_qualification_is_rejected(tmp_path: Path) -> None:
    key = SigningKey.generate()
    qualification = tmp_path / "qualification.json"
    _write_signed(qualification, _payload(now=100), key)

    with pytest.raises(BuilderTransportNotReady, match=r"expired|stale"):
        BuilderTransportReadiness(qualification, key.verify_key, clock=lambda: 5_000).require()
