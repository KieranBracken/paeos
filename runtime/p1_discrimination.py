"""Closed semantic-discrimination catalogue for the production P1 manifest."""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

from kernel.cas import CAS
from kernel.sandbox import SandboxLimits, SandboxResult, allowlisted_path, canonical_command

from runtime.candidate_materialization import (
    CandidateIntegrityError,
    CandidateMaterialization,
    verify_candidate_integrity,
)
from runtime.verification import _run_in_verification_workspace

P1_MANIFEST_ID = "P1-COMPLETENESS-REQUALIFICATION-20260907"


@dataclass(frozen=True, slots=True)
class _Mutation:
    path: str
    replacements: tuple[tuple[str, str], ...]


_CATALOGUE = {
    "CLAIM-CF-01-CAPABILITY-DISPOSITION": _Mutation(
        "runtime/court/completeness_firewall.py",
        (("if bundle.unresolved_omissions:", "if False and bundle.unresolved_omissions:"),),
    ),
    "CLAIM-CF-02-OPERATIONAL-TRANSPORT-PROOF": _Mutation(
        "runtime/court/completeness_firewall.py",
        (("if tr.is_test_only or not tr.verified:", "if False and (tr.is_test_only or not tr.verified):"),),
    ),
    "CLAIM-CF-03-AUTHORITATIVE-PATH-TRUTH": _Mutation(
        "runtime/court/completeness_firewall.py",
        (
            ("if insp.has_undisclosed_synthetic_fallback:", "if False and insp.has_undisclosed_synthetic_fallback:"),
            ("if insp.has_hardcoded_authoritative_metric:", "if False and insp.has_hardcoded_authoritative_metric:"),
        ),
    ),
    "CLAIM-CF-04-PROFILE-TRIGGERED-OBLIGATIONS": _Mutation(
        "runtime/court/completeness_firewall.py",
        (("if SystemProfileTag.PROFILE_CROSS_BOUNDARY in bundle.profiles and bundle.fixtures_only:", "if False and SystemProfileTag.PROFILE_CROSS_BOUNDARY in bundle.profiles and bundle.fixtures_only:"),),
    ),
    "CLAIM-CF-05-MANDATORY-E2E-EVIDENCE": _Mutation(
        "runtime/court/completeness_firewall.py",
        ((") and not bundle.e2e_evidence_hashes:", ") and False and not bundle.e2e_evidence_hashes:"),),
    ),
    "CLAIM-CF-06-L16-PROMOTION-GENUINE-L14-RECEIPT": _Mutation(
        "runtime/court/completeness_firewall.py",
        (("violations.append(f\"L16-BLOCK: Invalid or synthetic L14 auditor receipt/report: {exc}\")", "l14_qualified = True"),),
    ),
    "CLAIM-CF-07-ANTI-CIRCULAR-SEPARATION": _Mutation(
        "runtime/transports/mcp/court_server.py",
        (
            ('"stderr_sha256": content_hash(observation.stderr.encode()),', '"stderr_sha256": "",'),
            ('"stdout_sha256": content_hash(observation.stdout.encode()),', '"stdout_sha256": "",'),
        ),
    ),
    "CLAIM-CF-09-MANIFEST-OMISSION-PREVENTION": _Mutation(
        "runtime/court/completeness_firewall.py",
        (("for expected_cap in manifest.expected_capabilities:", "for expected_cap in ():"),),
    ),
    "CLAIM-CF-10-UNFORGEABLE-TRANSPORT-ATTESTATION": _Mutation(
        "paeos/model_router/auditor_receipt.py",
        (("if require_transport_attestation:", "if False and require_transport_attestation:"),),
    ),
    "CLAIM-CF-11-SOFTLOOP-L11-L13-L16-WIRING": _Mutation(
        "runtime/orchestrator/__init__.py",
        (("if production_completeness:\n            assert candidate is not None\n            assert capability_manifest is not None\n            try:\n                ledger_head", "if False and production_completeness:\n            assert candidate is not None\n            assert capability_manifest is not None\n            try:\n                ledger_head"),),
    ),
}


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _physical_result(result: SandboxResult, environment: dict[str, str]) -> dict[str, object]:
    return {
        "argv": list(result.argv),
        "executable": result.executable,
        "executable_version": result.executable_version,
        "environment": dict(sorted(environment.items())),
        "environment_fingerprint": result.environment_fingerprint,
        "exit_code": 124 if result.timed_out else result.exit_code,
        "stdout_sha256": _sha(result.stdout.encode()),
        "stderr_sha256": _sha(result.stderr.encode()),
        "duration_ms": result.duration_ms,
    }


def _result_hash(result: SandboxResult, environment: dict[str, str]) -> str:
    body = {
        key: value
        for key, value in _physical_result(result, environment).items()
        if key != "duration_ms"
    }
    return _sha(json.dumps(body, sort_keys=True, separators=(",", ":")).encode())


def _assert_qualified(result: object, *, negative: bool) -> None:
    stdout = getattr(result, "stdout", "")
    stderr = getattr(result, "stderr", "")
    if isinstance(stdout, bytes):
        stdout = stdout.decode("utf-8", errors="replace")
    if isinstance(stderr, bytes):
        stderr = stderr.decode("utf-8", errors="replace")
    output = stdout + stderr
    exit_code = getattr(result, "exit_code", getattr(result, "returncode", None))
    invalid = (
        "ERROR collecting", "ERROR at setup", "ImportError", "ModuleNotFoundError",
        "TypeError", "no tests ran", "collected 0 items", "KeyboardInterrupt",
    )
    if getattr(result, "timed_out", False) or any(marker in output for marker in invalid):
        raise CandidateIntegrityError("P1 discriminator encountered invalid test infrastructure failure")
    if re.search(r"\bskipped\b", output, re.IGNORECASE):
        raise CandidateIntegrityError("P1 discriminator did not execute the designated test")
    if negative:
        assertion_failure = (
            "AssertionError" in output
            or "\nE       assert " in output
            or "\n>       assert " in output
            or "DID NOT RAISE" in output
        )
        failure_evidence = bool(
            re.search(r"(?:^|\s)(?:FAILED|F)(?:\s|$)|\d+ failed\b", output)
        )
        if exit_code != 1 or not failure_evidence or not assertion_failure:
            raise CandidateIntegrityError("P1 negative arm did not produce a substantive assertion failure")
    else:
        pass_evidence = bool(re.search(r"\d+ passed\b", output)) or bool(
            re.search(r"(?m)^\.+\s*(?:\[\s*100%\])?\s*$", output)
        )
        if exit_code != 0 or not pass_evidence:
            raise CandidateIntegrityError("P1 positive arm did not pass with sufficient pytest evidence")


def discriminate_p1_candidate(
    *, candidate: CandidateMaterialization, cas: CAS, manifest_id: str, obligations: tuple[object, ...]
) -> tuple[dict[str, object], ...]:
    """Run the ten fixed P1 claims against the candidate and exact semantic negations."""
    if manifest_id != P1_MANIFEST_ID:
        raise CandidateIntegrityError("P1 discriminator invoked for an unknown manifest")
    verify_candidate_integrity(candidate, cas=cas)
    by_claim = {getattr(item, "claim_id", None): item for item in obligations if getattr(item, "kind", None).value == "CANDIDATE_DISCRIMINATION"}
    if set(by_claim) != set(_CATALOGUE):
        raise CandidateIntegrityError("P1 discriminator obligation catalogue mismatch")
    owned = {item.path: item for item in (*candidate.changed_files, *candidate.verification_source_files)}
    records: list[dict[str, object]] = []
    environment = {"PATH": allowlisted_path(), "LC_ALL": "C"}
    for claim_id, mutation in _CATALOGUE.items():
        verify_candidate_integrity(candidate, cas=cas)
        source = owned.get(mutation.path)
        if source is None:
            raise CandidateIntegrityError(f"P1 mutation target is outside candidate source closure: {mutation.path}")
        target = candidate.candidate_workspace / mutation.path
        before = target.read_bytes()
        if _sha(before) != source.file_sha256:
            raise CandidateIntegrityError(f"stale P1 mutation preimage: {mutation.path}")
        text = before.decode("utf-8")
        for expected, replacement in mutation.replacements:
            if text.count(expected) != 1:
                raise CandidateIntegrityError(f"P1 mutation preimage is missing or ambiguous: {claim_id}")
            text = text.replace(expected, replacement, 1)
        after = text.encode("utf-8")
        obligation = by_claim[claim_id]
        argv = tuple(
            str(Path(sys.executable).absolute()) if arg == "{python}" else arg
            for arg in obligation.argv
        )
        command = canonical_command(argv, environment=environment)
        limits = SandboxLimits(cpu_seconds=obligation.timeout_s, wallclock_s=obligation.timeout_s)
        positive = _run_in_verification_workspace(
            command, workspace=candidate.candidate_workspace, limits=limits
        )
        _assert_qualified(positive, negative=False)
        verify_candidate_integrity(candidate, cas=cas)
        with tempfile.TemporaryDirectory(prefix="paeos-p1-negative-") as raw:
            negative_root = Path(raw) / "candidate"
            shutil.copytree(candidate.candidate_workspace, negative_root, symlinks=True)
            negative_target = negative_root / mutation.path
            if _sha(negative_target.read_bytes()) != source.file_sha256:
                raise CandidateIntegrityError("P1 negative copy changed its source preimage")
            negative_target.write_bytes(after)
            negative = _run_in_verification_workspace(
                command, workspace=negative_root, limits=limits
            )
        _assert_qualified(negative, negative=True)
        mutation_sha = _sha(json.dumps({"path": mutation.path, "replacements": mutation.replacements}, sort_keys=True).encode())
        records.append({"claim_id": claim_id, "candidate_id": candidate.candidate_id, "candidate_sha256": candidate.cas_artifact_hash, "target_path": mutation.path, "source_cas_hash": source.cas_hash, "source_preimage_sha256": source.file_sha256, "source_postimage_sha256": _sha(after), "mutation_sha256": mutation_sha, "positive_result_sha256": _result_hash(positive, environment), "negative_result_sha256": _result_hash(negative, environment), "positive_result": _physical_result(positive, environment), "negative_result": _physical_result(negative, environment)})
    return tuple(records)
