"""Fail-closed admission adapter for the qualified public Cline SDK surface."""

from __future__ import annotations

import hashlib
import json
import os
import re
import select
import shlex
import subprocess
import time
from contextlib import suppress
from contextvars import ContextVar
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import BinaryIO, cast

from paeos.model_router.a08_enforcer import derive_family_from_actual_model
from paeos.model_router.catalog import ModelCatalog
from paeos.model_router.types import NormalizedErrorType

from runtime.integrations.cline_sdk_protocol import (
    PROTOCOL_VERSION,
    HostEventMachine,
    ProtocolError,
    encode_frame,
    read_frame,
)
from runtime.integrations.cline_sdk_qualification import (
    SDK_QUALIFICATION_SCHEMA,
    AdapterQualificationRecord,
)
from runtime.integrations.cline_worker import run_discriminative_verification
from runtime.worker_adapter import (
    ADAPTER_PROTOCOL_VERSION,
    AdapterFailureKind,
    AdapterFailureReceipt,
    AdmissionProbeTransport,
    SideEffectCertainty,
)
from runtime.worker_admission import (
    AdmissionError,
    AdmissionVerdict,
    PhysicalModelReceipt,
    ProbeContract,
    RawWorkerRun,
    ToolDecisionRecord,
    assess_worker_run,
    evaluate_tool_request,
    validate_physical_receipt,
)
from runtime.worker_profile import (
    AuthenticatedProfileHandle,
    ProfileLease,
    ProfileLeaseError,
)

_CAPABILITIES = {
    "backend_mode": "local",
    "disable_mcp_settings_tools": True,
    "enable_agent_teams": False,
    "enable_spawn_agent": False,
    "enabled_tools": ["editor", "run_commands"],
}


class _ProbeFailure(AdmissionError):
    def __init__(self, message: str, raw_stdout: bytes, raw_stderr: bytes) -> None:
        self.raw_stdout = raw_stdout
        self.raw_stderr = raw_stderr
        super().__init__(message)


_FAILURE_EVIDENCE: ContextVar[tuple[bytes, bytes]] = ContextVar(
    "cline_sdk_failure_evidence", default=(b"", b"")
)

_AUTH_FAILURE_RE = re.compile(
    r"\b(?:AUTH_FAILED|UNAUTHORIZED|UNAUTHORISED|AUTHENTICATION FAILED|RE-?AUTHENTICATE)\b"
)


def _sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha_file(path: Path) -> str:
    return _sha_bytes(path.read_bytes())


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()


@dataclass(frozen=True, slots=True)
class ClineSdkAdapterConfig:
    node_executable: Path
    host_module: Path
    qualification: AdapterQualificationRecord
    profile: AuthenticatedProfileHandle
    timeout_seconds: float
    lease_root: Path
    process_start_token: str
    boot_id: str


class ClineSdkAdmissionAdapter(AdmissionProbeTransport):
    """Run one no-retry, local-backend admission probe through public SDK APIs."""

    def __init__(self, config: ClineSdkAdapterConfig) -> None:
        self._config = config
        self._active_lease: ProfileLease | None = None

    def run_probe(self, contract: ProbeContract) -> RawWorkerRun | AdapterFailureReceipt:
        try:
            return self._run_probe(contract)
        except ProfileLeaseError as error:
            empty_hash = _sha_bytes(b"")
            return AdapterFailureReceipt(
                protocol_version=ADAPTER_PROTOCOL_VERSION,
                invocation_id=contract.probe_id,
                contract_id=contract.probe_id,
                adapter_failure=error.kind,
                normalized_error=None,
                additional_findings=(),
                side_effect_certainty=SideEffectCertainty.NOT_DISPATCHED,
                raw_stdout_sha256=empty_hash,
                raw_stderr_sha256=empty_hash,
                observation_sha256=_sha_bytes(empty_hash.encode() * 2),
            )
        except (AdmissionError, ProtocolError) as error:
            message = str(error)
            raw_stdout, raw_stderr = _FAILURE_EVIDENCE.get()
            failure_stdout = getattr(error, "raw_stdout", raw_stdout)
            failure_stderr = getattr(error, "raw_stderr", raw_stderr)
            self._release_failed_lease(
                contract,
                message=message,
                stdout=failure_stdout,
                stderr=failure_stderr,
            )
            failure_text = "\n".join(
                (
                    message,
                    failure_stderr.decode("utf-8", errors="replace"),
                )
            ).upper()
            normalized_error: NormalizedErrorType | None = None
            if _AUTH_FAILURE_RE.search(failure_text):
                kind = None
                normalized_error = NormalizedErrorType.AUTH_FAILED
                certainty = SideEffectCertainty.PROVIDER_ACCEPTED
            elif "tool denied" in message:
                kind = AdapterFailureKind.TOOL_DENIED
                certainty = SideEffectCertainty.PROVIDER_ACCEPTED
            elif "command expansion" in message:
                kind = AdapterFailureKind.COMMAND_EXPANSION
                certainty = SideEffectCertainty.TOOL_EFFECT_POSSIBLE
            elif "timeout" in message:
                kind = AdapterFailureKind.SIDE_EFFECT_UNCERTAIN
                certainty = SideEffectCertainty.UNKNOWN
            elif "qualification" in message:
                kind = AdapterFailureKind.ADAPTER_VERSION_UNQUALIFIED
                certainty = SideEffectCertainty.NOT_DISPATCHED
            elif "manifest provider" in message or "manifest model" in message:
                kind = AdapterFailureKind.MODEL_MISMATCH
                certainty = SideEffectCertainty.TOOL_EFFECT_POSSIBLE
            elif "manifest session" in message:
                kind = AdapterFailureKind.SESSION_AMBIGUOUS
                certainty = SideEffectCertainty.TOOL_EFFECT_POSSIBLE
            elif "manifest capabilities" in message or "manifest backend" in message:
                kind = AdapterFailureKind.CAPABILITY_DRIFT
                certainty = SideEffectCertainty.TOOL_EFFECT_POSSIBLE
            else:
                kind = AdapterFailureKind.TRANSPORT_FAILED
                certainty = SideEffectCertainty.UNKNOWN
            stdout_hash = _sha_bytes(failure_stdout)
            stderr_hash = _sha_bytes(failure_stderr)
            return AdapterFailureReceipt(
                protocol_version=ADAPTER_PROTOCOL_VERSION,
                invocation_id=contract.probe_id,
                contract_id=contract.probe_id,
                adapter_failure=kind,
                normalized_error=normalized_error,
                additional_findings=(),
                side_effect_certainty=certainty,
                raw_stdout_sha256=stdout_hash,
                raw_stderr_sha256=stderr_hash,
                observation_sha256=_sha_bytes(stdout_hash.encode() + stderr_hash.encode()),
            )

    def _release_failed_lease(
        self,
        contract: ProbeContract,
        *,
        message: str,
        stdout: bytes,
        stderr: bytes,
    ) -> None:
        lease = self._active_lease
        if lease is None:
            return
        evidence = lease.lease_root / f"{contract.probe_id}.failure.json"
        payload = _canonical_bytes(
            {
                "invocation_id": contract.probe_id,
                "status": "failed",
                "reason": message,
                "stdout_sha256": _sha_bytes(stdout),
                "stderr_sha256": _sha_bytes(stderr),
            }
        ) + b"\n"
        descriptor = os.open(evidence, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        try:
            os.write(descriptor, payload)
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
        lease.release(evidence)
        self._active_lease = None

    def _run_probe(self, contract: ProbeContract) -> RawWorkerRun:
        _FAILURE_EVIDENCE.set((b"", b""))
        self._validate_qualification()
        self._prepare_probe(contract)
        invocation_id = contract.probe_id
        session_id = f"{contract.probe_id}-session"
        lease = ProfileLease.acquire(
            self._config.profile,
            invocation_id=invocation_id,
            lease_root=self._config.lease_root,
            forbidden_roots=(contract.sandbox,),
            process_start_token=self._config.process_start_token,
            boot_id=self._config.boot_id,
        )
        self._active_lease = lease
        argv = [str(self._config.node_executable), str(self._config.host_module)]
        env = {
            "CLINE_DATA_DIR": str(self._config.profile.root),
            "LANG": "C.UTF-8",
            "PATH": "/usr/bin:/bin:/usr/sbin:/sbin:/opt/homebrew/bin",
        }
        process = subprocess.Popen(
            argv,
            cwd=contract.sandbox,
            env=env,
            shell=False,
            start_new_session=True,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        assert process.stdin is not None
        assert process.stdout is not None
        assert process.stderr is not None
        prompt = "PAEOS_SDK_PROBE:" + json.dumps(
            {
                "artifact_path": str(contract.artifact_path),
                "expected_text": contract.expected_bytes.decode(),
                "initial_text": contract.initial_bytes.decode(),
                "probe_id": contract.probe_id,
                "verification_command": contract.verification_command,
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        start = {
            "invocation_id": invocation_id,
            "payload": {
                "backend_mode": "local",
                "core_entrypoint": self._config.qualification.core_entrypoint,
                "core_sha256": _sha_file(Path(self._config.qualification.core_entrypoint)),
                "cwd": str(contract.sandbox),
                "max_declared_model_turns": 2,
                "model_id": contract.model_id,
                "prompt": prompt,
                "provider_id": contract.provider_id,
                "sdk_entrypoint": self._config.qualification.sdk_entrypoint,
                "sdk_sha256": _sha_file(Path(self._config.qualification.sdk_entrypoint)),
                "session_id": session_id,
            },
            "protocol_version": PROTOCOL_VERSION,
            "sequence": 0,
            "type": "start",
        }
        start_bytes = encode_frame(start)
        process.stdin.write(start_bytes)
        process.stdin.flush()

        deadline = time.monotonic() + self._config.timeout_seconds
        machine = HostEventMachine(invocation_id)
        raw_stdout = bytearray()
        decisions: list[ToolDecisionRecord] = []
        attempts: dict[str, int] = {}
        capability_snapshot: dict[str, object] | None = None
        manifest_path: Path | None = None
        messages_path: Path | None = None
        terminal_payload: dict[str, object] | None = None
        command_sequence = 1
        while not machine.terminal:
            try:
                event = self._read_event(cast(BinaryIO, process.stdout), deadline)
            except (AdmissionError, ProtocolError) as error:
                stderr_bytes = self._cancel_and_stop(
                    process, invocation_id, session_id, command_sequence
                )
                message = (
                    f"SDK protocol failure: {error}"
                    if isinstance(error, ProtocolError)
                    else str(error)
                )
                raise _ProbeFailure(message, bytes(raw_stdout), stderr_bytes) from error
            raw_stdout.extend(encode_frame(event))
            try:
                machine.accept(event)
            except ProtocolError as error:
                stderr_bytes = self._cancel_and_stop(
                    process, invocation_id, session_id, command_sequence
                )
                raise _ProbeFailure(
                    f"SDK protocol failure: {error}", bytes(raw_stdout), stderr_bytes
                ) from error
            event_type = event["type"]
            payload = event["payload"]
            assert isinstance(payload, dict)
            if event_type == "session_created":
                manifest_path = self._profile_path(payload.get("manifest_path"))
                messages_path = self._profile_path(payload.get("messages_path"))
            elif event_type == "capability_snapshot":
                capability_snapshot = payload
            elif event_type == "provider_attempt_started":
                turn_id = payload.get("turn_id")
                if not isinstance(turn_id, str):
                    raise AdmissionError("provider attempt missing turn")
                attempts[turn_id] = attempts.get(turn_id, 0) + 1
            elif event_type == "tool_request":
                decision = evaluate_tool_request(
                    contract,
                    {"toolName": payload.get("tool_name"), "input": payload.get("input")},
                    tuple(decisions),
                )
                decisions.append(decision)
                if not decision.approved:
                    stderr_bytes = self._cancel_and_stop(
                        process, invocation_id, session_id, command_sequence
                    )
                    if (
                        decision.tool_name == "run_commands"
                        and decision.reason_code == "COMMAND_MISMATCH"
                    ):
                        raise _ProbeFailure(
                            "SDK command expansion denied", bytes(raw_stdout), stderr_bytes
                        )
                    raise _ProbeFailure(
                        f"SDK tool denied: {decision.reason_code}",
                        bytes(raw_stdout),
                        stderr_bytes,
                    )
                result = self._execute_tool(contract, payload, decision)
                response = {
                    "invocation_id": invocation_id,
                    "payload": {
                        "approved": True,
                        "call_id": payload["call_id"],
                        "result": result,
                    },
                    "protocol_version": PROTOCOL_VERSION,
                    "sequence": command_sequence,
                    "session_id": session_id,
                    "type": "tool_response",
                }
                command_sequence += 1
                process.stdin.write(encode_frame(response))
                process.stdin.flush()
            elif event_type == "terminal":
                terminal_payload = payload
            elif event_type in {"failure", "cancelled"}:
                try:
                    process.wait(timeout=1)
                except subprocess.TimeoutExpired:
                    process.terminate()
                    process.wait(timeout=1)
                stderr_bytes = process.stderr.read()
                if payload.get("normalized_error") == "AUTH_FAILED":
                    raise _ProbeFailure("SDK AUTH_FAILED", bytes(raw_stdout), stderr_bytes)
                error_class = payload.get("error_class")
                suffix = f" ({error_class})" if isinstance(error_class, str) else ""
                raise _ProbeFailure(
                    f"SDK terminal failure: {event_type}{suffix}",
                    bytes(raw_stdout),
                    stderr_bytes,
                )

        process.stdin.close()
        process.wait(timeout=max(0.1, deadline - time.monotonic()))
        stderr_bytes = process.stderr.read()
        _FAILURE_EVIDENCE.set((bytes(raw_stdout), stderr_bytes))
        if process.returncode != 0:
            raise AdmissionError(f"SDK host exit was {process.returncode}")
        if capability_snapshot != _CAPABILITIES:
            raise AdmissionError("SDK capability snapshot mismatch")
        assert capability_snapshot is not None
        if attempts != {"turn-1": 1, "turn-2": 1}:
            raise AdmissionError("provider attempt telemetry mismatch")
        if manifest_path is None or messages_path is None or terminal_payload is None:
            raise AdmissionError("SDK evidence incomplete")

        manifest = self._load_json_object(manifest_path)
        messages = self._load_json_object(messages_path)
        self._validate_profile_evidence(
            manifest,
            messages,
            contract,
            session_id,
            messages_path,
            capability_snapshot,
        )
        terminal_result = terminal_payload.get("result")
        if not isinstance(terminal_result, dict):
            raise AdmissionError("SDK terminal result missing")
        actual = terminal_result.get("model")
        if not isinstance(actual, dict):
            raise AdmissionError("SDK terminal model missing")
        actual_provider = actual.get("provider")
        actual_model = actual.get("id")
        if not isinstance(actual_provider, str) or not isinstance(actual_model, str):
            raise AdmissionError("SDK terminal model malformed")

        message_models = self._message_models(messages, actual_provider)
        receipt = PhysicalModelReceipt(
            transport_id=(
                f"headless:cline-sdk:{self._config.qualification.record_sha256}:"
                f"{_sha_file(self._config.host_module)}"
            ),
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
            argv_hash=_sha_bytes(_canonical_bytes(argv)),
            stdout_hash=_sha_bytes(bytes(raw_stdout)),
            stderr_hash=_sha_bytes(stderr_bytes),
            manifest_hash=_sha_file(manifest_path),
            messages_hash=_sha_file(messages_path),
        )
        validate_physical_receipt(receipt, contract)
        verification = run_discriminative_verification(contract)
        artifact = contract.artifact_path.read_bytes()
        run = RawWorkerRun(
            probe_id=contract.probe_id,
            receipt=receipt,
            tool_decisions=tuple(decisions),
            artifact_name=contract.artifact_name,
            artifact_hash=_sha_bytes(artifact),
            artifact_size=len(artifact),
            verification=verification,
        )
        assessment = assess_worker_run(contract, run)
        if assessment.verdict is not AdmissionVerdict.ADMITTED:
            raise AdmissionError("SDK worker run rejected: " + "; ".join(assessment.reasons))
        terminal_record = self._config.lease_root / f"{invocation_id}.terminal.json"
        descriptor = os.open(terminal_record, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        try:
            os.write(descriptor, _canonical_bytes({"receipt": receipt.receipt_hash}) + b"\n")
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
        lease.release(terminal_record)
        self._active_lease = None
        return run

    def _validate_qualification(self) -> None:
        record = self._config.qualification
        payload = asdict(record)
        payload.pop("record_sha256")
        expected_record_hash = _sha_bytes(_canonical_bytes(payload))
        if (
            record.schema != SDK_QUALIFICATION_SCHEMA
            or record.record_sha256 != expected_record_hash
        ):
            raise AdmissionError("SDK qualification record invalid")
        package_root = Path(record.package_root)
        if not package_root.is_absolute() or not record.files:
            raise AdmissionError("SDK qualification package invalid")
        try:
            package_root = package_root.resolve(strict=True)
        except OSError as error:
            raise AdmissionError("SDK qualification package invalid") from error
        qualified_paths: set[Path] = set()
        for qualified_file in record.files:
            relative = Path(qualified_file.relative_path)
            if relative.is_absolute() or ".." in relative.parts:
                raise AdmissionError("SDK qualification file escaped")
            try:
                qualified_path = (package_root / relative).resolve(strict=True)
            except OSError as error:
                raise AdmissionError("SDK qualification file missing") from error
            if (
                not qualified_path.is_file()
                or not qualified_path.is_relative_to(package_root)
                or qualified_path.stat().st_size != qualified_file.byte_count
                or _sha_file(qualified_path) != qualified_file.sha256
            ):
                raise AdmissionError("SDK qualification file changed")
            qualified_paths.add(qualified_path)
        if not {
            Path(record.sdk_entrypoint).resolve(strict=True),
            Path(record.core_entrypoint).resolve(strict=True),
        }.issubset(qualified_paths):
            raise AdmissionError("SDK qualification entrypoint not in closure")
        checks = (
            (self._config.node_executable, record.node_executable, record.node_sha256),
            (
                Path(record.sdk_entrypoint),
                record.sdk_entrypoint,
                _sha_file(Path(record.sdk_entrypoint)),
            ),
            (
                Path(record.core_entrypoint),
                record.core_entrypoint,
                _sha_file(Path(record.core_entrypoint)),
            ),
        )
        for path, qualified_path, expected_hash in checks:
            if (
                not path.is_absolute()
                or str(path) != qualified_path
                or _sha_file(path) != expected_hash
            ):
                raise AdmissionError("SDK qualification tuple changed")
        if not self._config.host_module.is_absolute() or not self._config.host_module.is_file():
            raise AdmissionError("SDK host module invalid")

    @staticmethod
    def _prepare_probe(contract: ProbeContract) -> None:
        if not contract.sandbox.is_absolute() or contract.sandbox.exists():
            raise AdmissionError("probe sandbox must be fresh, absent, and absolute")
        contract.sandbox.mkdir(mode=0o700, parents=True)
        contract.artifact_path.write_bytes(contract.initial_bytes)
        (contract.sandbox / "verify_probe.py").write_text(
            "import sys\n"
            f"expected = {contract.expected_bytes!r}\n"
            f"actual = open({contract.artifact_name!r}, 'rb').read()\n"
            "sys.exit(0 if actual == expected else 1)\n"
        )

    @staticmethod
    def _read_event(stream: BinaryIO, deadline: float) -> dict[str, object]:
        remaining = deadline - time.monotonic()
        if remaining <= 0 or not select.select([stream], [], [], remaining)[0]:
            raise AdmissionError("SDK probe timeout")
        return read_frame(stream)

    @staticmethod
    def _send_cancel(stream: BinaryIO, invocation_id: str, session_id: str, sequence: int) -> None:
        stream.write(
            encode_frame(
                {
                    "invocation_id": invocation_id,
                    "payload": {},
                    "protocol_version": PROTOCOL_VERSION,
                    "sequence": sequence,
                    "session_id": session_id,
                    "type": "cancel",
                }
            )
        )
        stream.flush()

    @classmethod
    def _cancel_and_stop(
        cls,
        process: subprocess.Popen[bytes],
        invocation_id: str,
        session_id: str,
        sequence: int,
    ) -> bytes:
        assert process.stdin is not None
        assert process.stderr is not None
        with suppress(BrokenPipeError, OSError):
            cls._send_cancel(cast(BinaryIO, process.stdin), invocation_id, session_id, sequence)
        try:
            process.wait(timeout=0.1)
        except subprocess.TimeoutExpired:
            process.terminate()
            try:
                process.wait(timeout=1)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=1)
        with suppress(BrokenPipeError, OSError):
            process.stdin.close()
        return process.stderr.read()

    @staticmethod
    def _execute_tool(
        contract: ProbeContract,
        payload: dict[str, object],
        decision: ToolDecisionRecord,
    ) -> dict[str, object]:
        tool_input = payload.get("input")
        assert isinstance(tool_input, dict)
        if decision.tool_name == "editor":
            if contract.artifact_path.read_bytes() != contract.initial_bytes:
                raise AdmissionError("probe artifact initial bytes changed")
            contract.artifact_path.write_bytes(contract.expected_bytes)
            return {"bytes_written": len(contract.expected_bytes)}
        argv = shlex.split(contract.verification_command)
        completed = subprocess.run(
            argv,
            cwd=contract.sandbox,
            env={"LANG": "C.UTF-8", "PATH": "/usr/bin:/bin:/usr/sbin:/sbin:/opt/homebrew/bin"},
            shell=False,
            capture_output=True,
            check=False,
            timeout=30,
        )
        return {
            "exit_code": completed.returncode,
            "stderr_sha256": _sha_bytes(completed.stderr),
            "stdout_sha256": _sha_bytes(completed.stdout),
        }

    def _profile_path(self, value: object) -> Path:
        if not isinstance(value, str):
            raise AdmissionError("SDK profile evidence path missing")
        path = Path(value)
        if path.is_symlink():
            raise AdmissionError("SDK profile evidence symlink")
        resolved = path.resolve(strict=True)
        if not resolved.is_relative_to(self._config.profile.root.resolve(strict=True)):
            raise AdmissionError("SDK profile evidence path escaped")
        return resolved

    @staticmethod
    def _load_json_object(path: Path) -> dict[str, object]:
        value = json.loads(path.read_bytes())
        if not isinstance(value, dict):
            raise AdmissionError("SDK profile evidence malformed")
        return value

    @staticmethod
    def _validate_profile_evidence(
        manifest: dict[str, object],
        messages: dict[str, object],
        contract: ProbeContract,
        session_id: str,
        messages_path: Path,
        capabilities: dict[str, object],
    ) -> None:
        manifest_capabilities = dict(capabilities)
        manifest_capabilities.pop("backend_mode", None)
        if manifest.get("backend_mode") != "local":
            raise AdmissionError("SDK manifest backend mismatch")
        if manifest.get("capabilities") != manifest_capabilities:
            raise AdmissionError("SDK manifest capabilities mismatch")
        if manifest.get("messages_path") != str(messages_path):
            raise AdmissionError("SDK manifest messages path mismatch")
        if manifest.get("provider") != contract.provider_id:
            raise AdmissionError("SDK manifest provider mismatch")
        if manifest.get("model") != contract.model_id:
            raise AdmissionError("SDK manifest model mismatch")
        if manifest.get("session_id") != session_id or messages.get("sessionId") != session_id:
            raise AdmissionError("SDK manifest session mismatch")
        if set(manifest) != {
            "backend_mode",
            "capabilities",
            "messages_path",
            "model",
            "provider",
            "session_id",
        }:
            raise AdmissionError("SDK manifest schema mismatch")

    @staticmethod
    def _message_models(messages: dict[str, object], provider: str) -> tuple[str, ...]:
        rows = messages.get("messages")
        if not isinstance(rows, list) or not rows:
            raise AdmissionError("SDK message identity missing")
        models: list[str] = []
        for row in rows:
            if not isinstance(row, dict) or row.get("role") != "assistant":
                continue
            info = row.get("modelInfo")
            if not isinstance(info, dict) or info.get("provider") != provider:
                raise AdmissionError("SDK message provider mismatch")
            model = info.get("id")
            if not isinstance(model, str):
                raise AdmissionError("SDK message model malformed")
            models.append(model)
        if not models:
            raise AdmissionError("SDK message identity missing")
        return tuple(models)
