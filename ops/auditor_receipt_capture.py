#!/usr/bin/env python3
"""Capture one PAEOS Layer 14 physical auditor receipt through the model router.

This command is intentionally one-shot: the router owns policy and may reject the request, while
the receipt layer rejects retries/fallbacks and persists only hashes and identities.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from pathlib import Path

from paeos.model_router.audit_prompt import validate_substantive_audit_prompt
from paeos.model_router.auditor_receipt import (
    AuditorCaptureResult,
    AuditorReceiptContract,
    AuditorReceiptError,
    adjudicate_auditor_artifact_pair,
    bind_auditor_report,
    capture_auditor_interaction,
    persist_auditor_receipt,
    persist_auditor_report,
    request_fingerprint,
    validate_auditor_receipt,
    validate_auditor_report,
)
from paeos.model_router.router import ModelRouter
from paeos.model_router.types import (
    DataClass,
    LogicalModel,
    ModelFamily,
    NormalizedError,
    RetryPolicy,
    TaskClass,
    TaskRequest,
)

_SHA40 = re.compile(r"^[0-9a-f]{40}$")
_SHA64 = re.compile(r"^[0-9a-f]{64}$")
_MAX_PROMPT_BYTES = 4 * 1024 * 1024
_REJECTION_SCHEMA = "paeos.auditor-rejection/1"
_TRANSPORT_FAILURE_SCHEMA = "paeos.auditor-transport-failure/1"
_BEARER_SECRET_RE = re.compile(r"(?i)\bBearer\s+[^\s,;]+")
_ASSIGNED_SECRET_RE = re.compile(
    r"(?i)(\b(?:api[_ -]?key|authorization|secret|token)\b\s*[:=]\s*)(?!Bearer\b)[^\s,;]+"
)
_KEYLIKE_SECRET_RE = re.compile(r"(?i)\b(?:sk|key|token)-[A-Za-z0-9_-]{8,}\b")


def _absolute_regular_file(path: Path, label: str) -> Path:
    if not path.is_absolute() or path.is_symlink() or not path.is_file():
        raise AuditorReceiptError(f"{label} must be an absolute regular file")
    if path.stat().st_size > _MAX_PROMPT_BYTES:
        raise AuditorReceiptError(f"{label} exceeds size limit")
    return path


def _write_once_private_json(path: Path, payload: dict[str, object]) -> Path:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    encoded = (
        json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True) + "\n"
    ).encode("utf-8")
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        written = 0
        while written < len(encoded):
            count = os.write(descriptor, encoded[written:])
            if count <= 0:
                raise AuditorReceiptError("auditor rejection write made no progress")
            written += count
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    return path


def _redact_secret_text(value: str) -> str:
    """Remove credential-shaped values before diagnostic text leaves the process."""

    redacted = _BEARER_SECRET_RE.sub("Bearer <REDACTED>", value)
    redacted = _ASSIGNED_SECRET_RE.sub(r"\1<REDACTED>", redacted)
    return _KEYLIKE_SECRET_RE.sub("<REDACTED>", redacted)


def _persist_transport_failure(
    error: NormalizedError,
    contract: AuditorReceiptContract,
    receipt_path: Path,
) -> Path:
    """Persist content-free normalized transport evidence exactly once.

    Provider response bodies are intentionally not written: they may contain credentials or
    account metadata.  A digest is retained when a body existed so a later forensic capture can
    prove whether the raw payload changed without exposing it in the repository or quarantine.
    """

    failure_path = receipt_path.with_name(f"{receipt_path.name}.transport-failure.json")
    raw_response = error.raw_response or ""
    provider_id = getattr(error.provider_id, "value", None)
    _write_once_private_json(
        failure_path,
        {
            "audit_id": contract.audit_id,
            "candidate_sha256": contract.candidate_sha256,
            "evidence_bundle_sha256": contract.evidence_bundle_sha256,
            "error_type": error.error_type.value,
            "provider_id": provider_id,
            "model_id": error.model_id,
            "http_status": error.http_status,
            "retry_after": error.retry_after,
            "message": _redact_secret_text(error.message),
            "raw_response_sha256": hashlib.sha256(raw_response.encode("utf-8")).hexdigest()
            if raw_response
            else None,
            "review_scope_sha256": contract.review_scope_sha256,
            "schema": _TRANSPORT_FAILURE_SCHEMA,
        },
    )
    return failure_path


def _persist_rejected_interaction(
    interaction: AuditorCaptureResult,
    contract: AuditorReceiptContract,
    error: AuditorReceiptError,
    report_path: Path,
    receipt_path: Path,
) -> None:
    rejected_report_path = report_path.with_name(f"{report_path.name}.rejected")
    rejected_receipt_path = receipt_path.with_name(f"{receipt_path.name}.rejected")
    rejection_path = receipt_path.with_name(f"{receipt_path.name}.rejection.json")
    persist_auditor_report(interaction.response_content, rejected_report_path)
    persist_auditor_receipt(interaction.receipt, rejected_receipt_path)
    _write_once_private_json(
        rejection_path,
        {
            "audit_id": contract.audit_id,
            "candidate_sha256": contract.candidate_sha256,
            "evidence_bundle_sha256": contract.evidence_bundle_sha256,
            "reason": str(error),
            "receipt_path": str(rejected_receipt_path),
            "receipt_sha256": interaction.receipt.receipt_sha256,
            "report_path": str(rejected_report_path),
            "report_sha256": hashlib.sha256(
                interaction.response_content.encode("utf-8")
            ).hexdigest(),
            "schema": _REJECTION_SCHEMA,
        },
    )


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audit-id", required=True)
    parser.add_argument("--candidate-sha", required=True)
    parser.add_argument("--evidence-sha", required=True)
    parser.add_argument("--prompt-file", required=True, type=Path)
    parser.add_argument("--report-path", required=True, type=Path)
    parser.add_argument("--receipt-path", required=True, type=Path)
    parser.add_argument("--max-tokens", type=int, default=512)
    parser.add_argument("--auditor-model")
    args = parser.parse_args(argv)
    if not args.audit_id or any(character.isspace() for character in args.audit_id):
        parser.error("--audit-id must be non-empty and contain no whitespace")
    if not _SHA40.fullmatch(args.candidate_sha):
        parser.error("--candidate-sha must be a lowercase 40-character commit SHA")
    if not _SHA64.fullmatch(args.evidence_sha):
        parser.error("--evidence-sha must be a lowercase 64-character SHA-256")
    if args.max_tokens <= 0:
        parser.error("--max-tokens must be positive")
    if args.auditor_model is not None and (
        not args.auditor_model or any(character.isspace() for character in args.auditor_model)
    ):
        parser.error("--auditor-model must be non-empty and contain no whitespace")
    return args


def run(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    contract: AuditorReceiptContract | None = None
    try:
        prompt_file = _absolute_regular_file(args.prompt_file, "--prompt-file")
        if not args.receipt_path.is_absolute():
            raise AuditorReceiptError("--receipt-path must be absolute")
        if not args.report_path.is_absolute():
            raise AuditorReceiptError("--report-path must be absolute")
        prompt = prompt_file.read_text(encoding="utf-8")
        validate_substantive_audit_prompt(prompt, args.candidate_sha, args.evidence_sha)
        request = TaskRequest(
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Perform an independent Layer 14 audit. Do not modify files, "
                        "execute tools, "
                        "or claim Gate A closure. The first six non-blank lines of your response "
                        "must be the Candidate SHA, Evidence Bundle SHA-256, L14_STATUS, "
                        "INVARIANT, REPRODUCTION, and the exact Worker/Court accounting lines. "
                        "Do not emit a preamble, analysis, file list, or markdown heading before "
                        "those lines. Return only concise findings after them."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            task_class=TaskClass.AUDIT,
            data_class=DataClass.INTERNAL,
            logical_model=LogicalModel.PAEOS_AUDIT,
            explicit_model=args.auditor_model,
            builder_family=ModelFamily.GLM,
            max_tokens=args.max_tokens,
            temperature=0.0,
            retry_policy=RetryPolicy.NONE,
            allow_fallback=False,
        )
        contract = AuditorReceiptContract(
            audit_id=args.audit_id,
            candidate_sha256=args.candidate_sha,
            evidence_bundle_sha256=args.evidence_sha,
            review_scope_sha256=request_fingerprint(request),
            builder_provider="cline-pass",
            builder_model_id="z-ai/glm-5.3-flash",
            builder_family=ModelFamily.GLM,
            expected_worker_counts=(0, 1, 0),
            expected_court_counts=(0, 0, 0),
        )
        router = ModelRouter()
        interaction = capture_auditor_interaction(router, contract, request)
        try:
            validate_auditor_report(interaction.response_content, contract)
            receipt = bind_auditor_report(interaction.receipt, interaction.response_content)
            validate_auditor_receipt(
                receipt, contract, router.catalog, require_report_binding=True
            )
        except AuditorReceiptError as error:
            _persist_rejected_interaction(
                interaction, contract, error, args.report_path, args.receipt_path
            )
            raise
        persist_auditor_report(interaction.response_content, args.report_path)
        persist_auditor_receipt(receipt, args.receipt_path)
        adjudication = adjudicate_auditor_artifact_pair(
            args.receipt_path, args.report_path, contract, router.catalog
        )
    except AuditorReceiptError as error:
        print(f"AUDITOR_RECEIPT_REJECTED:{error}", file=sys.stderr)
        return 2
    except NormalizedError as error:
        failure_path: Path | None = None
        if contract is not None:
            try:
                failure_path = _persist_transport_failure(error, contract, args.receipt_path)
            except (AuditorReceiptError, OSError) as write_error:
                print(
                    f"AUDITOR_RECEIPT_FAILURE_ARTIFACT_ERROR:{type(write_error).__name__}",
                    file=sys.stderr,
                )
        print(f"AUDITOR_RECEIPT_FAILED:{_redact_secret_text(str(error))}", file=sys.stderr)
        if failure_path is not None:
            print(f"AUDITOR_RECEIPT_FAILURE_ARTIFACT:{failure_path}", file=sys.stderr)
        return 2
    except OSError as error:
        print(f"AUDITOR_RECEIPT_IO_ERROR:{type(error).__name__}", file=sys.stderr)
        return 2
    except Exception as error:
        print(f"AUDITOR_RECEIPT_FAILED:{type(error).__name__}", file=sys.stderr)
        return 2

    print(
        json.dumps(
            {
                "receipt_path": str(args.receipt_path),
                "report_path": str(args.report_path),
                "receipt_sha256": receipt.receipt_sha256,
                "actual_provider": receipt.actual_provider_id.value,
                "actual_model": receipt.actual_model_id,
                "actual_family": receipt.actual_family.value,
                "provider_attempt_count": receipt.provider_attempt_count,
                "report_status": adjudication.report_status.value,
                "a08_verdict": adjudication.a08_verdict,
                "qualified": adjudication.qualified,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
