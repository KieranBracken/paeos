#!/usr/bin/env python3
"""Capture one PAEOS Layer 14 physical auditor receipt through the model router.

This command is intentionally one-shot: the router owns policy and may reject the request, while
the receipt layer rejects retries/fallbacks and persists only hashes and identities.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from paeos.model_router.auditor_receipt import (
    AuditorReceiptContract,
    AuditorReceiptError,
    capture_auditor_receipt,
    persist_auditor_receipt,
    request_fingerprint,
)
from paeos.model_router.router import ModelRouter
from paeos.model_router.types import (
    DataClass,
    LogicalModel,
    ModelFamily,
    TaskClass,
    TaskRequest,
)

_SHA40 = re.compile(r"^[0-9a-f]{40}$")
_SHA64 = re.compile(r"^[0-9a-f]{64}$")
_MAX_PROMPT_BYTES = 4 * 1024 * 1024


def _absolute_regular_file(path: Path, label: str) -> Path:
    if not path.is_absolute() or path.is_symlink() or not path.is_file():
        raise AuditorReceiptError(f"{label} must be an absolute regular file")
    if path.stat().st_size > _MAX_PROMPT_BYTES:
        raise AuditorReceiptError(f"{label} exceeds size limit")
    return path


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audit-id", required=True)
    parser.add_argument("--candidate-sha", required=True)
    parser.add_argument("--evidence-sha", required=True)
    parser.add_argument("--prompt-file", required=True, type=Path)
    parser.add_argument("--receipt-path", required=True, type=Path)
    parser.add_argument("--max-tokens", type=int, default=2_000)
    args = parser.parse_args(argv)
    if not args.audit_id or any(character.isspace() for character in args.audit_id):
        parser.error("--audit-id must be non-empty and contain no whitespace")
    if not _SHA40.fullmatch(args.candidate_sha):
        parser.error("--candidate-sha must be a lowercase 40-character commit SHA")
    if not _SHA64.fullmatch(args.evidence_sha):
        parser.error("--evidence-sha must be a lowercase 64-character SHA-256")
    if args.max_tokens <= 0:
        parser.error("--max-tokens must be positive")
    return args


def run(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    try:
        prompt_file = _absolute_regular_file(args.prompt_file, "--prompt-file")
        if not args.receipt_path.is_absolute():
            raise AuditorReceiptError("--receipt-path must be absolute")
        prompt = prompt_file.read_text(encoding="utf-8")
        request = TaskRequest(
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Perform an independent Layer 14 audit. Do not modify files, "
                        "execute tools, "
                        "or claim Gate A closure. Return concise findings and disposition."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            task_class=TaskClass.AUDIT,
            data_class=DataClass.INTERNAL,
            logical_model=LogicalModel.PAEOS_AUDIT,
            builder_family=ModelFamily.GLM,
            max_tokens=args.max_tokens,
            temperature=0.0,
        )
        contract = AuditorReceiptContract(
            audit_id=args.audit_id,
            candidate_sha256=args.candidate_sha,
            evidence_bundle_sha256=args.evidence_sha,
            review_scope_sha256=request_fingerprint(request),
            builder_provider="cline-pass",
            builder_model_id="z-ai/glm-5.3-flash",
            builder_family=ModelFamily.GLM,
        )
        receipt = capture_auditor_receipt(ModelRouter(), contract, request)
        persist_auditor_receipt(receipt, args.receipt_path)
    except AuditorReceiptError as error:
        print(f"AUDITOR_RECEIPT_REJECTED:{error}", file=sys.stderr)
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
                "receipt_sha256": receipt.receipt_sha256,
                "actual_provider": receipt.actual_provider_id.value,
                "actual_model": receipt.actual_model_id,
                "actual_family": receipt.actual_family.value,
                "provider_attempt_count": receipt.provider_attempt_count,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
