"""Content-addressed supervisor checkpoints and clean rotation fencing."""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from pathlib import Path

from kernel.cas import CAS
from kernel.ledger import Ledger
from kernel.types import ArtifactRef

from runtime.integrations.bridge_protocol import ProtocolViolation, canonical_json

_HASH = set("0123456789abcdef")
SCHEMA_VERSION = "paeos-supervisor-checkpoint-v1"


def _require_hash(value: str, field: str) -> None:
    if not isinstance(value, str) or len(value) != 64 or set(value) - _HASH:
        raise ProtocolViolation(f"{field} must be a lowercase SHA-256 digest")


def _repository_head(repo: Path) -> str:
    git_path = repo / ".git"
    if git_path.is_file():
        marker = git_path.read_text(encoding="utf-8").strip()
        if marker.startswith("gitdir:"):
            git_path = (repo / marker.split(":", 1)[1].strip()).resolve()
    head_file = git_path / "HEAD"
    if not head_file.is_file():
        raise ProtocolViolation("repository has no readable .git/HEAD")
    head = head_file.read_text(encoding="utf-8").strip()
    if head.startswith("ref: "):
        ref = head[5:]
        ref_file = git_path / ref
        if ref_file.is_file():
            head = ref_file.read_text(encoding="utf-8").strip()
    _require_hash(head, "repository_head")
    return head


def repository_digest(repo: Path) -> str:
    """Hash repository file names and bytes while excluding mutable tool caches."""

    root = repo.resolve()
    records: list[tuple[str, str]] = []
    ignored = {".git", ".venv", "__pycache__", ".pytest_cache", "node_modules"}
    for directory, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(name for name in dirnames if name not in ignored)
        for name in sorted(filenames):
            path = Path(directory) / name
            relative = path.relative_to(root).as_posix()
            records.append((relative, hashlib.sha256(path.read_bytes()).hexdigest()))
    return hashlib.sha256(canonical_json(records).encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class SupervisorCheckpoint:
    schema_version: str
    checkpoint_id: str
    ledger_seq: int
    ledger_head: str
    repository_head: str
    repository_digest: str
    policy_hash: str
    governance_hashes: tuple[tuple[str, str], ...]
    transaction_digests: tuple[tuple[str, str, int], ...]
    open_reconciliation_ids: tuple[str, ...]
    open_debt_ids: tuple[str, ...]
    previous_checkpoint_hash: str | None

    def __post_init__(self) -> None:
        if self.schema_version != SCHEMA_VERSION:
            raise ProtocolViolation("unsupported checkpoint schema_version")
        if not self.checkpoint_id or not isinstance(self.checkpoint_id, str):
            raise ProtocolViolation("checkpoint_id must be non-empty")
        if not isinstance(self.ledger_seq, int) or self.ledger_seq < 0:
            raise ProtocolViolation("ledger_seq must be non-negative")
        for field in ("ledger_head", "repository_head", "repository_digest", "policy_hash"):
            _require_hash(getattr(self, field), field)
        for path, digest in self.governance_hashes:
            if not path or not isinstance(path, str):
                raise ProtocolViolation("governance paths must be non-empty")
            _require_hash(digest, "governance_hash")
        for transaction_key, digest, seq in self.transaction_digests:
            if not transaction_key or not isinstance(transaction_key, str):
                raise ProtocolViolation("transaction keys must be non-empty")
            _require_hash(digest, "transaction_digest")
            if not isinstance(seq, int) or seq < 0:
                raise ProtocolViolation("transaction sequence must be non-negative")
        if self.previous_checkpoint_hash is not None:
            _require_hash(self.previous_checkpoint_hash, "previous_checkpoint_hash")

    def to_bytes(self) -> bytes:
        payload = {
            "schema_version": self.schema_version,
            "checkpoint_id": self.checkpoint_id,
            "ledger_seq": self.ledger_seq,
            "ledger_head": self.ledger_head,
            "repository_head": self.repository_head,
            "repository_digest": self.repository_digest,
            "policy_hash": self.policy_hash,
            "governance_hashes": self.governance_hashes,
            "transaction_digests": self.transaction_digests,
            "open_reconciliation_ids": self.open_reconciliation_ids,
            "open_debt_ids": self.open_debt_ids,
            "previous_checkpoint_hash": self.previous_checkpoint_hash,
        }
        return (canonical_json(payload) + "\n").encode("utf-8")

    @classmethod
    def from_bytes(cls, raw: bytes) -> SupervisorCheckpoint:
        import json

        try:
            value = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ProtocolViolation("checkpoint is not valid UTF-8 JSON") from exc
        if not isinstance(value, dict):
            raise ProtocolViolation("checkpoint must be a JSON object")
        expected = {
            "schema_version",
            "checkpoint_id",
            "ledger_seq",
            "ledger_head",
            "repository_head",
            "repository_digest",
            "policy_hash",
            "governance_hashes",
            "transaction_digests",
            "open_reconciliation_ids",
            "open_debt_ids",
            "previous_checkpoint_hash",
        }
        if set(value) != expected or (canonical_json(value) + "\n").encode("utf-8") != raw:
            raise ProtocolViolation("checkpoint fields or canonical encoding are invalid")
        return cls(
            schema_version=value["schema_version"],
            checkpoint_id=value["checkpoint_id"],
            ledger_seq=value["ledger_seq"],
            ledger_head=value["ledger_head"],
            repository_head=value["repository_head"],
            repository_digest=value["repository_digest"],
            policy_hash=value["policy_hash"],
            governance_hashes=tuple(tuple(item) for item in value["governance_hashes"]),
            transaction_digests=tuple(tuple(item) for item in value["transaction_digests"]),
            open_reconciliation_ids=tuple(value["open_reconciliation_ids"]),
            open_debt_ids=tuple(value["open_debt_ids"]),
            previous_checkpoint_hash=value["previous_checkpoint_hash"],
        )


def verify_checkpoint(checkpoint: SupervisorCheckpoint, *, ledger: Ledger, repo: Path) -> None:
    """Verify chain head and repository snapshot before any claim can rotate."""

    ledger_head = ledger.head_hash()
    if ledger_head != checkpoint.ledger_head:
        raise ProtocolViolation("checkpoint ledger head is stale")
    if len(ledger.read()) != checkpoint.ledger_seq:
        raise ProtocolViolation("checkpoint ledger sequence is stale")
    if _repository_head(repo) != checkpoint.repository_head:
        raise ProtocolViolation("checkpoint repository head is stale")
    if repository_digest(repo) != checkpoint.repository_digest:
        raise ProtocolViolation("checkpoint repository digest is stale")


class SupervisorRotationError(RuntimeError):
    """Rotation refused because an active or ambiguous claim is present."""


class SupervisorCoordinator:
    """Small fencing coordinator for checkpoint creation and adapter rotation.

    The canonical transaction coordinator remains the ledger append authority.  This seam only
    records local claim state and requires a verified CAS checkpoint before changing profiles.
    """

    def __init__(self, *, ledger: Ledger, cas: CAS, repo: Path, policy_hash: str) -> None:
        _require_hash(policy_hash, "policy_hash")
        self._ledger = ledger
        self._cas = cas
        self._repo = repo
        self._policy_hash = policy_hash
        self._active_claim = False
        self._ambiguous_claim = False
        self._current_profile: str | None = None
        self._previous_checkpoint_hash: str | None = None

    def mark_claim(self, *, active: bool, ambiguous: bool = False) -> None:
        self._active_claim = active
        self._ambiguous_claim = ambiguous

    def checkpoint(self, *, expected_ledger_head: str) -> ArtifactRef:
        actual_head = self._ledger.head_hash()
        if actual_head != expected_ledger_head:
            raise SupervisorRotationError("ledger advanced before checkpoint")
        ledger_seq = len(self._ledger.read())
        checkpoint = SupervisorCheckpoint(
            schema_version=SCHEMA_VERSION,
            checkpoint_id=f"checkpoint-{ledger_seq + 1}",
            ledger_seq=ledger_seq,
            ledger_head=actual_head,
            repository_head=_repository_head(self._repo),
            repository_digest=repository_digest(self._repo),
            policy_hash=self._policy_hash,
            governance_hashes=(),
            transaction_digests=(),
            open_reconciliation_ids=(),
            open_debt_ids=(),
            previous_checkpoint_hash=self._previous_checkpoint_hash,
        )
        raw = checkpoint.to_bytes()
        digest = self._cas.put(raw)
        self._previous_checkpoint_hash = digest
        return ArtifactRef(hash=digest, type="supervisor-checkpoint")

    def rotate(self, *, from_profile: str, to_profile: str, checkpoint_ref: ArtifactRef) -> None:
        if self._active_claim or self._ambiguous_claim:
            raise SupervisorRotationError(
                "active or ambiguous claim must be isolated before rotation"
            )
        if self._current_profile is not None and self._current_profile != from_profile:
            raise SupervisorRotationError("rotation source profile is stale")
        checkpoint = SupervisorCheckpoint.from_bytes(self._cas.get(checkpoint_ref.hash))
        verify_checkpoint(checkpoint, ledger=self._ledger, repo=self._repo)
        self._current_profile = to_profile
