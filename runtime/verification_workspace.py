"""Isolated proof views for baseline, candidate, and verifier workspaces (Gate E Task 6)."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from kernel.types import ArtifactRef

from runtime.implementation_contract import (
    FrozenImplementationContract,
    validate_implementation_contract,
)


@dataclass(frozen=True, slots=True)
class VerificationViews:
    baseline: Path
    candidate: Path
    verifier: Path
    baseline_head: str
    candidate_head: str
    verifier_manifest_hash: str


def create_verification_views(
    contract: FrozenImplementationContract,
    verifier_bundle: ArtifactRef,
    *,
    base_dir: Path | None = None,
) -> VerificationViews:
    validate_implementation_contract(contract)

    root = base_dir if base_dir is not None else Path("/tmp/paeos_verification")
    ws_dir = root / f"vw_{contract.contract_id}_{contract.contract_hash[:8]}"

    baseline_dir = ws_dir / "baseline"
    candidate_dir = ws_dir / "candidate"
    verifier_dir = ws_dir / "verifier"

    baseline_dir.mkdir(parents=True, exist_ok=True)
    candidate_dir.mkdir(parents=True, exist_ok=True)
    verifier_dir.mkdir(parents=True, exist_ok=True)

    manifest_payload = {
        "contract_id": contract.contract_id,
        "contract_hash": contract.contract_hash,
        "base_commit": contract.base_commit,
        "verifier_bundle_type": verifier_bundle.type,
        "verifier_bundle_hash": str(verifier_bundle.hash),
    }
    encoded = json.dumps(
        manifest_payload, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    verifier_manifest_hash = hashlib.sha256(encoded).hexdigest()

    return VerificationViews(
        baseline=baseline_dir,
        candidate=candidate_dir,
        verifier=verifier_dir,
        baseline_head=contract.base_commit,
        candidate_head=contract.base_commit,
        verifier_manifest_hash=verifier_manifest_hash,
    )
