"""Single-use exact-ref promotion controller (Gate F Task 5)."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import threading
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from kernel.capability import CapabilityBroker, CapabilityError
from kernel.cas import is_valid_hash
from kernel.promotion import (
    PromotionEvidence,
    PromotionIntent,
    evaluate_promotion,
    promotion_operation,
)
from kernel.types import CapabilityToken, Role, StageId


class PromotionError(RuntimeError):
    """Raised when a promotion request is denied or fails execution."""


@dataclass(frozen=True, slots=True)
class PromotionReceipt:
    repository_id: str
    target_ref: str
    prior_head: str
    new_head: str
    promoted_at: str
    receipt_hash: str


class PromotionController:
    """Dormant controller enforcing one exact-ref update after bootstrap.

    The default instance is intentionally incapable of promotion.  A later Founder
    bootstrap must inject a manifest hash, state root, and explicit evidence before
    this class can touch a disposable repository.  No shell is used: Git is invoked
    through an absolute binary path with a fixed argument vector.
    """

    def __init__(
        self,
        capability_broker: CapabilityBroker | None = None,
        *,
        bootstrap_manifest_hash: str | None = None,
        state_root: Path | None = None,
        git_binary: str = "/usr/bin/git",
        cas: Any = None,
    ) -> None:
        if bootstrap_manifest_hash is not None and not is_valid_hash(bootstrap_manifest_hash):
            raise ValueError("bootstrap manifest hash must be a lowercase SHA-256")
        self._broker = capability_broker or CapabilityBroker()
        self._bootstrap_manifest_hash = bootstrap_manifest_hash
        self._state_root = state_root
        self._git_binary = git_binary
        self._cas = cas
        self._consumed_tokens: set[str] = set()
        self._lock = threading.Lock()

    def promote(
        self,
        intent: PromotionIntent,
        token: CapabilityToken,
        *,
        current_seq: int,
        current_target_head: str,
        evidence: PromotionEvidence | None = None,
        repository_path: Path | None = None,
        cas: Any = None,
        candidate_files: Any = None,
        candidate_base_dir: Path | str | None = None,
    ) -> PromotionReceipt:
        evidence = evidence or PromotionEvidence()
        effective_cas = cas if cas is not None else self._cas
        reasons = evaluate_promotion(
            intent,
            evidence,
            cas=effective_cas,
            candidate_files=candidate_files,
            candidate_base_dir=candidate_base_dir,
        )
        if self._bootstrap_manifest_hash is None and "FOUNDER_BOOTSTRAP_REQUIRED" not in reasons:
            reasons = ("FOUNDER_BOOTSTRAP_REQUIRED", *reasons)
        if reasons:
            raise PromotionError("promotion denied: " + ", ".join(reasons))
        if repository_path is None:
            raise PromotionError("promotion repository is required")
        if not Path(self._git_binary).is_absolute():
            raise PromotionError("Git binary must be an absolute pinned path")
        repository = repository_path.resolve()
        if not repository.is_dir():
            raise PromotionError("promotion repository must be an existing directory")
        if current_target_head != intent.expected_target_head:
            raise PromotionError("target head changed; reconciliation required")
        expected_op = promotion_operation(intent)
        try:
            self._broker.verify(
                token=token,
                goal_id=token.bound_to.goal_id,
                run_id=token.bound_to.run_id,
                stage=StageId.SEAL,
                role=Role.RATIFIER,
                operation=expected_op,
                current_seq=current_seq,
                session=token.bound_to.session,
            )
        except CapabilityError as e:
            raise PromotionError(f"promotion not permitted by capability: {e}") from e

        with self._lock:
            token_id = hashlib.sha256(token.token.encode("ascii")).hexdigest()
            if token_id in self._consumed_tokens:
                raise PromotionError("single-use promotion token already consumed")

            actual_head = self._git(
                repository,
                "rev-parse",
                "--verify",
                f"{intent.target_ref}^{{commit}}",
            )
            if actual_head != intent.expected_target_head:
                raise PromotionError("target head changed; reconciliation required")
            self._verify_ancestry(repository, intent)
            self._verify_rollback(repository, intent)
            prepared = self._persist_prepared(token_id, intent, actual_head)
            try:
                self._git(
                    repository,
                    "update-ref",
                    intent.target_ref,
                    intent.reviewed_commit,
                    intent.expected_target_head,
                )
            except PromotionError:
                raise

            now_iso = datetime.now(UTC).isoformat()
            payload = {
                "repository_id": intent.repository_id,
                "target_ref": intent.target_ref,
                "prior_head": intent.expected_target_head,
                "new_head": intent.reviewed_commit,
                "promoted_at": now_iso,
            }
            encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
            receipt_hash = hashlib.sha256(encoded).hexdigest()
            receipt = PromotionReceipt(
                repository_id=intent.repository_id,
                target_ref=intent.target_ref,
                prior_head=intent.expected_target_head,
                new_head=intent.reviewed_commit,
                promoted_at=now_iso,
                receipt_hash=receipt_hash,
            )
            self._persist_receipt(token_id, receipt, prepared)
            self._consumed_tokens.add(token_id)
            return receipt

    def _git(self, repository: Path, *args: str) -> str:
        try:
            result = subprocess.run(
                [self._git_binary, "-C", str(repository), *args],
                capture_output=True,
                text=True,
                check=False,
                timeout=10,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise PromotionError(f"Git operation unavailable: {exc}") from exc
        if result.returncode != 0:
            detail = result.stderr.strip() or result.stdout.strip() or "unknown Git failure"
            raise PromotionError(f"Git operation failed: {detail}")
        return result.stdout.strip()

    def _verify_ancestry(self, repository: Path, intent: PromotionIntent) -> None:
        try:
            self._git(
                repository,
                "merge-base",
                "--is-ancestor",
                intent.expected_target_head,
                intent.reviewed_commit,
            )
        except PromotionError as exc:
            raise PromotionError("reviewed commit is not a fast-forward descendant") from exc

    def _verify_rollback(self, repository: Path, intent: PromotionIntent) -> None:
        parents = self._git(
            repository,
            "rev-list",
            "--parents",
            "-n",
            "1",
            intent.rollback_commit,
        ).split()
        if len(parents) != 2 or parents[1] != intent.reviewed_commit:
            raise PromotionError("rollback commit must have reviewed commit as its sole parent")
        expected_tree = self._git(
            repository,
            "rev-parse",
            f"{intent.expected_target_head}^{{tree}}",
        )
        rollback_tree = self._git(repository, "rev-parse", f"{intent.rollback_commit}^{{tree}}")
        if expected_tree != rollback_tree:
            raise PromotionError("rollback tree does not match expected target tree")

    def _persist_prepared(self, token_id: str, intent: PromotionIntent, prior_head: str) -> Path:
        if self._state_root is None:
            raise PromotionError("promotion state root is required")
        root = self._state_root.resolve()
        root.mkdir(parents=True, exist_ok=True)
        path = root / f"promotion-{token_id}.prepared.json"
        payload = {
            "token_id": token_id,
            "intent": {
                "repository_id": intent.repository_id,
                "target_ref": intent.target_ref,
                "expected_target_head": intent.expected_target_head,
                "reviewed_commit": intent.reviewed_commit,
                "rollback_commit": intent.rollback_commit,
                "disposition_hash": intent.disposition_hash,
                "health_command_id": intent.health_command_id,
                "expires_seq": intent.expires_seq,
            },
            "prior_head": prior_head,
            "bootstrap_manifest_hash": self._bootstrap_manifest_hash,
        }
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        try:
            raw = (json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n").encode()
            offset = 0
            while offset < len(raw):
                written = os.write(descriptor, raw[offset:])
                if written <= 0:
                    raise PromotionError("promotion state write made no progress")
                offset += written
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
        directory = os.open(root, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
        return path

    def _persist_receipt(self, token_id: str, receipt: PromotionReceipt, prepared: Path) -> None:
        path = prepared.with_name(prepared.name.replace(".prepared.json", ".receipt.json"))
        payload = {
            "token_id": token_id,
            "repository_id": receipt.repository_id,
            "target_ref": receipt.target_ref,
            "prior_head": receipt.prior_head,
            "new_head": receipt.new_head,
            "promoted_at": receipt.promoted_at,
            "receipt_hash": receipt.receipt_hash,
        }
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        try:
            raw = (json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n").encode()
            offset = 0
            while offset < len(raw):
                written = os.write(descriptor, raw[offset:])
                if written <= 0:
                    raise PromotionError("promotion receipt write made no progress")
                offset += written
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
        directory = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
