"""Cline desktop-approval broker for worker admission probes.

Implements file-IPC approval/denial for Cline 3.0.56's desktop tool-approval
protocol. The broker binds to one session, delegates policy to the pure
evaluate_tool_request function, and never duplicates admission logic.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shlex
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any, Protocol

from paeos.model_router.a08_enforcer import derive_family_from_actual_model
from paeos.model_router.catalog import ModelCatalog

from runtime.worker_adapter import (
    ADAPTER_PROTOCOL_VERSION,
    AdapterFailureKind,
    AdapterFailureReceipt,
    SideEffectCertainty,
)
from runtime.worker_admission import (
    AdmissionError,
    AdmissionVerdict,
    PhysicalModelReceipt,
    ProbeContract,
    RawWorkerRun,
    ToolDecisionRecord,
    VerificationReceipt,
    assess_worker_run,
    evaluate_tool_request,
    validate_physical_receipt,
)

_IDENTIFIER_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}\Z")


def _valid_identifier(value: object) -> bool:
    """Return whether an untrusted IPC identifier is one safe path component."""
    return isinstance(value, str) and _IDENTIFIER_RE.fullmatch(value) is not None


class ProcessHandle(Protocol):
    """Minimal process interface for the broker — no subprocess import needed."""

    pid: int

    def poll(self) -> int | None: ...
    def terminate(self) -> None: ...
    def wait(self, timeout: float | None = None) -> int: ...
    def kill(self) -> None: ...


class DesktopApprovalBroker:
    """Cline desktop tool-approval broker.

    Reads request files from the approval directory, evaluates them against
    the probe contract, and writes decision files. Every decision is
    journaled. The broker never executes tools itself.
    """

    def __init__(
        self,
        *,
        contract: ProbeContract,
        approval_dir: Path,
        quarantine_dir: Path,
        journal_path: Path,
        poll_seconds: float = 0.05,
        max_wait_seconds: float = 300.0,
    ) -> None:
        self._contract = contract
        self._approval_dir = approval_dir
        self._quarantine_dir = quarantine_dir
        self._journal_path = journal_path
        self._poll_seconds = poll_seconds
        self._max_wait_seconds = max_wait_seconds
        self._bound_session_id: str | None = None
        self._prior_decisions: list[ToolDecisionRecord] = []
        self.circuit_breaker_fired: bool = False

    def process_request(
        self,
        path: Path,
        process: ProcessHandle | None = None,
    ) -> ToolDecisionRecord:
        """Process a single Cline tool-approval request file.

        Returns a ToolDecisionRecord. On denial, writes the denial decision,
        fires circuit breaker if needed, and terminates the process.
        """
        raw_bytes = path.read_bytes()
        request_hash = hashlib.sha256(raw_bytes).hexdigest()

        # Parse request JSON
        try:
            request_data = json.loads(raw_bytes)
            if not isinstance(request_data, dict):
                raise ValueError("request is not a dict")
        except (json.JSONDecodeError, ValueError):
            # Malformed JSON → quarantine
            self._quarantine(path, raw_bytes)
            decision = ToolDecisionRecord(
                tool_name="<malformed>",
                approved=False,
                reason_code="MALFORMED_JSON",
            )
            self._journal_and_write_decision(
                path,
                request_data={},
                request_hash=request_hash,
                decision=decision,
                tool_call_id="unknown",
                session_id="unknown",
            )
            self._halt_process(process)
            return decision

        session_id = request_data.get("sessionId", "unknown")
        tool_call_id = request_data.get("toolCallId", "unknown")

        if not _valid_identifier(session_id) or not _valid_identifier(tool_call_id):
            decision = ToolDecisionRecord(
                tool_name=str(request_data.get("toolName", "<unknown>")),
                approved=False,
                reason_code="INVALID_IDENTIFIER",
            )
            safe_tool_call = f"invalid-{request_hash[:16]}"
            self._journal_and_write_decision(
                path,
                request_data,
                request_hash,
                decision,
                safe_tool_call,
                "invalid",
            )
            self._halt_process(process)
            return decision

        assert isinstance(session_id, str)
        assert isinstance(tool_call_id, str)

        # Session binding: first well-formed request locks the session ID
        if self._bound_session_id is None:
            self._bound_session_id = session_id
        elif session_id != self._bound_session_id:
            decision = ToolDecisionRecord(
                tool_name=request_data.get("toolName", "<unknown>"),
                approved=False,
                reason_code="SESSION_MISMATCH",
            )
            self.circuit_breaker_fired = True
            self._journal_and_write_decision(
                path,
                request_data,
                request_hash,
                decision,
                tool_call_id,
                session_id,
            )
            if process is not None:
                self._terminate_process(process)
            return decision

        # Check for existing decision file (protocol violation)
        decision_path = self._decision_path(session_id, tool_call_id)
        if decision_path.exists():
            decision = ToolDecisionRecord(
                tool_name=request_data.get("toolName", "<unknown>"),
                approved=False,
                reason_code="DECISION_ALREADY_EXISTS",
            )
            # Do NOT overwrite the existing decision file
            self._journal_entry(
                request_hash=request_hash,
                decision=decision,
                decision_hash="<existing>",
                tool_call_id=tool_call_id,
                session_id=session_id,
            )
            self._halt_process(process)
            return decision

        # Delegate to pure policy evaluator
        decision = evaluate_tool_request(
            self._contract,
            request_data,
            tuple(self._prior_decisions),
        )

        # Write decision and journal
        try:
            self._journal_and_write_decision(
                path,
                request_data,
                request_hash,
                decision,
                tool_call_id,
                session_id,
            )
        except FileExistsError:
            decision = ToolDecisionRecord(
                tool_name=request_data.get("toolName", "<unknown>"),
                approved=False,
                reason_code="DECISION_ALREADY_EXISTS",
            )
            existing_path = self._decision_path(session_id, tool_call_id)
            existing_hash = hashlib.sha256(existing_path.read_bytes()).hexdigest()
            self._journal_entry(
                request_hash=request_hash,
                decision=decision,
                decision_hash=existing_hash,
                tool_call_id=tool_call_id,
                session_id=session_id,
            )
            self._halt_process(process)
            return decision

        # Track decisions for ordering
        self._prior_decisions.append(decision)

        # On denial: fire circuit breaker and terminate
        if not decision.approved:
            self._halt_process(process)

        return decision

    def serve(
        self,
        process: ProcessHandle,
    ) -> tuple[ToolDecisionRecord, ...]:
        """Serve approval requests while the process is alive.

        Returns after the process exits and all discovered requests
        have terminal journal entries.
        """
        decisions: list[ToolDecisionRecord] = []
        seen_requests: set[str] = set()
        deadline = time.monotonic() + self._max_wait_seconds

        while process.poll() is None and not self.circuit_breaker_fired:
            if time.monotonic() >= deadline:
                self._halt_process(process)
                break
            self._approval_dir.mkdir(parents=True, exist_ok=True)
            for req_file in sorted(self._approval_dir.glob("*.request.*.json")):
                if str(req_file) not in seen_requests:
                    seen_requests.add(str(req_file))
                    decision = self.process_request(req_file, process=process)
                    decisions.append(decision)
            time.sleep(self._poll_seconds)

        # Final sweep after process exits
        if self._approval_dir.exists():
            for req_file in sorted(self._approval_dir.glob("*.request.*.json")):
                if str(req_file) not in seen_requests:
                    seen_requests.add(str(req_file))
                    decision = self.process_request(req_file, process=process)
                    decisions.append(decision)

        return tuple(decisions)

    # -------------------------------------------------------------------
    # Private helpers
    # -------------------------------------------------------------------

    def _decision_path(self, session_id: str, tool_call_id: str) -> Path:
        return self._approval_dir / f"{session_id}.decision.{tool_call_id}.json"

    def _quarantine(self, source: Path, raw_bytes: bytes) -> None:
        """Copy malformed request bytes to quarantine directory."""
        self._quarantine_dir.mkdir(parents=True, mode=0o700, exist_ok=True)
        dest = self._quarantine_dir / source.name
        dest.write_bytes(raw_bytes)
        os.chmod(dest, 0o600)

    def _write_decision_file(
        self,
        session_id: str,
        tool_call_id: str,
        decision: ToolDecisionRecord,
    ) -> str:
        """Write decision file atomically. Returns hash of written bytes."""
        self._approval_dir.mkdir(parents=True, mode=0o700, exist_ok=True)
        final_path = self._decision_path(session_id, tool_call_id)

        if decision.approved:
            decision_data: dict[str, Any] = {"approved": True}
        else:
            decision_data = {
                "approved": False,
                "reason": f"PAEOS_{decision.reason_code}",
            }

        decision_bytes = json.dumps(decision_data).encode()
        decision_hash = hashlib.sha256(decision_bytes).hexdigest()

        # Atomic no-replace publish: temp file, fsync, hard-link, unlink temp.
        # os.link fails with FileExistsError if another broker won the race.
        fd, tmp_path = tempfile.mkstemp(
            dir=str(self._approval_dir),
            prefix=".decision_",
            suffix=".tmp",
        )
        try:
            os.write(fd, decision_bytes)
            os.fsync(fd)
            os.fchmod(fd, 0o600)
        finally:
            os.close(fd)

        try:
            os.link(tmp_path, final_path)
        finally:
            os.unlink(tmp_path)

        return decision_hash

    def _journal_entry(
        self,
        *,
        request_hash: str,
        decision: ToolDecisionRecord,
        decision_hash: str,
        tool_call_id: str,
        session_id: str,
    ) -> None:
        """Append a single JSONL journal entry."""
        self._journal_path.parent.mkdir(parents=True, mode=0o700, exist_ok=True)
        entry = {
            "timestamp": time.time(),
            "request_hash": request_hash,
            "decision_hash": decision_hash,
            "approved": decision.approved,
            "reason_code": decision.reason_code,
            "tool_name": decision.tool_name,
            "tool_call_id": tool_call_id,
            "session_id": session_id,
        }
        with self._journal_path.open("a") as f:
            f.write(json.dumps(entry) + "\n")
        os.chmod(self._journal_path, 0o600)

    def _journal_and_write_decision(
        self,
        path: Path,
        request_data: dict[str, Any],
        request_hash: str,
        decision: ToolDecisionRecord,
        tool_call_id: str,
        session_id: str,
    ) -> None:
        """Write decision file and journal entry together."""
        decision_hash = self._write_decision_file(
            session_id,
            tool_call_id,
            decision,
        )
        self._journal_entry(
            request_hash=request_hash,
            decision=decision,
            decision_hash=decision_hash,
            tool_call_id=tool_call_id,
            session_id=session_id,
        )

    def _terminate_process(self, process: ProcessHandle) -> None:
        """Terminate the exact child process. Kill if terminate doesn't work."""
        process.terminate()
        try:
            process.wait(timeout=2.0)
        except (subprocess.TimeoutExpired, TimeoutError, OSError):
            process.kill()

    def _halt_process(self, process: ProcessHandle | None) -> None:
        """Trip the broker breaker and terminate only the bound child, if present."""
        self.circuit_breaker_fired = True
        if process is not None:
            self._terminate_process(process)


_MUTATION_BYTES = b"seeded-mutation\n"


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical_json_hash(value: object) -> str:
    return _sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode())


def _run_verifier(argv: tuple[str, ...], sandbox: Path) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        argv,
        cwd=sandbox,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        shell=False,
        timeout=30,
        check=False,
    )


def run_discriminative_verification(contract: ProbeContract) -> VerificationReceipt:
    """Prove baseline fail, candidate pass, seeded fail, and restored pass."""
    artifact = contract.artifact_path
    candidate_bytes = artifact.read_bytes()
    if candidate_bytes != contract.expected_bytes:
        raise AdmissionError("candidate artifact does not match admitted bytes")

    argv = tuple(shlex.split(contract.verification_command))
    argv_hash = _sha256(json.dumps(argv, separators=(",", ":")).encode())

    try:
        artifact.write_bytes(contract.initial_bytes)
        baseline = _run_verifier(argv, contract.sandbox)
        baseline_hash = _sha256(artifact.read_bytes())

        artifact.write_bytes(candidate_bytes)
        candidate = _run_verifier(argv, contract.sandbox)
        candidate_hash = _sha256(artifact.read_bytes())

        artifact.write_bytes(_MUTATION_BYTES)
        mutation = _run_verifier(argv, contract.sandbox)
        mutation_hash = _sha256(artifact.read_bytes())
    finally:
        artifact.write_bytes(candidate_bytes)
    restored = _run_verifier(argv, contract.sandbox)
    restored_hash = _sha256(artifact.read_bytes())

    return VerificationReceipt(
        argv=argv,
        argv_hash=argv_hash,
        baseline_artifact_hash=baseline_hash,
        baseline_exit_code=baseline.returncode,
        baseline_stdout_hash=_sha256(baseline.stdout),
        baseline_stderr_hash=_sha256(baseline.stderr),
        candidate_artifact_hash=candidate_hash,
        candidate_exit_code=candidate.returncode,
        candidate_stdout_hash=_sha256(candidate.stdout),
        candidate_stderr_hash=_sha256(candidate.stderr),
        mutation_hash=mutation_hash,
        mutation_exit_code=mutation.returncode,
        mutation_stdout_hash=_sha256(mutation.stdout),
        mutation_stderr_hash=_sha256(mutation.stderr),
        artifact_restored_hash=restored_hash,
        restored_exit_code=restored.returncode,
        restored_stdout_hash=_sha256(restored.stdout),
        restored_stderr_hash=_sha256(restored.stderr),
    )


class ClineWorkerTransport:
    """Historical CLI diagnostic transport; never an admission authority."""

    admission_capable = False

    def __init__(self, *, timeout_seconds: int = 300) -> None:
        self._timeout_seconds = timeout_seconds

    def run_probe(self, contract: ProbeContract, evidence_root: Path) -> AdapterFailureReceipt:
        """Reject admission without launching the legacy CLI transport."""

        empty_hash = _sha256(b"")
        return AdapterFailureReceipt(
            protocol_version=ADAPTER_PROTOCOL_VERSION,
            invocation_id=contract.probe_id,
            contract_id=contract.probe_id,
            adapter_failure=AdapterFailureKind.ADAPTER_VERSION_UNQUALIFIED,
            normalized_error=None,
            additional_findings=(),
            side_effect_certainty=SideEffectCertainty.NOT_DISPATCHED,
            raw_stdout_sha256=empty_hash,
            raw_stderr_sha256=empty_hash,
            observation_sha256=empty_hash,
        )

    def run_diagnostic_probe(self, contract: ProbeContract, evidence_root: Path) -> RawWorkerRun:
        """Retain the old CLI path solely for bounded diagnostic reproduction."""
        cline_path = shutil.which("cline")
        if cline_path is None:
            raise FileNotFoundError("cline binary not found")

        self._prepare_probe(contract, evidence_root)
        approval_dir = evidence_root / "approvals"
        cline_data_dir = evidence_root / "cline-data"
        stdout_path = evidence_root / "stdout.raw"
        stderr_path = evidence_root / "stderr.raw"
        prompt = self._prompt(contract)
        argv = [
            cline_path,
            "-P",
            contract.provider_id,
            "-m",
            contract.model_id,
            "--json",
            "--auto-approve",
            "false",
            "--retries",
            "1",
            "--thinking",
            "medium",
            "-t",
            str(self._timeout_seconds),
            "-c",
            str(contract.sandbox),
            "--data-dir",
            str(cline_data_dir),
            prompt,
        ]
        env = os.environ.copy()
        env.update(
            {
                "CLINE_TOOL_APPROVAL_MODE": "desktop",
                "CLINE_TOOL_APPROVAL_DIR": str(approval_dir),
                "CLINE_SANDBOX": "1",
            }
        )
        broker = DesktopApprovalBroker(
            contract=contract,
            approval_dir=approval_dir,
            quarantine_dir=evidence_root / "quarantine",
            journal_path=evidence_root / "journal.jsonl",
            max_wait_seconds=float(self._timeout_seconds),
        )

        with stdout_path.open("wb") as stdout_file, stderr_path.open("wb") as stderr_file:
            os.chmod(stdout_path, 0o600)
            os.chmod(stderr_path, 0o600)
            process = subprocess.Popen(
                argv,
                cwd=contract.sandbox,
                stdin=subprocess.DEVNULL,
                stdout=stdout_file,
                stderr=stderr_file,
                env=env,
                start_new_session=True,
            )
            decisions = broker.serve(process)
            try:
                process.wait(timeout=self._timeout_seconds)
            except subprocess.TimeoutExpired as error:
                broker._halt_process(process)
                raise AdmissionError("Cline process timeout") from error

        stdout_bytes = stdout_path.read_bytes()
        stderr_bytes = stderr_path.read_bytes()
        if process.returncode != 0:
            raise AdmissionError(f"CLI exit was {process.returncode}")

        run_result = self._last_run_result(stdout_bytes)
        if run_result.get("finishReason") != "completed":
            raise AdmissionError("finishReason was not completed")

        model = run_result.get("model")
        if not isinstance(model, dict):
            raise AdmissionError("run_result model is missing")
        actual_provider = model.get("provider")
        actual_model = model.get("id")
        if not isinstance(actual_provider, str) or not isinstance(actual_model, str):
            raise AdmissionError("run_result model identity is malformed")

        manifest_path, manifest = self._load_manifest(cline_data_dir)
        messages_path, messages = self._load_messages(manifest_path, manifest, cline_data_dir)
        session_id = self._validate_manifest(manifest, contract, process.pid, messages)
        message_models, tool_uses = self._message_evidence(messages, actual_provider)
        self._correlate_tool_uses(
            tool_uses,
            evidence_root / "journal.jsonl",
            approval_dir,
        )

        binary_hash = _sha256(Path(cline_path).read_bytes())
        receipt = PhysicalModelReceipt(
            transport_id=f"headless:cline-cli:{binary_hash}",
            session_id=session_id,
            pid=process.pid,
            configured_provider_id=contract.provider_id,
            configured_model_id=contract.model_id,
            actual_provider_id=actual_provider,
            actual_model_id=actual_model,
            actual_family=derive_family_from_actual_model(actual_model, ModelCatalog()),
            manifest_provider_id=str(manifest["provider"]),
            manifest_model_id=str(manifest["model"]),
            message_models=message_models,
            argv_hash=_sha256(json.dumps(argv, separators=(",", ":")).encode()),
            stdout_hash=_sha256(stdout_bytes),
            stderr_hash=_sha256(stderr_bytes),
            manifest_hash=_sha256(manifest_path.read_bytes()),
            messages_hash=_sha256(messages_path.read_bytes()),
        )
        validate_physical_receipt(receipt, contract)

        verification = run_discriminative_verification(contract)
        artifact_bytes = contract.artifact_path.read_bytes()
        run = RawWorkerRun(
            probe_id=contract.probe_id,
            receipt=receipt,
            tool_decisions=decisions,
            artifact_name=contract.artifact_name,
            artifact_hash=_sha256(artifact_bytes),
            artifact_size=len(artifact_bytes),
            verification=verification,
        )
        assessment = assess_worker_run(contract, run)
        if assessment.verdict is not AdmissionVerdict.ADMITTED:
            raise AdmissionError("worker run rejected: " + "; ".join(assessment.reasons))
        return run

    @staticmethod
    def _prepare_probe(contract: ProbeContract, evidence_root: Path) -> None:
        if evidence_root.exists():
            if not evidence_root.is_dir() or any(evidence_root.iterdir()):
                raise AdmissionError("evidence root must be a fresh empty directory")
        else:
            evidence_root.mkdir(parents=True, mode=0o700)
        os.chmod(evidence_root, 0o700)
        contract.sandbox.mkdir(parents=True, mode=0o700, exist_ok=True)
        os.chmod(contract.sandbox, 0o700)
        contract.artifact_path.write_bytes(contract.initial_bytes)
        (contract.sandbox / "verify_probe.py").write_text(
            "import sys\n"
            f"expected = {contract.expected_bytes!r}\n"
            f"actual = open({contract.artifact_name!r}, 'rb').read()\n"
            "sys.exit(0 if actual == expected else 1)\n"
        )

    @staticmethod
    def _prompt(contract: ProbeContract) -> str:
        return (
            "You are an implementation-only admission probe in a disposable sandbox.\n"
            "Perform exactly two tool calls in this order and no others.\n"
            f"1. Use editor on {contract.artifact_path}, replacing exactly "
            f"{contract.initial_bytes.decode()!r} with exactly "
            f"{contract.expected_bytes.decode()!r}.\n"
            f"2. Use run_commands with exactly one command: {contract.verification_command}\n"
            "Do not read, search, list, inspect, spawn, delegate, call a skill, add shell "
            "syntax, or run any other command. End after the exact verification result."
        )

    @staticmethod
    def _last_run_result(stdout_bytes: bytes) -> dict[str, Any]:
        result: dict[str, Any] | None = None
        for raw_line in stdout_bytes.splitlines():
            try:
                candidate = json.loads(raw_line)
            except (UnicodeDecodeError, json.JSONDecodeError):
                continue
            if isinstance(candidate, dict) and candidate.get("type") == "run_result":
                result = candidate
        if result is None:
            raise AdmissionError("missing terminal run_result")
        return result

    @staticmethod
    def _load_manifest(cline_data_dir: Path) -> tuple[Path, dict[str, Any]]:
        manifests = [
            path
            for path in cline_data_dir.glob("sessions/*/*.json")
            if not path.name.endswith((".messages.json", ".compaction.json"))
        ]
        if len(manifests) != 1:
            raise AdmissionError(f"expected exactly one manifest, found {len(manifests)}")
        path = manifests[0]
        try:
            value = json.loads(path.read_bytes())
        except (OSError, json.JSONDecodeError) as error:
            raise AdmissionError("manifest is malformed") from error
        if not isinstance(value, dict):
            raise AdmissionError("manifest is not an object")
        return path, value

    @staticmethod
    def _load_messages(
        manifest_path: Path,
        manifest: dict[str, Any],
        cline_data_dir: Path,
    ) -> tuple[Path, dict[str, Any]]:
        raw_path = manifest.get("messages_path")
        if not isinstance(raw_path, str):
            raise AdmissionError("manifest messages_path is missing")
        path = Path(raw_path).resolve()
        if not path.is_relative_to(cline_data_dir.resolve()):
            raise AdmissionError("messages_path escapes isolated Cline data")
        expected = manifest_path.with_name(f"{manifest_path.stem}.messages.json").resolve()
        if path != expected:
            raise AdmissionError("messages_path does not match session manifest")
        try:
            value = json.loads(path.read_bytes())
        except (OSError, json.JSONDecodeError) as error:
            raise AdmissionError("messages archive is malformed") from error
        if not isinstance(value, dict):
            raise AdmissionError("messages archive is not an object")
        return path, value

    @staticmethod
    def _validate_manifest(
        manifest: dict[str, Any],
        contract: ProbeContract,
        pid: int,
        messages: dict[str, Any],
    ) -> str:
        session_id = manifest.get("session_id")
        if not _valid_identifier(session_id):
            raise AdmissionError("manifest session_id is invalid")
        expected = {
            "source": "cli",
            "pid": pid,
            "exit_code": 0,
            "status": "completed",
            "interactive": False,
            "provider": contract.provider_id,
            "model": contract.model_id,
            "cwd": str(contract.sandbox),
            "workspace_root": str(contract.sandbox),
            "enable_tools": True,
            "enable_spawn": False,
            "enable_teams": False,
        }
        for key, value in expected.items():
            if manifest.get(key) != value:
                raise AdmissionError(f"manifest {key} mismatch")
        if messages.get("sessionId") != session_id:
            raise AdmissionError("messages session mismatch")
        assert isinstance(session_id, str)
        return session_id

    @staticmethod
    def _message_evidence(
        messages: dict[str, Any],
        actual_provider: str,
    ) -> tuple[tuple[str, ...], tuple[tuple[str, str, str], ...]]:
        rows = messages.get("messages")
        if not isinstance(rows, list):
            raise AdmissionError("messages array is missing")
        models: list[str] = []
        tool_uses: list[tuple[str, str, str]] = []
        for row in rows:
            if not isinstance(row, dict) or row.get("role") != "assistant":
                continue
            model_info = row.get("modelInfo")
            if not isinstance(model_info, dict):
                raise AdmissionError("assistant modelInfo is missing")
            message_provider, message_model = (
                model_info.get("provider"),
                model_info.get("id"),
            )
            if message_provider != actual_provider:
                raise AdmissionError("provider mismatch: assistant message")
            if not isinstance(message_model, str):
                raise AdmissionError("assistant modelInfo is malformed")
            models.append(message_model)
            content = row.get("content")
            if not isinstance(content, list):
                continue
            for item in content:
                if not isinstance(item, dict) or item.get("type") != "tool_use":
                    continue
                call_id, name = item.get("id"), item.get("name")
                if not isinstance(call_id, str) or not isinstance(name, str):
                    raise AdmissionError("tool-use record is malformed")
                tool_uses.append((call_id, name, _canonical_json_hash(item.get("input"))))
        if not models:
            raise AdmissionError("assistant modelInfo is missing")
        return tuple(models), tuple(tool_uses)

    @staticmethod
    def _correlate_tool_uses(
        tool_uses: tuple[tuple[str, str, str], ...],
        journal_path: Path,
        approval_dir: Path,
    ) -> None:
        try:
            rows = [json.loads(line) for line in journal_path.read_text().splitlines()]
        except (OSError, json.JSONDecodeError) as error:
            raise AdmissionError("approval journal is malformed") from error
        journal_uses: list[tuple[str, str, str]] = []
        for row in rows:
            if not isinstance(row, dict):
                raise AdmissionError("approval journal row is malformed")
            session_id = row.get("session_id")
            call_id = row.get("tool_call_id")
            tool_name = row.get("tool_name")
            request_hash = row.get("request_hash")
            if (
                not _valid_identifier(session_id)
                or not _valid_identifier(call_id)
                or not isinstance(tool_name, str)
                or not isinstance(request_hash, str)
            ):
                raise AdmissionError("approval journal identity is malformed")
            assert isinstance(session_id, str)
            assert isinstance(call_id, str)
            request_path = approval_dir / f"{session_id}.request.{call_id}.json"
            try:
                raw_request = request_path.read_bytes()
                request = json.loads(raw_request)
            except (OSError, json.JSONDecodeError) as error:
                raise AdmissionError("approval request evidence is malformed") from error
            if _sha256(raw_request) != request_hash or not isinstance(request, dict):
                raise AdmissionError("approval request hash mismatch")
            if (
                request.get("sessionId") != session_id
                or request.get("toolCallId") != call_id
                or request.get("toolName") != tool_name
            ):
                raise AdmissionError("approval request identity mismatch")
            journal_uses.append((call_id, tool_name, _canonical_json_hash(request.get("input"))))
        if tuple(journal_uses) != tool_uses:
            raise AdmissionError("tool-use mismatch with approval journal")
