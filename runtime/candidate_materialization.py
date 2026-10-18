"""Trusted, unpromoted L12 candidate materialization.

This module is deliberately mechanical.  It copies the non-sensitive repository baseline into a
state-owned workspace, applies the exact bytes collected by ``AgentDispatcher``, stores a
content-addressed changed-file manifest, and records an immutable candidate descriptor.  It does
not inspect Builder prose, decide correctness, or promote anything; L13 and L16 retain those
authorities.
"""

from __future__ import annotations

import io
import json
import os
import shutil
import subprocess
import tarfile
import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path

from kernel.cas import CAS, content_hash
from kernel.types import Hash

__all__ = [
    "CandidateFile",
    "CandidateIntegrityError",
    "CandidateMaterialization",
    "CandidateStatus",
    "freeze_l11_plan",
    "freeze_verification_source_files",
    "freeze_verification_support_files",
    "materialize_candidate",
    "physical_base_revision",
    "verify_candidate_integrity",
]


class CandidateIntegrityError(ValueError):
    """The candidate or its runtime binding is missing, changed, or malformed."""


def physical_base_revision(repo_root: Path) -> str:
    """Read the repository's physical immutable base revision for candidate provenance."""
    try:
        result = subprocess.run(
            ["git", "-C", str(repo_root), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise CandidateIntegrityError("unable to obtain physical base revision") from exc
    revision = result.stdout.strip()
    if result.returncode != 0 or not revision or any(ch.isspace() for ch in revision):
        raise CandidateIntegrityError("physical base revision is unavailable")
    return revision


class CandidateStatus(StrEnum):
    UNPROMOTED_PENDING_VERIFICATION = "UNPROMOTED_PENDING_VERIFICATION"


@dataclass(frozen=True, slots=True)
class CandidateFile:
    path: str
    cas_hash: Hash
    file_sha256: Hash
    size: int


@dataclass(frozen=True, slots=True)
class CandidateMaterialization:
    candidate_id: str
    run_id: str
    l11_binding_sha256: Hash
    builder_identity: str
    base_revision: str
    changed_files: tuple[CandidateFile, ...]
    verification_support_files: tuple[CandidateFile, ...]
    verification_source_files: tuple[CandidateFile, ...]
    tree_sha256: Hash
    diff_sha256: Hash
    cas_artifact_hash: Hash
    workspace_identity: str
    environment_identity: str
    created_at: str
    status: CandidateStatus
    candidate_workspace: Path
    metadata_path: Path

    def to_json(self) -> dict[str, object]:
        return {
            "candidate_id": self.candidate_id,
            "run_id": self.run_id,
            "l11_binding_sha256": self.l11_binding_sha256,
            "builder_identity": self.builder_identity,
            "base_revision": self.base_revision,
            "changed_files": [
                {
                    "path": item.path,
                    "cas_hash": item.cas_hash,
                    "file_sha256": item.file_sha256,
                    "size": item.size,
                }
                for item in self.changed_files
            ],
            "verification_support_files": [
                {
                    "path": item.path,
                    "cas_hash": item.cas_hash,
                    "file_sha256": item.file_sha256,
                    "size": item.size,
                }
                for item in self.verification_support_files
            ],
            "verification_source_files": [
                {
                    "path": item.path,
                    "cas_hash": item.cas_hash,
                    "file_sha256": item.file_sha256,
                    "size": item.size,
                }
                for item in self.verification_source_files
            ],
            "tree_sha256": self.tree_sha256,
            "diff_sha256": self.diff_sha256,
            "cas_artifact_hash": self.cas_artifact_hash,
            "workspace_identity": self.workspace_identity,
            "environment_identity": self.environment_identity,
            "created_at": self.created_at,
            "status": self.status.value,
        }


_SKIP_NAMES = frozenset(
    {
        ".git",
        # Developer-only Claude worktree/skill projections are not runtime source.  The
        # repository contains a tracked symlink here; excluding the whole projection keeps the
        # candidate baseline regular-file-only without dereferencing a path outside the candidate.
        ".claude",
        ".venv",
        "__pycache__",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
        ".tox",
        ".state",
    }
)
_QUARANTINED_NAMES = frozenset(
    {".env", ".env.local", ".env.production", "api_keys.json", "sentium"}
)
_QUARANTINED_PREFIXES = frozenset(
    {"backlog/research", "misc/_research_verdicts", "ops/keys"}
)
_SAFE_CREDENTIAL_SOURCE = "paeos/model_router/credentials.py"


def _is_quarantined(relative: str) -> bool:
    normalized = Path(relative).as_posix().casefold()
    # ``credentials.py`` is the model-router's credential-loading implementation, not a
    # credential store.  It is required for isolated candidate Court replay.  Keep the exception
    # path-exact so similarly named files elsewhere remain denied by the quarantine policy.
    if normalized == _SAFE_CREDENTIAL_SOURCE:
        return False
    if normalized == "credentials.py" or normalized.endswith("/credentials.py"):
        return True
    return any(
        normalized == prefix or normalized.startswith(prefix + "/")
        for prefix in _QUARANTINED_PREFIXES
    ) or any(
        part.casefold() in _QUARANTINED_NAMES or part.casefold().startswith("sentium")
        for part in Path(relative).parts
    )


def _safe_relative(relative: str) -> str:
    path = Path(relative)
    if path.is_absolute() or not relative or ".." in path.parts or path == Path("."):
        raise CandidateIntegrityError(f"candidate path is not repository-relative: {relative!r}")
    normalized = path.as_posix()
    if _is_quarantined(normalized):
        raise CandidateIntegrityError(f"quarantined candidate path: {normalized}")
    return normalized


def _copy_baseline(source: Path, destination: Path, base_revision: str) -> None:
    """Materialize the immutable Git base, never the dirty host working tree."""
    if not source.is_absolute() or source.is_symlink() or not source.is_dir():
        raise CandidateIntegrityError("repo_root must be an absolute regular directory")
    if not base_revision or any(ch.isspace() for ch in base_revision):
        raise CandidateIntegrityError("base revision is invalid")
    try:
        result = subprocess.run(
            ["git", "-C", str(source), "archive", "--format=tar", base_revision],
            capture_output=True,
            check=False,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise CandidateIntegrityError("unable to materialize the physical Git base") from exc
    if result.returncode != 0 or not result.stdout:
        raise CandidateIntegrityError("physical Git base archive failed")
    try:
        with tarfile.open(fileobj=io.BytesIO(result.stdout), mode="r:") as archive:
            for member in archive.getmembers():
                relative = Path(member.name).as_posix()
                if not relative or relative == "." or relative.startswith("../"):
                    raise CandidateIntegrityError("Git archive contains a tree-escaping path")
                if _is_quarantined(relative) or any(part in _SKIP_NAMES for part in Path(relative).parts):
                    continue
                if member.issym() or member.islnk() or not (member.isfile() or member.isdir()):
                    raise CandidateIntegrityError(f"Git archive contains an unsafe entry: {relative}")
                target = destination / relative
                if member.isdir():
                    target.mkdir(parents=True, exist_ok=True)
                    continue
                target.parent.mkdir(parents=True, exist_ok=True)
                extracted = archive.extractfile(member)
                if extracted is None:
                    raise CandidateIntegrityError(f"Git archive file could not be read: {relative}")
                target.write_bytes(extracted.read())
                target.chmod(member.mode & 0o777)
    except (OSError, tarfile.TarError) as exc:
        raise CandidateIntegrityError("physical Git base archive is unreadable") from exc


def _tree_hash(workspace: Path) -> Hash:
    records: list[str] = []
    for path in sorted(workspace.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(workspace).as_posix()
        if _is_quarantined(relative) or any(part in _SKIP_NAMES for part in Path(relative).parts):
            continue
        data = path.read_bytes()
        records.append(f"{relative}\0{content_hash(data)}\0{len(data)}\n")
    return content_hash("".join(records).encode("utf-8"))


def _write_once(path: Path, payload: bytes) -> None:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    fd = os.open(path, flags, 0o600)
    try:
        offset = 0
        while offset < len(payload):
            written = os.write(fd, payload[offset:])
            if written <= 0:
                raise OSError(f"short write for {path}")
            offset += written
        os.fsync(fd)
    finally:
        os.close(fd)


def freeze_l11_plan(cas: CAS, plan: Mapping[str, object]) -> str:
    """Persist the canonical L11 plan bytes and return their immutable CAS binding."""
    if not plan:
        raise CandidateIntegrityError("L11 plan must not be empty")
    payload = (json.dumps(plan, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
    return cas.put(payload)


def _freeze_verification_files(
    *, repo_root: Path, paths: tuple[str, ...], cas: CAS, label: str
) -> tuple[CandidateFile, ...]:
    """Snapshot one explicit L11 verifier closure into CAS."""

    source_root = repo_root.resolve()
    if not source_root.is_absolute() or source_root.is_symlink() or not source_root.is_dir():
        raise CandidateIntegrityError(f"{label} root must be an absolute regular directory")
    frozen: list[CandidateFile] = []
    seen: set[str] = set()
    for raw_path in paths:
        relative = _safe_relative(raw_path)
        if relative in seen:
            raise CandidateIntegrityError(f"duplicate {label} path: {relative}")
        source = source_root / relative
        try:
            resolved = source.resolve(strict=True)
        except OSError as exc:
            raise CandidateIntegrityError(f"{label} path is unavailable: {relative}") from exc
        if not resolved.is_relative_to(source_root) or source.is_symlink() or not source.is_file():
            raise CandidateIntegrityError(
                f"{label} path is not a regular in-repository file: {relative}"
            )
        data = source.read_bytes()
        frozen.append(
            CandidateFile(
                path=relative,
                cas_hash=cas.put(data),
                file_sha256=content_hash(data),
                size=len(data),
            )
        )
        seen.add(relative)
    return tuple(sorted(frozen, key=lambda item: item.path))


def freeze_verification_source_files(
    *, repo_root: Path, paths: tuple[str, ...], cas: CAS
) -> tuple[CandidateFile, ...]:
    """Snapshot the explicit L11 current-source closure into CAS.

    These are trusted, non-Builder source inputs required to replay the frozen verifier against a
    candidate reconstructed from Git.  The manifest owns the path list; this function binds the
    exact bytes before the Builder starts so later dirty-tree mutation cannot change the verifier.
    """
    return _freeze_verification_files(
        repo_root=repo_root, paths=paths, cas=cas, label="verification source"
    )


def freeze_verification_support_files(
    *, repo_root: Path, paths: tuple[str, ...], cas: CAS
) -> tuple[CandidateFile, ...]:
    """Snapshot the explicit L11 verifier-support closure into CAS.

    These files are trusted verification inputs, not Builder-authored changes.  The caller must
    pass the paths from the authoritative L11 manifest; this function binds the exact bytes before
    the Builder starts so a later dirty-tree mutation cannot silently change the verifier.
    """
    return _freeze_verification_files(
        repo_root=repo_root, paths=paths, cas=cas, label="verification support"
    )


def materialize_candidate(
    *,
    repo_root: Path,
    written_paths: tuple[tuple[str, Hash], ...],
    cas: CAS,
    state_dir: Path,
    run_id: str,
    l11_binding_sha256: Hash,
    builder_identity: str,
    base_revision: str,
    workspace_identity: str,
    environment_identity: str,
    affected_paths: tuple[str, ...] = (),
    verification_support_files: tuple[tuple[str, Hash], ...] = (),
    verification_source_files: tuple[tuple[str, Hash], ...] = (),
) -> CandidateMaterialization:
    """Create one immutable, state-owned candidate from runtime-collected bytes."""
    if not run_id or not builder_identity or not base_revision or not workspace_identity:
        raise CandidateIntegrityError("candidate identity bindings must be non-empty")
    if len(l11_binding_sha256) != 64 or not all(c in "0123456789abcdef" for c in l11_binding_sha256):
        raise CandidateIntegrityError("invalid L11 binding hash")
    normalized: list[tuple[str, Hash]] = []
    seen: set[str] = set()
    authorized = tuple(_safe_relative(item) for item in affected_paths)
    for raw_path, artifact_hash in written_paths:
        path = _safe_relative(raw_path)
        if path in seen:
            raise CandidateIntegrityError(f"duplicate candidate path: {path}")
        if not cas.has(artifact_hash):
            raise CandidateIntegrityError(f"candidate CAS artifact is missing: {artifact_hash}")
        if authorized and not any(
            path == item or path.startswith(item.rstrip("/") + "/") for item in authorized
        ):
            raise CandidateIntegrityError(f"candidate path is outside the frozen affected set: {path}")
        seen.add(path)
        normalized.append((path, artifact_hash))
    if not normalized:
        raise CandidateIntegrityError("successful L12 candidate must contain at least one file")
    support: list[CandidateFile] = []
    support_seen: set[str] = set()
    for raw_path, artifact_hash in verification_support_files:
        path = _safe_relative(raw_path)
        if path in seen or path in support_seen:
            raise CandidateIntegrityError(
                f"path is both Builder output and verification support: {path}"
                if path in seen
                else f"duplicate verification support path: {path}"
            )
        if not cas.has(artifact_hash):
            raise CandidateIntegrityError(f"verification support CAS artifact is missing: {artifact_hash}")
        data = cas.get(artifact_hash)
        support.append(
            CandidateFile(
                path=path,
                cas_hash=artifact_hash,
                file_sha256=content_hash(data),
                size=len(data),
            )
        )
        support_seen.add(path)
    support.sort(key=lambda item: item.path)
    source: list[CandidateFile] = []
    source_seen: set[str] = set()
    for raw_path, artifact_hash in verification_source_files:
        path = _safe_relative(raw_path)
        if path in seen or path in support_seen or path in source_seen:
            raise CandidateIntegrityError(
                f"path is both Builder output and verification source: {path}"
                if path in seen
                else (
                    f"path is both verification support and verification source: {path}"
                    if path in support_seen
                    else f"duplicate verification source path: {path}"
                )
            )
        if not cas.has(artifact_hash):
            raise CandidateIntegrityError(f"verification source CAS artifact is missing: {path}")
        data = cas.get(artifact_hash)
        source.append(
            CandidateFile(
                path=path,
                cas_hash=artifact_hash,
                file_sha256=content_hash(data),
                size=len(data),
            )
        )
        source_seen.add(path)
    source.sort(key=lambda item: item.path)

    state = state_dir.resolve()
    state.mkdir(mode=0o700, parents=True, exist_ok=True)
    candidate_id = "cand-" + uuid.uuid4().hex
    candidate_root = state / "candidates" / candidate_id
    workspace = candidate_root / "workspace"
    workspace.mkdir(mode=0o700, parents=True, exist_ok=False)
    try:
        _copy_baseline(repo_root.resolve(), workspace, base_revision)
        changed: list[CandidateFile] = []
        for relative, artifact_hash in sorted(normalized):
            target = workspace / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.is_symlink() or (target.exists() and not target.is_file()):
                raise CandidateIntegrityError(f"candidate target is not a regular file: {relative}")
            data = cas.get(artifact_hash)
            target.write_bytes(data)
            changed.append(
                CandidateFile(
                    path=relative,
                    cas_hash=artifact_hash,
                    file_sha256=content_hash(data),
                    size=len(data),
                )
            )
        for item in support:
            target = workspace / item.path
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.is_symlink() or (target.exists() and not target.is_file()):
                raise CandidateIntegrityError(
                    f"verification support target is not a regular file: {item.path}"
                )
            data = cas.get(item.cas_hash)
            target.write_bytes(data)
        for item in source:
            target = workspace / item.path
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.is_symlink() or (target.exists() and not target.is_file()):
                raise CandidateIntegrityError(
                    f"verification source target is not a regular file: {item.path}"
                )
            target.write_bytes(cas.get(item.cas_hash))
        diff_payload = json.dumps(
            [
                {"path": item.path, "cas_hash": item.cas_hash, "file_sha256": item.file_sha256, "size": item.size}
                for item in changed
            ],
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        diff_hash = content_hash(diff_payload)
        tree_hash = _tree_hash(workspace)
        artifact_payload = json.dumps(
            {
                "candidate_id": candidate_id,
                "run_id": run_id,
                "l11_binding_sha256": l11_binding_sha256,
                "builder_identity": builder_identity,
                "base_revision": base_revision,
                "workspace_identity": workspace_identity,
                "environment_identity": environment_identity,
                "tree_sha256": tree_hash,
                "diff_sha256": diff_hash,
                "files": json.loads(diff_payload),
                "verification_support_files": [
                    {
                        "path": item.path,
                        "cas_hash": item.cas_hash,
                        "file_sha256": item.file_sha256,
                        "size": item.size,
                    }
                    for item in support
                ],
                "verification_source_files": [
                    {
                        "path": item.path,
                        "cas_hash": item.cas_hash,
                        "file_sha256": item.file_sha256,
                        "size": item.size,
                    }
                    for item in source
                ],
                "status": CandidateStatus.UNPROMOTED_PENDING_VERIFICATION.value,
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        artifact_hash = cas.put(artifact_payload)
        candidate = CandidateMaterialization(
            candidate_id=candidate_id,
            run_id=run_id,
            l11_binding_sha256=l11_binding_sha256,
            builder_identity=builder_identity,
            base_revision=base_revision,
            changed_files=tuple(changed),
            verification_support_files=tuple(support),
            verification_source_files=tuple(source),
            tree_sha256=tree_hash,
            diff_sha256=diff_hash,
            cas_artifact_hash=artifact_hash,
            workspace_identity=workspace_identity,
            environment_identity=environment_identity,
            created_at=datetime.now(UTC).isoformat(),
            status=CandidateStatus.UNPROMOTED_PENDING_VERIFICATION,
            candidate_workspace=workspace,
            metadata_path=candidate_root / "candidate.json",
        )
        payload = (json.dumps(candidate.to_json(), sort_keys=True, separators=(",", ":")) + "\n").encode()
        _write_once(candidate.metadata_path, payload)
        return candidate
    except BaseException:
        shutil.rmtree(candidate_root, ignore_errors=True)
        raise


def verify_candidate_integrity(
    candidate: CandidateMaterialization,
    *,
    run_id: str | None = None,
    workspace_identity: str | None = None,
    cas: CAS | None = None,
) -> bool:
    """Re-derive candidate identity before L13/Court; no semantic approval is performed."""
    if candidate.status is not CandidateStatus.UNPROMOTED_PENDING_VERIFICATION:
        raise CandidateIntegrityError("candidate is not pending verification")
    if run_id is not None and candidate.run_id != run_id:
        raise CandidateIntegrityError("run binding mismatch")
    if workspace_identity is not None and candidate.workspace_identity != workspace_identity:
        raise CandidateIntegrityError("workspace binding mismatch")
    if not candidate.candidate_workspace.is_absolute() or candidate.candidate_workspace.is_symlink():
        raise CandidateIntegrityError("candidate workspace is not a stable regular directory")
    if not candidate.candidate_workspace.is_dir():
        raise CandidateIntegrityError("candidate workspace is missing")
    if not candidate.metadata_path.is_file() or candidate.metadata_path.is_symlink():
        raise CandidateIntegrityError("candidate metadata is missing or unsafe")
    try:
        metadata = json.loads(candidate.metadata_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CandidateIntegrityError("candidate metadata is malformed") from exc
    if metadata != candidate.to_json():
        raise CandidateIntegrityError("candidate metadata binding mismatch")
    if _tree_hash(candidate.candidate_workspace) != candidate.tree_sha256:
        raise CandidateIntegrityError("candidate tree hash mismatch")
    for item in candidate.changed_files:
        target = candidate.candidate_workspace / item.path
        if target.is_symlink() or not target.is_file():
            raise CandidateIntegrityError(f"candidate changed file is missing: {item.path}")
        data = target.read_bytes()
        if content_hash(data) != item.file_sha256 or len(data) != item.size:
            raise CandidateIntegrityError(f"candidate changed file hash mismatch: {item.path}")
        if cas is not None and cas.get(item.cas_hash) != data:
            raise CandidateIntegrityError(f"candidate CAS binding mismatch: {item.path}")
    for item in candidate.verification_support_files:
        target = candidate.candidate_workspace / item.path
        if target.is_symlink() or not target.is_file():
            raise CandidateIntegrityError(f"candidate verification support is missing: {item.path}")
        data = target.read_bytes()
        if content_hash(data) != item.file_sha256 or len(data) != item.size:
            raise CandidateIntegrityError(f"candidate verification support hash mismatch: {item.path}")
        if cas is not None and cas.get(item.cas_hash) != data:
            raise CandidateIntegrityError(f"candidate verification support CAS binding mismatch: {item.path}")
    for item in candidate.verification_source_files:
        target = candidate.candidate_workspace / item.path
        if target.is_symlink() or not target.is_file():
            raise CandidateIntegrityError(f"candidate verification source is missing: {item.path}")
        data = target.read_bytes()
        if content_hash(data) != item.file_sha256 or len(data) != item.size:
            raise CandidateIntegrityError(f"candidate verification source hash mismatch: {item.path}")
        if cas is not None and cas.get(item.cas_hash) != data:
            raise CandidateIntegrityError(
                f"candidate verification source CAS binding mismatch: {item.path}"
            )
    if cas is not None:
        if not cas.has(candidate.cas_artifact_hash):
            raise CandidateIntegrityError("candidate CAS artifact is missing")
        try:
            aggregate = json.loads(cas.get(candidate.cas_artifact_hash).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise CandidateIntegrityError("candidate CAS aggregate is malformed") from exc
        expected_aggregate = {
            "candidate_id": candidate.candidate_id,
            "run_id": candidate.run_id,
            "l11_binding_sha256": candidate.l11_binding_sha256,
            "builder_identity": candidate.builder_identity,
            "base_revision": candidate.base_revision,
            "workspace_identity": candidate.workspace_identity,
            "environment_identity": candidate.environment_identity,
            "tree_sha256": candidate.tree_sha256,
            "diff_sha256": candidate.diff_sha256,
            "files": [
                {
                    "path": item.path,
                    "cas_hash": item.cas_hash,
                    "file_sha256": item.file_sha256,
                    "size": item.size,
                }
                for item in candidate.changed_files
            ],
            "verification_support_files": [
                {
                    "path": item.path,
                    "cas_hash": item.cas_hash,
                    "file_sha256": item.file_sha256,
                    "size": item.size,
                }
                for item in candidate.verification_support_files
            ],
            "verification_source_files": [
                {
                    "path": item.path,
                    "cas_hash": item.cas_hash,
                    "file_sha256": item.file_sha256,
                    "size": item.size,
                }
                for item in candidate.verification_source_files
            ],
            "status": candidate.status.value,
        }
        if aggregate != expected_aggregate:
            raise CandidateIntegrityError("candidate CAS aggregate binding mismatch")
    return True
