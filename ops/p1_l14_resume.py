"""Fail-closed qualification of one preserved P1 L14 resource-remand attempt.

This module neither invokes a provider nor resumes a run. It proves that a fresh audit attempt
may be prepared for one exact, unchanged candidate whose original L13 clearance is still present
in an intact ledger prefix and whose later rows are terminal bookkeeping only.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

from kernel.cas import CAS, FilesystemCasStore
from kernel.ledger import GENESIS_HASH, Event, compute_row_hash
from runtime.candidate_materialization import (
    CandidateFile,
    CandidateMaterialization,
    CandidateStatus,
    verify_candidate_integrity,
)

_HEX = re.compile(r"^[0-9a-f]{64}$")
_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
_RESOURCE_ERRORS = frozenset({
    "QUOTA_EXHAUSTED",
    "RATE_LIMITED",
    "RATE_LIMIT",
    "QUOTA_EXCEEDED",
    "CREDIT_BALANCE_EXHAUSTED",
})
_TERMINAL_LAYERS = ("RETROSPECT", "EVOLVE", "MEMORY_UPDATE", "IMPROVE_RUNTIME")
_EXPECTED_RETROSPECT_SUBSTRING = "L14 heterogeneous audit failed closed: AuditorReceiptError"
_PRIOR_AUDIT_KINDS = frozenset({"L14_AUDIT_COMPLETED", "L14_AUDIT_PASS", "L14_AUDIT_FAILED", "L14_AUDIT"})
_SEAL_KINDS = frozenset({"COURT_SEALED", "RUN_SEALED", "L16_SEALED", "SEAL_ISSUED", "RUN_QUALIFIED"})

_ROOT06_ANCHORS_SHA256 = "6dd823c690b7c9cfa683d77ff73fa0628e4b25f9af1fe392bb8cdb30d5f95af4"
_ROOT06_ANCHORS_RELATIVE_PATH = "reviews/tasks/P1_DEBT0248_ROOT06_PRESERVATION_ANCHORS_20260919.json"


class ContinuationError(ValueError):
    """The preserved state cannot authorize a bounded L14 continuation."""


def _canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")


def _file_hash(path: Path) -> str:
    if not path.is_absolute() or path.is_symlink() or not path.is_file():
        raise ContinuationError(f"unsafe or missing immutable artifact: {path.name}")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _require_hash(value: str, label: str) -> None:
    if not isinstance(value, str) or _HEX.fullmatch(value) is None:
        raise ContinuationError(f"invalid {label}")


def _parse_timestamp(ts: object) -> float:
    if isinstance(ts, (int, float)):
        return float(ts)
    if isinstance(ts, str):
        try:
            return datetime.fromisoformat(ts).timestamp()
        except ValueError:
            pass
    raise ContinuationError(f"invalid timestamp format: {ts}")


@dataclass(frozen=True, slots=True)
class ContinuationProof:
    schema: str
    run_id: str
    candidate_id: str
    candidate_sha256: str
    manifest_sha256: str
    evidence_tuple_sha256: str
    evidence_bundle_sha256: str
    projection_sha256: str
    disclosure_binding_sha256: str
    router_observation_sha256: str
    verification_seq: int
    verification_sha256: str
    clearance_seq: int
    clearance_sha256: str
    current_head_seq: int
    current_head_sha256: str

    @property
    def proof_sha256(self) -> str:
        return hashlib.sha256(_canonical(asdict(self))).hexdigest()


def _ledger_rows(path: Path) -> list[dict[str, object]]:
    if not path.is_absolute() or path.is_symlink() or not path.is_file():
        raise ContinuationError("ledger is missing or unsafe")
    try:
        with sqlite3.connect(f"file:{path}?mode=ro", uri=True) as db:
            raw = db.execute(
                "SELECT seq,timestamp,prev_hash,row_hash,schema_ver,kind,payload "
                "FROM ledger_rows ORDER BY seq"
            ).fetchall()
        previous = GENESIS_HASH
        rows: list[dict[str, object]] = []
        for expected, item in enumerate(raw, 1):
            seq, timestamp, prev_hash, row_hash, schema_ver, kind, payload_raw = item
            payload = json.loads(payload_raw)
            event = Event(schema_ver, kind, payload)
            if (
                seq != expected
                or isinstance(seq, bool)
                or prev_hash != previous
                or (
                    compute_row_hash(prev_hash, seq, timestamp, event, domain_tag="PRODUCTION") != row_hash
                    and compute_row_hash(prev_hash, seq, timestamp, event, domain_tag=None) != row_hash
                )
                or not isinstance(payload, dict)
            ):
                raise ContinuationError("ledger hash chain is invalid")
            rows.append({
                "seq": seq,
                "timestamp": timestamp,
                "row_hash": row_hash,
                "prev_hash": prev_hash,
                "kind": kind,
                "payload": payload,
            })
            previous = row_hash
        if not rows:
            raise ContinuationError("ledger is empty")
        return rows
    except ContinuationError:
        raise
    except (OSError, sqlite3.Error, json.JSONDecodeError, TypeError, ValueError):
        raise ContinuationError("ledger cannot be validated") from None


def _validate_router_evidence(
    path: Path,
    observation_id: int,
    expected_hash: str,
    *,
    clearance_timestamp: object,
    retrospect_timestamp: object,
) -> None:
    _require_hash(expected_hash, "router observation hash")
    if not path.is_absolute() or path.is_symlink() or not path.is_file():
        raise ContinuationError("durable router evidence is missing or unsafe")
    columns = (
        "id", "timestamp", "task_class", "logical_model", "model_id", "provider_id",
        "family", "latency_ms", "prompt_tokens", "completion_tokens", "success",
        "normalized_error", "failure_scope", "scope_key",
    )
    try:
        with sqlite3.connect(f"file:{path}?mode=ro", uri=True) as db:
            row = db.execute(
                f"SELECT {','.join(columns)} FROM routing_observations WHERE id=?",
                (observation_id,),
            ).fetchone()
    except sqlite3.Error:
        raise ContinuationError("durable router evidence cannot be read") from None
    if row is None or hashlib.sha256(_canonical(list(row))).hexdigest() != expected_hash:
        raise ContinuationError("durable router evidence hash mismatch")
    record = dict(zip(columns, row, strict=True))
    if record["task_class"] not in {"AUDIT", "UNKNOWN"}:
        raise ContinuationError("router evidence task class is invalid")
    if record["success"] != 0:
        raise ContinuationError("router evidence does not record a failure")
    if record["normalized_error"] not in _RESOURCE_ERRORS:
        raise ContinuationError("router evidence is not an evidenced L14 resource exhaustion")
    if not record["provider_id"] or not record["model_id"]:
        raise ContinuationError("router evidence is missing provider or model identity")
    if record["provider_id"] != "google" or record["family"] != "gemini":
        raise ContinuationError("router evidence is not the authorized Gemini route")

    c_epoch = _parse_timestamp(clearance_timestamp)
    r_epoch = _parse_timestamp(retrospect_timestamp)
    obs_epoch = _parse_timestamp(record["timestamp"])
    if not (c_epoch < obs_epoch < r_epoch):
        raise ContinuationError("router observation timestamp is outside clearance-remand window")


def validate_resource_remand_continuation(
    *,
    state_dir: Path,
    candidate: CandidateMaterialization,
    manifest_sha256: str,
    evidence_hashes: tuple[str, ...],
    evidence_tuple_sha256: str,
    evidence_bundle_sha256: str,
    projection_sha256: str,
    binding_sha256: str,
    router_db: Path,
    router_observation_id: int,
    router_observation_sha256: str,
) -> ContinuationProof:
    """Validate preserved exact identity and return a proof; perform no writes."""
    state_dir = state_dir.resolve()
    for value, label in (
        (manifest_sha256, "manifest hash"),
        (evidence_tuple_sha256, "evidence tuple hash"),
        (evidence_bundle_sha256, "evidence bundle hash"),
        (projection_sha256, "projection hash"),
        (binding_sha256, "binding hash"),
        (router_observation_sha256, "router observation hash"),
    ):
        _require_hash(value, label)
    if not evidence_hashes or any(_HEX.fullmatch(item) is None for item in evidence_hashes):
        raise ContinuationError("invalid evidence hashes")
    try:
        verify_candidate_integrity(
            candidate,
            run_id=candidate.run_id,
            cas=CAS(FilesystemCasStore(state_dir / "cas")),
        )
    except Exception as exc:
        raise ContinuationError(f"candidate integrity failed: {type(exc).__name__}") from None

    audit_dir = state_dir / "l14-audits" / candidate.run_id
    projection = audit_dir / "projection.json"
    binding_path = audit_dir / "disclosure-binding.json"
    if _file_hash(projection) != projection_sha256 or _file_hash(binding_path) != binding_sha256:
        raise ContinuationError("original L14 projection or disclosure binding changed")
    try:
        binding = json.loads(binding_path.read_bytes())
    except (OSError, json.JSONDecodeError):
        raise ContinuationError("original disclosure binding is malformed") from None
    required = {
        "run_id": candidate.run_id,
        "candidate_id": candidate.candidate_id,
        "candidate_cas_sha256": candidate.cas_artifact_hash,
        "manifest_sha256": manifest_sha256,
        "l13_evidence_bundle_sha256": evidence_bundle_sha256,
        "evidence_tuple_sha256": evidence_tuple_sha256,
        "projection_file_sha256": projection_sha256,
    }
    if not isinstance(binding, dict) or any(binding.get(k) != v for k, v in required.items()):
        raise ContinuationError("original disclosure binding identity mismatch")
    if any((audit_dir / name).exists() for name in ("receipt.json", "report.md")):
        raise ContinuationError("prior L14 audit artifacts exist")

    rows = _ledger_rows(state_dir / "ledger.db")
    matches: list[tuple[int, dict[str, object], dict[str, object]]] = []
    for index in range(1, len(rows)):
        verification, clearance = rows[index - 1], rows[index]
        vp, cp = verification["payload"], clearance["payload"]
        if (
            verification["kind"] == "L13_VERIFICATION"
            and clearance["kind"] == "L13_COMPLETENESS_CLEARED"
            and clearance["prev_hash"] == verification["row_hash"]
            and isinstance(vp, dict)
            and isinstance(cp, dict)
            and vp.get("run_id") == candidate.run_id
            and vp.get("candidate_id") == candidate.candidate_id
            and vp.get("candidate_sha256") == candidate.cas_artifact_hash
            and vp.get("verdict") == "PASS"
            and vp.get("evidence_hashes") == list(evidence_hashes)
            and cp.get("run_id") == candidate.run_id
            and cp.get("candidate_id") == candidate.candidate_id
            and cp.get("candidate_sha256") == candidate.cas_artifact_hash
            and cp.get("goal_id") == vp.get("goal_id")
            and cp.get("evidence_bundle_sha256") == evidence_bundle_sha256
        ):
            matches.append((index, verification, clearance))
    if len(matches) != 1:
        raise ContinuationError("exact adjacent L13 PASS/clearance pair is absent or ambiguous")
    index, verification, clearance = matches[0]
    prior = rows[: index - 1]
    freezes = [
        r for r in prior
        if r["kind"] == "L11_FREEZE" and r["payload"].get("run_id") == candidate.run_id
    ]
    if (
        len(freezes) != 1
        or freezes[0]["payload"].get("manifest_sha256") != manifest_sha256
        or freezes[0]["payload"].get("plan_sha256") != candidate.l11_binding_sha256
    ):
        raise ContinuationError("original manifest freeze identity mismatch")
    later = rows[index + 1:]
    if len(later) != len(_TERMINAL_LAYERS):
        raise ContinuationError("terminal remand suffix is incomplete or has later mutation")
    for row, layer in zip(later, _TERMINAL_LAYERS, strict=True):
        payload = row["payload"]
        if (
            row["kind"] != "EVOLUTION_EVENT"
            or payload.get("layer") != layer
            or payload.get("run_id") != candidate.run_id
            or payload.get("goal_id") != verification["payload"].get("goal_id")
            or payload.get("status") != "REMANDED"
        ):
            raise ContinuationError("later substantive mutation or nonterminal remand exists")
    retrospect_summary = str(later[0]["payload"].get("summary", ""))
    if _EXPECTED_RETROSPECT_SUBSTRING not in retrospect_summary:
        raise ContinuationError("first terminal evolution event is not an L14 audit remand")
    if any(r["kind"] in _PRIOR_AUDIT_KINDS or r["kind"] in _SEAL_KINDS for r in rows):
        raise ContinuationError("prior audit or seal exists")

    canonical_router_path = (state_dir / "l14-router.sqlite3").resolve()
    if router_db.resolve() != canonical_router_path:
        raise ContinuationError("router database path is not canonical state router DB")

    _validate_router_evidence(
        router_db,
        router_observation_id,
        router_observation_sha256,
        clearance_timestamp=clearance["timestamp"],
        retrospect_timestamp=later[0]["timestamp"],
    )
    head = rows[-1]
    return ContinuationProof(
        schema="paeos.p1-l14-resource-remand-continuation/1",
        run_id=candidate.run_id,
        candidate_id=candidate.candidate_id,
        candidate_sha256=candidate.cas_artifact_hash,
        manifest_sha256=manifest_sha256,
        evidence_tuple_sha256=evidence_tuple_sha256,
        evidence_bundle_sha256=evidence_bundle_sha256,
        projection_sha256=projection_sha256,
        disclosure_binding_sha256=binding_sha256,
        router_observation_sha256=router_observation_sha256,
        verification_seq=int(verification["seq"]),
        verification_sha256=str(verification["row_hash"]),
        clearance_seq=int(clearance["seq"]),
        clearance_sha256=str(clearance["row_hash"]),
        current_head_seq=int(head["seq"]),
        current_head_sha256=str(head["row_hash"]),
    )


def validate_root06_preservation(repo_root: Path) -> ContinuationProof:
    """Validate preserved root06 exact identity against pinned observation anchors."""
    repo_root = repo_root.resolve()
    anchors_file = repo_root / _ROOT06_ANCHORS_RELATIVE_PATH
    if _file_hash(anchors_file) != _ROOT06_ANCHORS_SHA256:
        raise ContinuationError("pinned root06 preservation anchors file hash mismatch")

    try:
        anchors = json.loads(anchors_file.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ContinuationError("root06 preservation anchors file is malformed") from exc

    if not isinstance(anchors, dict) or anchors.get("schema") != "paeos.root06-preservation-observation/1":
        raise ContinuationError("root06 preservation anchors schema is invalid")

    state_dir = (repo_root / anchors["root"]).resolve()
    if not state_dir.is_dir() or state_dir.is_symlink():
        raise ContinuationError("root06 state directory is missing or unsafe")

    cand_meta_path = (state_dir / "candidates" / anchors["candidate_id"] / "candidate.json").resolve()
    if _file_hash(cand_meta_path) != anchors["candidate_metadata_sha256"]:
        raise ContinuationError("candidate metadata hash mismatch with anchors")

    try:
        cand_data = json.loads(cand_meta_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ContinuationError("candidate metadata is malformed") from exc

    candidate = CandidateMaterialization(
        candidate_id=cand_data["candidate_id"],
        run_id=cand_data["run_id"],
        l11_binding_sha256=cand_data["l11_binding_sha256"],
        builder_identity=cand_data["builder_identity"],
        base_revision=cand_data["base_revision"],
        changed_files=tuple(CandidateFile(**f) for f in cand_data["changed_files"]),
        verification_support_files=tuple(CandidateFile(**f) for f in cand_data["verification_support_files"]),
        verification_source_files=tuple(CandidateFile(**f) for f in cand_data["verification_source_files"]),
        tree_sha256=cand_data["tree_sha256"],
        diff_sha256=cand_data["diff_sha256"],
        cas_artifact_hash=cand_data["cas_artifact_hash"],
        workspace_identity=cand_data["workspace_identity"],
        environment_identity=cand_data["environment_identity"],
        created_at=cand_data["created_at"],
        status=CandidateStatus(cand_data["status"]),
        candidate_workspace=(cand_meta_path.parent / "workspace").resolve(),
        metadata_path=cand_meta_path,
    )

    if candidate.cas_artifact_hash != anchors["candidate_cas_sha256"]:
        raise ContinuationError("candidate CAS hash mismatch with anchors")
    if candidate.run_id != anchors["run_id"] or candidate.candidate_id != anchors["candidate_id"]:
        raise ContinuationError("candidate run_id or candidate_id mismatch with anchors")

    proj_path = (state_dir / "l14-audits" / anchors["run_id"] / "projection.json").resolve()
    if _file_hash(proj_path) != anchors["projection_file_sha256"]:
        raise ContinuationError("projection file hash mismatch with anchors")

    try:
        proj_data = json.loads(proj_path.read_text(encoding="utf-8"))
        packet_first_line = proj_data["projection"]["packet"].splitlines()[0]
        data = json.loads(packet_first_line)
        physical_evidence = data["physical_l13_evidence"]
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, KeyError, IndexError) as exc:
        raise ContinuationError("failed to extract physical L13 evidence from projection") from exc

    evidence_tuple_sha256 = hashlib.sha256(_canonical(physical_evidence)).hexdigest()
    evidence_hashes = tuple(item["hash"] for item in physical_evidence)

    binding_path = (state_dir / "l14-audits" / anchors["run_id"] / "disclosure-binding.json").resolve()
    if _file_hash(binding_path) != anchors["disclosure_binding_sha256"]:
        raise ContinuationError("disclosure binding hash mismatch with anchors")

    router_db = (state_dir / "l14-router.sqlite3").resolve()
    columns = (
        "id", "timestamp", "task_class", "logical_model", "model_id", "provider_id",
        "family", "latency_ms", "prompt_tokens", "completion_tokens", "success",
        "normalized_error", "failure_scope", "scope_key",
    )
    try:
        with sqlite3.connect(f"file:{router_db}?mode=ro", uri=True) as db:
            row = db.execute(
                f"SELECT {','.join(columns)} FROM routing_observations WHERE id=1"
            ).fetchone()
    except sqlite3.Error as exc:
        raise ContinuationError("failed to read router observation id 1") from exc

    if row is None:
        raise ContinuationError("router observation id 1 is missing")
    router_obs_sha256 = hashlib.sha256(_canonical(list(row))).hexdigest()

    proof = validate_resource_remand_continuation(
        state_dir=state_dir,
        candidate=candidate,
        manifest_sha256=anchors["manifest_sha256"],
        evidence_hashes=evidence_hashes,
        evidence_tuple_sha256=evidence_tuple_sha256,
        evidence_bundle_sha256=anchors["l13_evidence_bundle_sha256"],
        projection_sha256=anchors["projection_file_sha256"],
        binding_sha256=anchors["disclosure_binding_sha256"],
        router_db=router_db,
        router_observation_id=1,
        router_observation_sha256=router_obs_sha256,
    )

    if (
        proof.verification_seq != anchors["l13_verification_seq"]
        or proof.verification_sha256 != anchors["l13_verification_sha256"]
        or proof.clearance_seq != anchors["clearance_seq"]
        or proof.clearance_sha256 != anchors["clearance_sha256"]
        or proof.current_head_seq != anchors["terminal_head_seq"]
        or proof.current_head_sha256 != anchors["terminal_head_sha256"]
    ):
        raise ContinuationError("validated proof fields mismatch with preservation anchors")

    return proof


def reserve_audit_attempt(
    root: Path,
    proof: ContinuationProof,
    *,
    attempt_id: str,
    state_dir: Path | None = None,
) -> Path:
    """Atomically reserve one fresh immutable attempt directory and metadata file."""
    if not root.is_absolute() or root.is_symlink() or _ID.fullmatch(attempt_id) is None:
        raise ContinuationError("attempt reservation path or identity is unsafe")
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    if root.is_symlink() or not root.is_dir():
        raise ContinuationError("attempt reservation root is unsafe")

    # The proof digest, rather than the caller's label, is the uniqueness key.
    # Thus two controllers cannot reserve the same immutable continuation under different attempt IDs.
    attempt = root / proof.proof_sha256
    try:
        os.mkdir(attempt, 0o700)
    except FileExistsError:
        raise ContinuationError("audit attempt is already reserved") from None

    # TOCTOU prevention: if state_dir is supplied, verify ledger head has not drifted.
    if state_dir is not None:
        state_dir = state_dir.resolve()
        rows = _ledger_rows(state_dir / "ledger.db")
        current_head = rows[-1]
        if (
            int(current_head["seq"]) != proof.current_head_seq
            or str(current_head["row_hash"]) != proof.current_head_sha256
        ):
            try:
                os.rmdir(attempt)
            except OSError:
                pass
            raise ContinuationError("ledger head has advanced since proof was generated")

    metadata = {
        "schema": "paeos.p1-l14-audit-attempt-reservation/1",
        "attempt_id": attempt_id,
        "run_id": proof.run_id,
        "candidate_id": proof.candidate_id,
        "continuation_proof_sha256": proof.proof_sha256,
        "continuation_proof": asdict(proof),
    }
    raw = _canonical(metadata) + b"\n"
    nofollow_flag = getattr(os, "O_NOFOLLOW", 0)
    try:
        fd = os.open(attempt / "attempt.json", os.O_WRONLY | os.O_CREAT | os.O_EXCL | nofollow_flag, 0o600)
        try:
            offset = 0
            while offset < len(raw):
                written = os.write(fd, raw[offset:])
                if written <= 0:
                    raise OSError("short attempt metadata write")
                offset += written
            os.fsync(fd)
        finally:
            os.close(fd)
        parent_fd = os.open(attempt, os.O_RDONLY)
        try:
            os.fsync(parent_fd)
        finally:
            os.close(parent_fd)
    except OSError:
        raise ContinuationError("audit attempt metadata reservation failed") from None
    return attempt
