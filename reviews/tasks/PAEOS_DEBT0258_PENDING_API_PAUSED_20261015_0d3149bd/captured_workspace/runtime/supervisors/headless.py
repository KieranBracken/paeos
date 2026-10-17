"""Shell-free invocation primitives shared by headless supervisor adapters."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from paeos.model_router.types import ModelFamily

from runtime.integrations.bridge_protocol import ProtocolViolation
from runtime.supervisors.protocol import (
    MAX_ENVELOPE_BYTES,
    AdapterResult,
    SupervisorAdapter,
    SupervisorRequest,
    TransportObservation,
    decode_response,
    encode_request,
    validate_response,
)


@dataclass(frozen=True, slots=True)
class HeadlessInvocation:
    argv: tuple[str, ...]
    cwd: Path
    stdin: bytes
    timeout_seconds: float
    environment_keys: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.argv or any(not isinstance(item, str) or not item for item in self.argv):
            raise ProtocolViolation("headless argv must be a non-empty string tuple")
        if not self.cwd.is_absolute() or not self.cwd.is_dir():
            raise ProtocolViolation("headless cwd must be an existing absolute directory")
        if not isinstance(self.stdin, bytes) or len(self.stdin) > MAX_ENVELOPE_BYTES:
            raise ProtocolViolation("headless stdin is empty or oversized")
        if not isinstance(self.timeout_seconds, (int, float)) or self.timeout_seconds <= 0:
            raise ProtocolViolation("headless timeout must be positive")
        if any(
            not isinstance(key, str) or not key or "=" in key or "\x00" in key
            for key in self.environment_keys
        ):
            raise ProtocolViolation("environment_keys must contain names only")


@dataclass(frozen=True, slots=True)
class HeadlessResult:
    returncode: int
    stdout: bytes
    stderr: bytes
    provider: str
    actual_model_id: str
    model_family: ModelFamily
    provider_request_id: str
    observed_at: str
    usage: dict[str, int]


class HeadlessRunner(Protocol):
    def run(self, invocation: HeadlessInvocation) -> HeadlessResult: ...


class SupervisorAdapterError(RuntimeError):
    """A bounded headless invocation failed without a retry or fallback."""


class HeadlessSupervisorAdapter(SupervisorAdapter):
    """Common shell-free adapter implementation; subclasses only identify the transport."""

    def __init__(
        self,
        *,
        runner: HeadlessRunner,
        executable: Path,
        executable_sha256: str,
        cwd: Path,
        argv_prefix: tuple[str, ...],
        adapter_id: str,
        adapter_version: str,
        environment_keys: tuple[str, ...] = (),
        timeout_seconds: float = 120.0,
    ) -> None:
        self._runner = runner
        self._executable = executable
        self._executable_sha256 = executable_sha256
        self._cwd = cwd
        self._argv_prefix = argv_prefix
        self._adapter_id = adapter_id
        self._adapter_version = adapter_version
        self._environment_keys = environment_keys
        self._timeout_seconds = timeout_seconds
        if not executable.is_absolute() or not cwd.is_absolute() or not cwd.is_dir():
            raise ProtocolViolation("headless executable and cwd must be absolute; cwd must exist")
        invalid_environment_key = any(
            not isinstance(key, str) or not key or "=" in key or "\x00" in key
            for key in environment_keys
        )
        if invalid_environment_key:
            raise ProtocolViolation("environment_keys must contain names only")
        if timeout_seconds <= 0:
            raise ProtocolViolation("headless timeout must be positive")

    def invoke(self, request: SupervisorRequest, context: bytes) -> AdapterResult:
        if not isinstance(context, bytes) or len(context) > MAX_ENVELOPE_BYTES:
            raise ProtocolViolation("headless context must be bounded bytes")
        request_bytes = encode_request(request)
        stdin = request_bytes + context
        if len(stdin) > MAX_ENVELOPE_BYTES:
            raise ProtocolViolation("headless request and context exceed envelope size limit")
        if not self._executable.is_file() or not self._executable.is_absolute():
            raise SupervisorAdapterError("pinned headless executable is unavailable")
        actual_hash = hashlib.sha256(self._executable.read_bytes()).hexdigest()
        if actual_hash != self._executable_sha256:
            raise SupervisorAdapterError("pinned headless executable hash mismatch")
        invocation = HeadlessInvocation(
            argv=(*self._argv_prefix, str(self._executable)),
            cwd=self._cwd,
            stdin=stdin,
            timeout_seconds=self._timeout_seconds,
            environment_keys=self._environment_keys,
        )
        result = self._runner.run(invocation)
        if result.returncode != 0:
            raise SupervisorAdapterError(
                f"headless invocation failed with returncode {result.returncode}: {result.stderr!r}"
            )
        response = decode_response(result.stdout)
        validate_response(request, response)
        observation = TransportObservation(
            provider=result.provider,
            actual_model_id=result.actual_model_id,
            model_family=result.model_family,
            adapter_id=self._adapter_id,
            adapter_version=self._adapter_version,
            provider_request_id=result.provider_request_id,
            observed_at=result.observed_at,
            usage=result.usage,
        )
        return AdapterResult(response_bytes=result.stdout, observation=observation)
