"""Offline response-authentication candidate; all provider execution remains denied.

This file is installed as a read-only LaunchAgent bundle outside worker-approved roots. It is
not a general command launcher: the IPC protocol contains no caller-selected executable,
profile, environment, filesystem roots, network policy, or fallback route.
"""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import math
import os
import re
import shutil
import socket
import stat
import threading
import time
from collections.abc import Mapping
from dataclasses import replace
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from types import MappingProxyType
from typing import Any, ClassVar

from nacl.exceptions import BadSignatureError
from nacl.signing import SigningKey, VerifyKey
from paeos.model_router.catalog import ModelCatalog
from paeos.model_router.credentials import CredentialStore
from paeos.model_router.errors import parse_retry_after
from paeos.model_router.provider_transports import ClineEnvelopeTransport
from paeos.model_router.router import ModelRouter
from paeos.model_router.server import run_gateway_server
from paeos.model_router.state import RouterStateDB
from paeos.model_router.types import (
    AdmissionState,
    DataClass,
    ModelCatalogEntry,
    ModelFamily,
    NormalizedError,
    NormalizedErrorType,
    ProviderId,
    RetryPolicy,
    RouterResponse,
    TaskClass,
    TaskRequest,
)
from runtime.integrations.process_supervisor import (
    ProcessLifecycleState,
    ProcessSupervisorError,
    run_bounded_process,
)
from runtime.integrations.worker_confinement import (
    WorkerConfinementError,
    build_provider_environment,
    policy_for_worker,
)

SERVICE_SCHEMA = "paeos.trusted-worker-service/1"
CAPABILITY_SCHEMA = "paeos.trusted-worker-capability/1"
OPERATION = "provider_chat"
PROVIDER = "openrouter"
MODEL = "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free"
FAMILY = "nemotron"
MAX_PROMPT_BYTES = 4096
MAX_RESPONSE_BYTES = 256 * 1024
MAX_FRAME_BYTES = 512 * 1024
CAPABILITY_TTL_SECONDS = 45.0
CLINE_CAPABILITY_SCHEMA = "paeos.trusted-cline-critic-capability/1"
CLINE_OPERATION = "critic"
CLINE_PROVIDER = "cline-pass"
CLINE_MODEL = "cline-pass/glm-5.3"
CLINE_FAMILY = "glm-5.3"
NVIDIA_CRITIC_CAPABILITY_SCHEMA = "paeos.trusted-nvidia-critic-capability/1"
NVIDIA_CRITIC_PROVIDER = "nvidia"
NVIDIA_CRITIC_MODEL = "meta/llama-3.1-8b-instruct"
NVIDIA_CRITIC_FAMILY = "llama"
GEMINI38_CRITIC_CAPABILITY_SCHEMA = "paeos.trusted-gemini38-critic-capability/1"
GEMINI38_CRITIC_OPERATION = "critic"
GEMINI38_CRITIC_PROVIDER = "google"
GEMINI38_CRITIC_MODEL = "gemini-3.8-flash"
GEMINI38_CRITIC_FAMILY = "gemini"
GEMINI38_CRITIC_MAX_COMPLETION_TOKENS = 512
GEMINI38_ADVERSARY_CAPABILITY_SCHEMA = "paeos.trusted-gemini38-adversary-capability/1"
GEMINI38_ADVERSARY_OPERATION = "adversarial_review"
GEMINI38_ADVERSARY_PROVIDER = "google"
GEMINI38_ADVERSARY_MODEL = "gemini-3.8-flash"
GEMINI38_ADVERSARY_FAMILY = "gemini"
GEMINI38_ADVERSARY_MAX_COMPLETION_TOKENS = 1024
GEMINI36_CRITIC_CAPABILITY_SCHEMA = "paeos.trusted-gemini36-critic-capability/1"
GEMINI36_CRITIC_PROVIDER = "google"
GEMINI36_CRITIC_MODEL = "gemini-3.6-flash"
GEMINI36_CRITIC_FAMILY = "gemini"
GEMINI36_CRITIC_MAX_COMPLETION_TOKENS = 512
GEMINI36_ADVERSARY_CAPABILITY_SCHEMA = "paeos.trusted-gemini36-adversary-capability/1"
GEMINI36_ADVERSARY_OPERATION = "adversarial_review"
GEMINI36_ADVERSARY_PROVIDER = "google"
GEMINI36_ADVERSARY_MODEL = "gemini-3.6-flash"
GEMINI36_ADVERSARY_FAMILY = "gemini"
GEMINI36_ADVERSARY_MAX_COMPLETION_TOKENS = 1024
GEMINI36_ADVERSARY_MAX_PROMPT_BYTES = 128 * 1024
GEMINI36_RESPONSE_CONTRACT_FAILURE_CODES = frozenset(
    {
        "response_type",
        "response_provider_identity",
        "response_fallback_chain",
        "response_attempt_count",
        "response_completion_shape",
        "response_content",
        "response_size",
    }
)
GEMINI36_RESPONSE_COMPLETION_SHAPE_DETAILS = frozenset(
    {"tool_calls_present", "finish_reason_not_stop"}
)
PROVIDER_FAILURE_OBSERVATION_SCHEMA = "paeos.provider-failure-observation/1"
GEMINI38_PROCESS_OBSERVATION_SCHEMA = "paeos.gemini38-process-observation/1"
GEMINI38_RESPONSE_CONTRACT_DIAGNOSTIC_SCHEMA = (
    "paeos.gemini38-response-contract-diagnostic/3"
)
GEMINI38_RESPONSE_CONTRACT_FAILURE_CODES = frozenset(
    {
        "response_type",
        "response_provider_identity",
        "response_fallback_chain",
        "response_attempt_count",
        "response_completion_shape",
        "response_content",
        "response_size",
    }
)
GEMINI38_RESPONSE_COMPLETION_SHAPE_DETAILS = frozenset(
    {"tool_calls_present", "finish_reason_not_stop"}
)
GEMINI38_FINISH_REASON_CLASSES = frozenset(
    {"length", "content_filter", "tool_calls", "function_call", "other"}
)
CAPABILITY_ID_RE = re.compile(r"^[0-9a-f]{32}$")
SIGNATURE_RE = re.compile(r"^[0-9a-f]{128}$")
DEFAULT_SOCKET = Path("/Users/bob/GitHub/paeos/ops/.trusted-worker/launcher.sock")
_CANARY_SCRIPT = """#!/bin/sh
set +e
mark() {
  printf '%s=%s\\n' "$1" "$2"
}
if [ "${PAEOS_SYNTHETIC_PARENT_SECRET+x}" = x ] || \
    /usr/bin/env | /usr/bin/grep -q '_API_KEY='
then
  mark parent_secret_or_provider_credential FAIL
else
  mark parent_secret_or_provider_credential PASS
fi
if [ "$(/bin/cat "$1" 2>/dev/null)" = "DEBT0124_APPROVED_READ" ]
then
  mark approved_read PASS
else
  mark approved_read FAIL
fi
if (printf '%s' DEBT0124_APPROVED_WRITE > "$2" 2>/dev/null) && \
    [ "$(/bin/cat "$2" 2>/dev/null)" = "DEBT0124_APPROVED_WRITE" ]
then
  mark approved_write PASS
else
  mark approved_write FAIL
fi
if /bin/cat "$3" >/dev/null 2>&1
then
  mark forbidden_file_read FAIL
else
  mark forbidden_file_read PASS
fi
if /bin/ls "$4" >/dev/null 2>&1
then
  mark forbidden_directory_list FAIL
else
  mark forbidden_directory_list PASS
fi
if (printf '%s' DEBT0124_FORBIDDEN_WRITE > "$7" 2>/dev/null)
then
  mark forbidden_write FAIL
else
  mark forbidden_write PASS
fi
if /bin/cat "$5" >/dev/null 2>&1
then
  mark symlink_escape FAIL
else
  if (printf '%s' DEBT0124_SYMLINK_WRITE > "$5" 2>/dev/null)
  then
    mark symlink_escape FAIL
  else
    mark symlink_escape PASS
  fi
fi
if /bin/cat "$6" >/dev/null 2>&1
then
  mark traversal_escape FAIL
else
  mark traversal_escape PASS
fi
if /bin/sh -c '/bin/cat "$1" >/dev/null 2>&1' confined-child "$3"
then
  mark subprocess_inheritance FAIL
else
  mark subprocess_inheritance PASS
fi
"""
_CANARY_KEYS = frozenset(
    {
        "parent_secret_or_provider_credential",
        "approved_read",
        "approved_write",
        "forbidden_file_read",
        "forbidden_directory_list",
        "forbidden_write",
        "symlink_escape",
        "traversal_escape",
        "subprocess_inheritance",
    }
)


def _canonical_bytes(value: object) -> bytes:
    return (
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
        + "\n"
    ).encode("utf-8")


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _gemini38_finish_reason_class(value: object) -> str:
    """Reduce a provider finish reason to a bounded, non-identifying class."""

    if type(value) is str and value in GEMINI38_FINISH_REASON_CLASSES - {"other"}:
        return value
    return "other"


_SAFE_RESET_HEADER_NAMES = frozenset(
    {
        "ratelimit-reset",
        "rate-limit-reset",
        "x-ratelimit-reset",
        "x-rate-limit-reset",
    }
)
_SAFE_RESET_BODY_KEYS = frozenset(
    {
        "reset",
        "reset_at",
        "reset_at_epoch",
        "rate_limit_reset",
        "rate_limit_reset_epoch",
        "ratelimit_reset",
        "ratelimit_reset_epoch",
        "x_ratelimit_reset",
    }
)


def _safe_timing_number(value: object) -> float | None:
    """Return bounded numeric timing metadata without retaining its source text."""

    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number) or number < 0.0 or number > 4_102_444_800.0:
        return None
    return number


def _safe_reset_from_headers(headers: Mapping[str, object] | None) -> float | None:
    if not headers:
        return None
    for name, value in headers.items():
        if isinstance(name, str) and name.lower() in _SAFE_RESET_HEADER_NAMES:
            parsed = _safe_timing_number(value)
            if parsed is not None:
                return parsed
    return None


def _safe_reset_from_body(raw_response: str | None) -> float | None:
    if not isinstance(raw_response, str) or not raw_response:
        return None
    try:
        document = json.loads(raw_response)
    except (TypeError, ValueError):
        return None
    candidates: list[object] = [document]
    if isinstance(document, dict) and isinstance(document.get("error"), dict):
        candidates.append(document["error"])
    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        for key, value in candidate.items():
            if isinstance(key, str) and key.lower() in _SAFE_RESET_BODY_KEYS:
                parsed = _safe_timing_number(value)
                if parsed is not None:
                    return parsed
    return None


def _safe_response_bytes(error: BaseException) -> bytes:
    """Materialize provider error data only in memory for hashing; never persist its contents."""

    raw_response = getattr(error, "raw_response", None)
    if raw_response is None:
        return b""
    if isinstance(raw_response, bytes):
        return raw_response
    if isinstance(raw_response, str):
        return raw_response.encode("utf-8")
    return _canonical_bytes(raw_response)


def _nvidia_provider_failure_observation(error: NormalizedError) -> dict[str, object]:
    """Reduce one exact NVIDIA failure to the complete content-free wire contract."""

    if (
        error.provider_id is not ProviderId.NVIDIA
        or error.model_id != NVIDIA_CRITIC_MODEL
        or not isinstance(error.error_type, NormalizedErrorType)
    ):
        raise RuntimeError("NVIDIA provider failure attribution is malformed")
    status = error.http_status
    if status is not None and (
        not isinstance(status, int)
        or isinstance(status, bool)
        or not 100 <= status <= 599
    ):
        raise RuntimeError("NVIDIA provider failure HTTP status is malformed")
    retry_after = error.retry_after
    if retry_after is not None:
        retry_after = _safe_timing_number(retry_after)
        if retry_after is None:
            raise RuntimeError("NVIDIA provider failure retry metadata is malformed")
    raw_response = error.raw_response
    if raw_response is not None and not isinstance(raw_response, (str, bytes)):
        raise RuntimeError("NVIDIA provider failure response metadata is malformed")
    response_bytes = None
    response_sha256 = None
    if raw_response is not None:
        body = (
            raw_response
            if isinstance(raw_response, bytes)
            else raw_response.encode("utf-8")
        )
        response_bytes = len(body)
        response_sha256 = _sha256(body)
    return {
        "schema": PROVIDER_FAILURE_OBSERVATION_SCHEMA,
        "provider_id": NVIDIA_CRITIC_PROVIDER,
        "model_id": NVIDIA_CRITIC_MODEL,
        "error_type": error.error_type.value,
        "http_status": status,
        "retry_after": retry_after,
        "response_bytes": response_bytes,
        "response_sha256": response_sha256,
        "raw_response_persisted": False,
    }


def _gemini38_provider_failure_observation(error: NormalizedError) -> dict[str, object]:
    """Reduce one exact Google/Gemini failure to content-free bounded facts."""

    if (
        error.provider_id is not ProviderId.GOOGLE
        or error.model_id != GEMINI38_CRITIC_MODEL
        or not isinstance(error.error_type, NormalizedErrorType)
    ):
        raise RuntimeError("Gemini 3.8 provider failure attribution is malformed")
    status = error.http_status
    if status is not None and (
        not isinstance(status, int)
        or isinstance(status, bool)
        or not 100 <= status <= 599
    ):
        raise RuntimeError("Gemini 3.8 provider failure HTTP status is malformed")
    retry_after = error.retry_after
    if retry_after is not None:
        retry_after = _safe_timing_number(retry_after)
        if retry_after is None:
            raise RuntimeError(
                "Gemini 3.8 provider failure retry metadata is malformed"
            )
    raw_response = error.raw_response
    if raw_response is not None and not isinstance(raw_response, (str, bytes)):
        raise RuntimeError("Gemini 3.8 provider failure response metadata is malformed")
    body = (
        None
        if raw_response is None
        else (
            raw_response
            if isinstance(raw_response, bytes)
            else raw_response.encode("utf-8")
        )
    )
    return {
        "schema": PROVIDER_FAILURE_OBSERVATION_SCHEMA,
        "provider_id": GEMINI38_CRITIC_PROVIDER,
        "model_id": GEMINI38_CRITIC_MODEL,
        "error_type": error.error_type.value,
        "http_status": status,
        "retry_after": retry_after,
        "response_bytes": None if body is None else len(body),
        "response_sha256": None if body is None else _sha256(body),
        "raw_response_persisted": False,
    }


def _gemini36_provider_failure_observation(error: NormalizedError) -> dict[str, object]:
    """Reduce one exact Google/Gemini 3.6 failure to content-free bounded facts."""

    if (
        error.provider_id is not ProviderId.GOOGLE
        or error.model_id != GEMINI36_CRITIC_MODEL
        or not isinstance(error.error_type, NormalizedErrorType)
    ):
        raise RuntimeError("Gemini 3.6 provider failure attribution is malformed")
    status = error.http_status
    if status is not None and (
        not isinstance(status, int)
        or isinstance(status, bool)
        or not 100 <= status <= 599
    ):
        raise RuntimeError("Gemini 3.6 provider failure HTTP status is malformed")
    retry_after = error.retry_after
    if retry_after is not None:
        retry_after = _safe_timing_number(retry_after)
        if retry_after is None:
            raise RuntimeError(
                "Gemini 3.6 provider failure retry metadata is malformed"
            )
    raw_response = error.raw_response
    if raw_response is not None and not isinstance(raw_response, (str, bytes)):
        raise RuntimeError("Gemini 3.6 provider failure response metadata is malformed")
    body = (
        None
        if raw_response is None
        else (
            raw_response
            if isinstance(raw_response, bytes)
            else raw_response.encode()
        )
    )
    return {
        "schema": PROVIDER_FAILURE_OBSERVATION_SCHEMA,
        "provider_id": GEMINI36_CRITIC_PROVIDER,
        "model_id": GEMINI36_CRITIC_MODEL,
        "error_type": error.error_type.value,
        "http_status": status,
        "retry_after": retry_after,
        "response_bytes": None if body is None else len(body),
        "response_sha256": None if body is None else _sha256(body),
        "raw_response_persisted": False,
    }


def _gemini36_post_response_failure_observation(
    response: object,
) -> dict[str, object]:
    """Describe a rejected router response without retaining any response content."""

    body: bytes | None = None
    if type(response) is RouterResponse and isinstance(response.content, str):
        try:
            body = response.content.encode("utf-8")
        except UnicodeEncodeError:
            body = None
    return {
        "schema": PROVIDER_FAILURE_OBSERVATION_SCHEMA,
        "provider_id": GEMINI36_CRITIC_PROVIDER,
        "model_id": GEMINI36_CRITIC_MODEL,
        "error_type": NormalizedErrorType.UNKNOWN.value,
        "http_status": 200 if type(response) is RouterResponse else None,
        "retry_after": None,
        "response_bytes": None if body is None else len(body),
        "response_sha256": None if body is None else _sha256(body),
        "raw_response_persisted": False,
    }


def _is_gemini36_failure_code(value: object) -> bool:
    """Accept only a base response predicate or one bounded shape detail."""

    if type(value) is not str:
        return False
    if value in GEMINI36_RESPONSE_CONTRACT_FAILURE_CODES:
        return True
    prefix = "response_completion_shape:"
    return value.startswith(prefix) and value.removeprefix(prefix) in (
        GEMINI36_RESPONSE_COMPLETION_SHAPE_DETAILS
    )


def _safe_provider_http_diagnostic(
    error: BaseException,
    *,
    transport_exit_code: int | None,
    headers: Mapping[str, object] | None = None,
) -> dict[str, object]:
    """Build a content-free, bounded diagnostic for one parent-owned provider exchange."""

    raw_response = getattr(error, "raw_response", None)
    status = getattr(error, "http_status", None)
    if (
        not isinstance(status, int)
        or isinstance(status, bool)
        or not 100 <= status <= 599
    ):
        status = None
    response_observed = status is not None or bool(headers)
    raw_bytes = _safe_response_bytes(error) if response_observed else b""
    retry_after = (
        _safe_timing_number(getattr(error, "retry_after", None))
        if response_observed
        else None
    )
    if retry_after is None and response_observed:
        raw_text = raw_response if isinstance(raw_response, str) else ""
        retry_after = _safe_timing_number(
            parse_retry_after(dict(headers or {}), raw_text)
        )
    reset_epoch = _safe_reset_from_headers(headers)
    if reset_epoch is None and response_observed:
        reset_epoch = _safe_reset_from_body(
            raw_response if isinstance(raw_response, str) else None
        )
    error_type = getattr(error, "error_type", None)
    error_class = getattr(error_type, "value", None)
    if not isinstance(error_class, str) or not error_class:
        error_class = "UNOBSERVED"
    provider_id = getattr(error, "provider_id", None)
    model_id = getattr(error, "model_id", None)
    return {
        "schema": "paeos.cline-provider-http-diagnostic/1",
        "provider_id": provider_id.value
        if isinstance(provider_id, ProviderId)
        else CLINE_PROVIDER,
        "model_id": model_id if isinstance(model_id, str) else CLINE_MODEL,
        "upstream_http_status": status,
        "transport_exit_code": transport_exit_code,
        "headers_received": status is not None or bool(headers),
        "retry_after_seconds": retry_after,
        "rate_limit_reset_epoch": reset_epoch,
        "safe_rate_limit_timing_present": retry_after is not None
        or reset_epoch is not None,
        "response_bytes": len(raw_bytes),
        "response_sha256": _sha256(raw_bytes) if raw_bytes else None,
        "error_class": error_class,
        "raw_response_persisted": False,
        "sensitive_headers_persisted": False,
    }


def _persist_cline_http_diagnostic(
    observation_root: Path,
    capability_id: str,
    error: BaseException,
    *,
    transport_exit_code: int | None,
    loopback_http_status: int | None,
    headers: Mapping[str, object] | None = None,
) -> None:
    diagnostic = _safe_provider_http_diagnostic(
        error,
        transport_exit_code=transport_exit_code,
        headers=headers,
    )
    diagnostic["capability_id"] = capability_id
    diagnostic["loopback_http_status"] = loopback_http_status
    _write_exclusive(
        observation_root / f"{capability_id}.provider-diagnostic.json",
        _canonical_bytes(diagnostic),
    )


def _write_exclusive(path: Path, payload: bytes) -> None:
    if not path.is_absolute() or path.exists():
        raise RuntimeError("transient provider file is not new and absolute")
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        offset = 0
        while offset < len(payload):
            written = os.write(fd, payload[offset:])
            if written <= 0:
                raise RuntimeError("transient provider file write made no progress")
            offset += written
        os.fsync(fd)
    finally:
        os.close(fd)
    os.chmod(path, 0o600)


def _persist_gemini38_process_observation(
    state_root: Path,
    capability_id: str,
    observation: Mapping[str, object],
) -> None:
    """Atomically retain only bounded facts about a failed confined child."""

    if _capability_id(capability_id) != capability_id:
        raise RuntimeError("Gemini 3.8 process observation capability id is invalid")
    if set(observation) != _ProcessFailure._FIELDS:
        raise RuntimeError("Gemini 3.8 process observation fields are not exact")
    # Reuse the strict value validation without retaining or serializing child content.
    validated = _ProcessFailure(dict(observation)).observation
    state_root = _safe_path(state_root, label="launcher state root")
    observation_root = _safe_path(
        state_root / "gemini38-process-observations",
        label="Gemini 3.8 process observation root",
    )
    observation_root.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(observation_root, 0o700)
    if (
        not observation_root.is_dir()
        or stat.S_IMODE(observation_root.stat().st_mode) != 0o700
    ):
        raise RuntimeError("Gemini 3.8 process observation directory is not exact")
    final_path = _safe_path(
        observation_root / f"{capability_id}.json",
        label="Gemini 3.8 process observation path",
    )
    temporary_path = _safe_path(
        observation_root / f".{capability_id}.tmp",
        label="Gemini 3.8 process observation temporary path",
    )
    record = {
        "schema": GEMINI38_PROCESS_OBSERVATION_SCHEMA,
        "capability_id": capability_id,
        "provider_id": GEMINI38_CRITIC_PROVIDER,
        "model_id": GEMINI38_CRITIC_MODEL,
        **validated,
    }
    expected = {
        "schema",
        "capability_id",
        "provider_id",
        "model_id",
        "lifecycle_state",
        "exit_code",
        "stdout_bytes",
        "stdout_sha256",
        "stderr_bytes",
        "stderr_sha256",
    }
    if set(record) != expected or final_path.exists() or temporary_path.exists():
        raise RuntimeError("Gemini 3.8 process observation target is not new")
    try:
        _write_exclusive(temporary_path, _canonical_bytes(record))
        os.replace(temporary_path, final_path)
        os.chmod(final_path, 0o600)
        if stat.S_IMODE(final_path.stat().st_mode) != 0o600:
            raise RuntimeError("Gemini 3.8 process observation mode is not exact")
        file_fd = os.open(final_path, os.O_RDONLY | os.O_NOFOLLOW)
        try:
            os.fsync(file_fd)
        finally:
            os.close(file_fd)
        directory_fd = os.open(observation_root, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    except Exception:
        with contextlib.suppress(OSError):
            temporary_path.unlink()
        raise


def _persist_gemini38_response_contract_diagnostic(
    state_root: Path,
    capability_id: str,
    failure_code: str,
    failure_detail: str | None,
    finish_reason_class: str | None,
    observation: Mapping[str, object],
    *,
    router_response_observed: bool,
) -> None:
    """Atomically retain only bounded facts about a local response rejection."""

    if _capability_id(capability_id) != capability_id:
        raise RuntimeError("Gemini 3.8 response diagnostic capability id is invalid")
    if (
        failure_code not in GEMINI38_RESPONSE_CONTRACT_FAILURE_CODES
        or type(router_response_observed) is not bool
    ):
        raise RuntimeError("Gemini 3.8 response diagnostic classification is invalid")
    if (
        failure_code == "response_completion_shape"
        and (
            type(failure_detail) is not str
            or failure_detail not in GEMINI38_RESPONSE_COMPLETION_SHAPE_DETAILS
        )
    ) or (failure_code != "response_completion_shape" and failure_detail is not None):
        raise RuntimeError("Gemini 3.8 response diagnostic detail is invalid")
    if (
        failure_code == "response_completion_shape"
        and (
            type(finish_reason_class) is not str
            or finish_reason_class not in GEMINI38_FINISH_REASON_CLASSES
        )
    ) or (
        failure_code != "response_completion_shape" and finish_reason_class is not None
    ):
        raise RuntimeError("Gemini 3.8 response finish reason class is invalid")
    if set(observation) != _ProcessFailure._FIELDS:
        raise RuntimeError(
            "Gemini 3.8 response diagnostic process fields are not exact"
        )
    validated = _ProcessFailure(dict(observation)).observation
    lifecycle_values = {state.value for state in ProcessLifecycleState}
    if (
        validated["lifecycle_state"] not in lifecycle_values
        or validated["exit_code"] == 0
        or validated["stdout_bytes"] < 0
        or validated["stderr_bytes"] < 0
        or re.fullmatch(r"[0-9a-f]{64}", validated["stdout_sha256"]) is None
        or re.fullmatch(r"[0-9a-f]{64}", validated["stderr_sha256"]) is None
        or router_response_observed is not True
    ):
        raise RuntimeError("Gemini 3.8 response diagnostic process facts are invalid")
    state_root = _safe_path(state_root, label="launcher state root")
    diagnostic_root = _safe_path(
        state_root / "gemini38-response-contract-diagnostics",
        label="Gemini 3.8 response diagnostic root",
    )
    diagnostic_root.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(diagnostic_root, 0o700)
    if (
        not diagnostic_root.is_dir()
        or stat.S_IMODE(diagnostic_root.stat().st_mode) != 0o700
    ):
        raise RuntimeError("Gemini 3.8 response diagnostic directory is not exact")
    final_path = _safe_path(
        diagnostic_root / f"{capability_id}.json",
        label="Gemini 3.8 response diagnostic path",
    )
    temporary_path = _safe_path(
        diagnostic_root / f".{capability_id}.tmp",
        label="Gemini 3.8 response diagnostic temporary path",
    )
    record = {
        "schema": GEMINI38_RESPONSE_CONTRACT_DIAGNOSTIC_SCHEMA,
        "capability_id": capability_id,
        "provider_id": GEMINI38_CRITIC_PROVIDER,
        "model_id": GEMINI38_CRITIC_MODEL,
        "failure_code": failure_code,
        "failure_detail": failure_detail,
        "router_response_observed": router_response_observed,
        "worker_lifecycle_state": validated["lifecycle_state"],
        "worker_exit_code": validated["exit_code"],
        "stdout_bytes": validated["stdout_bytes"],
        "stdout_sha256": validated["stdout_sha256"],
        "stderr_bytes": validated["stderr_bytes"],
        "stderr_sha256": validated["stderr_sha256"],
    }
    if finish_reason_class is not None:
        record["finish_reason_class"] = finish_reason_class
    expected = {
        "schema",
        "capability_id",
        "provider_id",
        "model_id",
        "failure_code",
        "failure_detail",
        "router_response_observed",
        "worker_lifecycle_state",
        "worker_exit_code",
        "stdout_bytes",
        "stdout_sha256",
        "stderr_bytes",
        "stderr_sha256",
    }
    if failure_code == "response_completion_shape":
        expected.add("finish_reason_class")
    if set(record) != expected or final_path.exists() or temporary_path.exists():
        raise RuntimeError("Gemini 3.8 response diagnostic target is not new")
    try:
        _write_exclusive(temporary_path, _canonical_bytes(record))
        os.link(temporary_path, final_path, follow_symlinks=False)
        temporary_path.unlink()
        if stat.S_IMODE(final_path.stat().st_mode) != 0o600:
            raise RuntimeError("Gemini 3.8 response diagnostic mode is not exact")
        file_fd = os.open(final_path, os.O_RDONLY | os.O_NOFOLLOW)
        try:
            os.fsync(file_fd)
        finally:
            os.close(file_fd)
        directory_fd = os.open(diagnostic_root, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    except Exception:
        with contextlib.suppress(OSError):
            temporary_path.unlink()
        raise


def _remove_exact(path: Path) -> None:
    if not path.exists():
        raise RuntimeError("transient provider file was absent during cleanup")
    path.unlink()
    if path.exists():
        raise RuntimeError("transient provider file remained after cleanup")


def _safe_path(path: Path, *, label: str) -> Path:
    if not path.is_absolute() or path.is_symlink() or ".." in path.parts:
        raise RuntimeError(f"{label} is not an absolute non-symlink path")
    resolved = path.resolve(strict=False)
    if resolved != path:
        raise RuntimeError(f"{label} is not canonical")
    return resolved


def _fixed_entry() -> Any:
    candidates = [
        entry
        for entry in ModelCatalog().list_models()
        if entry.provider_id is ProviderId.OPENROUTER and entry.model_id == MODEL
    ]
    if len(candidates) != 1:
        raise RuntimeError("fixed provider catalog entry is not unique")
    entry = candidates[0]
    from paeos.model_router.types import AdmissionState

    if (
        entry.family is not ModelFamily.NEMOTRON
        or entry.admission_state is not AdmissionState.ADMITTED
        or not entry.live_verified
        or not entry.available
    ):
        raise RuntimeError("fixed provider route is not admitted and live")
    return entry


def _fixed_cline_entry() -> Any:
    candidates = [
        entry
        for entry in ModelCatalog().list_models()
        if entry.provider_id is ProviderId.CLINE and entry.model_id == CLINE_MODEL
    ]
    if len(candidates) != 1 or candidates[0].family is not ModelFamily.GLM:
        raise RuntimeError("fixed Cline critic catalog entry is not unique")
    return candidates[0]


class _FixedRouter:
    """Attenuate the parent-owned router to one exact public non-GPT request."""

    def __init__(self, router: ModelRouter, entry: Any) -> None:
        self.catalog = router.catalog
        self.credentials = router.credentials
        self.state_db = router.state_db
        self._router = router
        self._entry = entry
        self._used = False
        self._response: Any | None = None
        self._lock = threading.Lock()

    @property
    def response(self) -> Any | None:
        return self._response

    def route(self, request: TaskRequest) -> Any:
        if request.data_class is not DataClass.PUBLIC:
            raise RuntimeError("only PUBLIC data is permitted")
        if request.task_class is not TaskClass.ROUTINE:
            raise RuntimeError("only ROUTINE tasks are permitted")
        if request.explicit_model != MODEL:
            raise RuntimeError("model is outside the fixed supervisor binding")
        if (
            request.stream
            or request.tools is not None
            or request.tool_choice is not None
        ):
            raise RuntimeError("streaming and tools are forbidden")
        if request.require_tools or request.require_json:
            raise RuntimeError("unsupported request requirement")
        with self._lock:
            if self._used:
                raise RuntimeError("one request limit exceeded")
            self._used = True
        response = self._router.route(request)
        if (
            response.provider_id is not ProviderId.OPENROUTER
            or response.model_id != MODEL
        ):
            raise RuntimeError("provider/model attribution mismatch")
        if response.fallback_chain != [f"{PROVIDER}:{MODEL}"]:
            raise RuntimeError("fallback chain escaped the fixed supervisor binding")
        if response.actual_model is None or not response.actual_model.strip():
            raise RuntimeError("actual model attribution is missing")
        if response.actual_family in (None, ModelFamily.GPT, ModelFamily.UNKNOWN):
            raise RuntimeError("actual provider family is not known non-GPT")
        if response.tool_calls or response.finish_reason != "stop":
            raise RuntimeError("response is not a plain completed message")
        if not isinstance(response.content, str) or not response.content.strip():
            raise RuntimeError("provider response content is empty")
        if len(response.content.encode("utf-8")) > MAX_RESPONSE_BYTES:
            raise RuntimeError("provider response exceeds bounded size")
        self._response = response
        return response


class _FixedNvidiaCriticRouter:
    """Attenuate a parent-owned router to one exact NVIDIA critic request."""

    def __init__(self, router: ModelRouter) -> None:
        entry = ModelCatalogEntry(
            model_id=NVIDIA_CRITIC_MODEL,
            provider_id=ProviderId.NVIDIA,
            family=ModelFamily.LLAMA,
            live_verified=True,
            available=True,
            admission_state=AdmissionState.ADMITTED,
            supports_tools=False,
            supports_json=False,
        )
        catalog = ModelCatalog([entry])
        self.catalog = catalog
        self.credentials = router.credentials
        self.state_db = router.state_db
        self._router = ModelRouter(
            credentials=self.credentials,
            catalog=catalog,
            state_db=self.state_db,
        )
        self._used = False
        self._response: Any | None = None
        self._failure_observation: Mapping[str, object] | None = None
        self._lock = threading.Lock()

    @property
    def response(self) -> Any | None:
        return self._response

    @property
    def failure_observation(self) -> Mapping[str, object] | None:
        return self._failure_observation

    def route(self, request: TaskRequest) -> Any:
        if request.data_class is not DataClass.PUBLIC:
            raise RuntimeError("only PUBLIC data is permitted")
        if request.task_class is not TaskClass.ROUTINE:
            raise RuntimeError("only ROUTINE tasks are permitted")
        if request.explicit_model != NVIDIA_CRITIC_MODEL:
            raise RuntimeError("model is outside the fixed NVIDIA critic binding")
        if (
            request.stream
            or request.tools is not None
            or request.tool_choice is not None
        ):
            raise RuntimeError("streaming and tools are forbidden")
        if request.require_tools or request.require_json:
            raise RuntimeError("unsupported request requirement")
        with self._lock:
            if self._used:
                raise RuntimeError("one request limit exceeded")
            self._used = True
        fixed_request = replace(
            request,
            retry_policy=RetryPolicy.NONE,
            allow_fallback=False,
        )
        try:
            response = self._router.route(fixed_request)
        except NormalizedError as exc:
            observation = _nvidia_provider_failure_observation(exc)
            self._failure_observation = MappingProxyType(observation)
            raise
        if (
            response.provider_id is not ProviderId.NVIDIA
            or response.model_id != NVIDIA_CRITIC_MODEL
            or response.actual_model != NVIDIA_CRITIC_MODEL
            or response.actual_family is not ModelFamily.LLAMA
        ):
            raise RuntimeError("NVIDIA critic response attribution mismatch")
        if response.fallback_chain != [
            f"{NVIDIA_CRITIC_PROVIDER}:{NVIDIA_CRITIC_MODEL}"
        ]:
            raise RuntimeError("fallback chain escaped the fixed NVIDIA critic binding")
        if response.attempts != 1:
            raise RuntimeError("NVIDIA critic response did not use exactly one attempt")
        if response.tool_calls or response.finish_reason != "stop":
            raise RuntimeError("response is not a plain completed message")
        if not isinstance(response.content, str) or not response.content.strip():
            raise RuntimeError("provider response content is empty")
        if len(response.content.encode("utf-8")) > MAX_RESPONSE_BYTES:
            raise RuntimeError("provider response exceeds bounded size")
        self._response = response
        return response


class _FixedGemini38CriticRouter:
    """One-shot parent router bound to the sole admitted Google/Gemini model."""

    def __init__(self, router: ModelRouter) -> None:
        entry = ModelCatalogEntry(
            model_id=GEMINI38_CRITIC_MODEL,
            provider_id=ProviderId.GOOGLE,
            family=ModelFamily.GEMINI,
            live_verified=True,
            available=True,
            admission_state=AdmissionState.ADMITTED,
            supports_tools=False,
            supports_json=False,
        )
        catalog = ModelCatalog([entry])
        self.catalog = catalog
        self.credentials = router.credentials
        self.state_db = router.state_db
        self._router = ModelRouter(
            credentials=self.credentials, catalog=catalog, state_db=self.state_db
        )
        self._used = False
        self._response: Any | None = None
        self._failure_observation: Mapping[str, object] | None = None
        self._failure_code: str | None = None
        self._failure_detail: str | None = None
        self._finish_reason_class: str | None = None
        self._router_response_observed = False
        self._lock = threading.Lock()

    @property
    def response(self) -> Any | None:
        return self._response

    @property
    def failure_observation(self) -> Mapping[str, object] | None:
        return self._failure_observation

    @property
    def failure_code(self) -> str | None:
        return self._failure_code

    @property
    def failure_detail(self) -> str | None:
        if (
            self._failure_code == "response_completion_shape"
            and (
                type(self._failure_detail) is not str
                or self._failure_detail
                not in GEMINI38_RESPONSE_COMPLETION_SHAPE_DETAILS
            )
        ) or (
            self._failure_code != "response_completion_shape"
            and self._failure_detail is not None
        ):
            raise RuntimeError("Gemini 3.8 response diagnostic detail is invalid")
        return self._failure_detail

    @property
    def finish_reason_class(self) -> str | None:
        if (
            self._failure_code == "response_completion_shape"
            and (
                type(self._finish_reason_class) is not str
                or self._finish_reason_class not in GEMINI38_FINISH_REASON_CLASSES
            )
        ) or (
            self._failure_code != "response_completion_shape"
            and self._finish_reason_class is not None
        ):
            raise RuntimeError("Gemini 3.8 response finish reason class is invalid")
        return self._finish_reason_class

    @property
    def router_response_observed(self) -> bool:
        return self._router_response_observed

    def route(self, request: TaskRequest) -> Any:
        if type(request) is not TaskRequest:
            raise RuntimeError("Gemini 3.8 gateway request class is invalid")
        if (
            request.data_class is not DataClass.PUBLIC
            or request.task_class is not TaskClass.ROUTINE
        ):
            raise RuntimeError("Gemini 3.8 request classification is invalid")
        if request.explicit_model != GEMINI38_CRITIC_MODEL:
            raise RuntimeError("model is outside the fixed Gemini 3.8 critic binding")
        if (
            request.stream
            or request.tools is not None
            or request.tool_choice is not None
        ):
            raise RuntimeError("streaming and tools are forbidden")
        if request.require_tools or request.require_json:
            raise RuntimeError("unsupported request requirement")
        with self._lock:
            if self._used:
                raise RuntimeError("one request limit exceeded")
            self._used = True
        fixed_request = replace(
            request, retry_policy=RetryPolicy.NONE, allow_fallback=False
        )
        try:
            response = self._router.route(fixed_request)
        except NormalizedError as exc:
            observation = _gemini38_provider_failure_observation(exc)
            self._failure_observation = MappingProxyType(observation)
            raise
        self._router_response_observed = True
        if type(response) is not RouterResponse:
            self._failure_code = "response_type"
            raise RuntimeError("Gemini 3.8 critic response attribution mismatch")
        if (
            response.provider_id is not ProviderId.GOOGLE
            or response.model_id != GEMINI38_CRITIC_MODEL
            or response.actual_model != GEMINI38_CRITIC_MODEL
            or response.actual_family is not ModelFamily.GEMINI
            or response.family is not ModelFamily.GEMINI
        ):
            self._failure_code = "response_provider_identity"
            raise RuntimeError("Gemini 3.8 critic response attribution mismatch")
        if response.fallback_chain != [
            f"{GEMINI38_CRITIC_PROVIDER}:{GEMINI38_CRITIC_MODEL}"
        ]:
            self._failure_code = "response_fallback_chain"
            raise RuntimeError(
                "fallback chain escaped the fixed Gemini 3.8 critic binding"
            )
        if response.attempts != 1:
            self._failure_code = "response_attempt_count"
            raise RuntimeError(
                "Gemini 3.8 critic response did not use exactly one attempt"
            )
        if response.tool_calls or response.finish_reason != "stop":
            self._failure_code = "response_completion_shape"
            self._failure_detail = (
                "tool_calls_present"
                if response.tool_calls
                else "finish_reason_not_stop"
            )
            self._finish_reason_class = _gemini38_finish_reason_class(
                response.finish_reason
            )
            raise RuntimeError("response is not a plain completed message")
        if not isinstance(response.content, str) or not response.content.strip():
            self._failure_code = "response_content"
            raise RuntimeError("provider response content is empty")
        if len(response.content.encode("utf-8")) > MAX_RESPONSE_BYTES:
            self._failure_code = "response_size"
            raise RuntimeError("provider response exceeds bounded size")
        self._response = response
        return response


class _FixedGemini36CriticRouter:
    """One-shot router whose catalog and selection contain only Gemini 3.6 Flash."""

    def __init__(self, router: ModelRouter, *, adversary: bool = False) -> None:
        self._adversary = adversary
        entry = ModelCatalogEntry(
            model_id=GEMINI36_CRITIC_MODEL,
            provider_id=ProviderId.GOOGLE,
            family=ModelFamily.GEMINI,
            live_verified=True,
            available=True,
            admission_state=AdmissionState.ADMITTED,
            supports_tools=False,
            supports_json=False,
        )
        catalog = ModelCatalog([entry])
        self.catalog = catalog
        self.credentials = router.credentials
        self.state_db = router.state_db
        self._router = ModelRouter(
            credentials=self.credentials,
            catalog=catalog,
            state_db=self.state_db,
        )
        self._used = False
        self._response: RouterResponse | None = None
        self._failure_observation: Mapping[str, object] | None = None
        self._failure_code: str | None = None
        self._lock = threading.Lock()

    @property
    def response(self) -> RouterResponse | None:
        """Return the single validated response, when routing succeeded."""

        return self._response

    @property
    def failure_observation(self) -> Mapping[str, object] | None:
        """Return bounded facts for this router's own normalized failure."""

        return self._failure_observation

    @property
    def failure_code(self) -> str | None:
        """Return the bounded predicate for a local post-response rejection."""

        if self._failure_code is not None and not _is_gemini36_failure_code(
            self._failure_code
        ):
            raise RuntimeError("Gemini 3.6 response failure code is invalid")
        return self._failure_code

    def route(self, request: TaskRequest) -> RouterResponse:
        if type(request) is not TaskRequest:
            raise RuntimeError("Gemini 3.6 gateway request class is invalid")
        if request.explicit_model != GEMINI36_CRITIC_MODEL:
            raise RuntimeError("model is outside the fixed Gemini 3.6 critic binding")
        expected_data_class = DataClass.INTERNAL if self._adversary else DataClass.PUBLIC
        expected_task_class = TaskClass.AUDIT if self._adversary else TaskClass.ROUTINE
        if (
            request.data_class is not expected_data_class
            or request.task_class is not expected_task_class
        ):
            raise RuntimeError("Gemini 3.6 request classification is invalid")
        if (
            request.stream
            or request.tools is not None
            or request.tool_choice is not None
        ):
            raise RuntimeError("streaming and tools are forbidden")
        if request.require_tools or request.require_json:
            raise RuntimeError(
                "streaming, tools, and unsupported requirements are forbidden"
            )
        with self._lock:
            if self._used:
                raise RuntimeError("one request limit exceeded")
            self._used = True
        try:
            response = self._router.route(
                replace(request, retry_policy=RetryPolicy.NONE, allow_fallback=False)
            )
        except NormalizedError as exc:
            self._failure_observation = MappingProxyType(
                _gemini36_provider_failure_observation(exc)
            )
            raise
        self._failure_observation = MappingProxyType(
            _gemini36_post_response_failure_observation(response)
        )
        if type(response) is not RouterResponse:
            self._failure_code = "response_type"
            raise RuntimeError("Gemini 3.6 critic response attribution mismatch")
        if (
            response.provider_id is not ProviderId.GOOGLE
            or response.model_id != GEMINI36_CRITIC_MODEL
            or response.actual_model != GEMINI36_CRITIC_MODEL
            or response.actual_family is not ModelFamily.GEMINI
            or response.family is not ModelFamily.GEMINI
        ):
            self._failure_code = "response_provider_identity"
            raise RuntimeError("Gemini 3.6 critic response attribution mismatch")
        if response.fallback_chain != [
            f"{GEMINI36_CRITIC_PROVIDER}:{GEMINI36_CRITIC_MODEL}"
        ]:
            self._failure_code = "response_fallback_chain"
            raise RuntimeError("Gemini 3.6 critic response attribution mismatch")
        if response.attempts != 1:
            self._failure_code = "response_attempt_count"
            raise RuntimeError("Gemini 3.6 critic response attribution mismatch")
        if response.tool_calls:
            self._failure_code = "response_completion_shape:tool_calls_present"
            raise RuntimeError("Gemini 3.6 critic response attribution mismatch")
        if response.finish_reason != "stop":
            self._failure_code = "response_completion_shape:finish_reason_not_stop"
            raise RuntimeError("Gemini 3.6 critic response attribution mismatch")
        if not isinstance(response.content, str) or not response.content.strip():
            self._failure_code = "response_content"
            raise RuntimeError("Gemini 3.6 provider response content is invalid")
        try:
            response_size = len(response.content.encode("utf-8"))
        except UnicodeEncodeError:
            self._failure_code = "response_size"
            raise RuntimeError("Gemini 3.6 provider response content is invalid") from None
        if response_size > MAX_RESPONSE_BYTES:
            self._failure_code = "response_size"
            raise RuntimeError("Gemini 3.6 provider response content is invalid")
        self._failure_observation = None
        self._response = response
        return response


def _parse_provider_response(raw: bytes) -> str:
    if not raw or len(raw) > MAX_RESPONSE_BYTES:
        raise RuntimeError("gateway response is empty or oversized")
    try:
        document = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError("gateway response is not strict JSON") from exc
    if not isinstance(document, dict):
        raise RuntimeError("gateway response envelope is malformed")
    if (
        document.get("object") != "chat.completion"
        or document.get("model") != MODEL
        or document.get("provider") != PROVIDER
        or document.get("system_fingerprint") != f"paeos-router-{FAMILY}"
        or document.get("fallback_chain") != [f"{PROVIDER}:{MODEL}"]
    ):
        raise RuntimeError("gateway response attribution is malformed")
    choices = document.get("choices")
    if (
        not isinstance(choices, list)
        or len(choices) != 1
        or not isinstance(choices[0], dict)
    ):
        raise RuntimeError("gateway choices are malformed")
    choice = choices[0]
    message = choice.get("message")
    if choice.get("finish_reason") != "stop" or not isinstance(message, dict):
        raise RuntimeError("gateway completion did not stop normally")
    content = message.get("content")
    if (
        message.get("role") != "assistant"
        or not isinstance(content, str)
        or not content.strip()
    ):
        raise RuntimeError("gateway message is malformed")
    if message.get("tool_calls"):
        raise RuntimeError("gateway response contains tool calls")
    return content


def verify_bundle_manifest(bundle_root: Path, manifest_path: Path) -> None:
    """Refuse service startup unless every installed source digest matches its manifest."""

    bundle_root = _safe_path(bundle_root, label="bundle root")
    manifest_path = _safe_path(manifest_path, label="bundle manifest")
    document = json.loads(manifest_path.read_text(encoding="utf-8"))
    if (
        not isinstance(document, dict)
        or document.get("schema") != "paeos.trusted-worker-bundle/1"
    ):
        raise RuntimeError("trusted bundle manifest schema is invalid")
    files = document.get("files")
    if not isinstance(files, dict) or not files:
        raise RuntimeError("trusted bundle manifest files are missing")
    for relative, expected in files.items():
        if not isinstance(relative, str) or not isinstance(expected, str):
            raise RuntimeError("trusted bundle manifest entry is malformed")
        candidate = _safe_path(bundle_root / relative, label="bundle file")
        if not candidate.is_file() or _sha256(candidate.read_bytes()) != expected:
            raise RuntimeError("trusted bundle manifest verification failed")


def _capability_id(value: object) -> str | None:
    return (
        value if isinstance(value, str) and CAPABILITY_ID_RE.fullmatch(value) else None
    )


class _ProcessFailure(RuntimeError):
    """A failed child is reported with bounded process facts, never stream content."""

    _FIELDS: ClassVar[frozenset[str]] = frozenset(
        {
            "lifecycle_state",
            "exit_code",
            "stdout_bytes",
            "stdout_sha256",
            "stderr_bytes",
            "stderr_sha256",
        }
    )

    def __init__(
        self,
        observation: dict[str, object],
        *,
        error_code: str | None = None,
    ) -> None:
        if set(observation) != self._FIELDS:
            raise RuntimeError("process failure observation fields are not exact")
        if error_code is not None and (
            not isinstance(error_code, str)
            or error_code not in GEMINI38_RESPONSE_CONTRACT_FAILURE_CODES
        ):
            raise RuntimeError("process failure error code is invalid")
        if (
            not isinstance(observation["lifecycle_state"], str)
            or not isinstance(observation["exit_code"], int)
            or isinstance(observation["exit_code"], bool)
            or not isinstance(observation["stdout_bytes"], int)
            or isinstance(observation["stdout_bytes"], bool)
            or not isinstance(observation["stderr_bytes"], int)
            or isinstance(observation["stderr_bytes"], bool)
            or not isinstance(observation["stdout_sha256"], str)
            or not isinstance(observation["stderr_sha256"], str)
            or len(observation["stdout_sha256"]) != 64
            or len(observation["stderr_sha256"]) != 64
        ):
            raise RuntimeError("process failure observation is malformed")
        self.observation = dict(observation)
        self.error_code = error_code
        super().__init__("confined provider process did not return successfully")


class _ProviderFailure(RuntimeError):
    """An exact provider failure whose observation contains no provider content."""

    def __init__(self, observation: Mapping[str, object]) -> None:
        expected = {
            "schema",
            "provider_id",
            "model_id",
            "error_type",
            "http_status",
            "retry_after",
            "response_bytes",
            "response_sha256",
            "raw_response_persisted",
        }
        if set(observation) != expected:
            raise RuntimeError("provider failure observation fields are not exact")
        self._observation = MappingProxyType(dict(observation))
        super().__init__("fixed NVIDIA provider request failed")

    @property
    def observation(self) -> Mapping[str, object]:
        return self._observation


class _Gemini38ProviderFailure(_ProviderFailure):
    """A sanitized exact Google/Gemini failure exposed by ``handle``."""

    def __init__(self, observation: Mapping[str, object]) -> None:
        super().__init__(observation)
        self.args = ("fixed Google Gemini 3.8 provider request failed",)


class _Gemini36ProviderFailure(_ProviderFailure):
    """A sanitized exact Google/Gemini 3.6 failure exposed by ``handle``."""

    def __init__(
        self,
        observation: Mapping[str, object],
        *,
        error_code: str | None = None,
    ) -> None:
        if error_code is not None and not _is_gemini36_failure_code(error_code):
            raise RuntimeError("Gemini 3.6 provider failure code is invalid")
        super().__init__(observation)
        self.error_code = error_code
        self.args = ("fixed Google Gemini 3.6 provider request failed",)


def _failure_code(exc: BaseException) -> str:
    if isinstance(exc, _ProcessFailure) and exc.error_code is not None:
        return exc.error_code
    chain: list[str] = []
    current: BaseException | None = exc
    while current is not None and len(chain) < 8:
        chain.append(str(current).lower())
        current = current.__cause__
    for text in reversed(chain):
        if "confinement" in text or "sandbox" in text or "policy" in text:
            return "confinement_failure"
        if "cleanup" in text or "workspace" in text:
            return "cleanup_failure"
        if "process" in text or "launch" in text or "executable" in text:
            return "process_launch_failure"
        if "gateway" in text or "response" in text:
            return "gateway_response_failure"
        if (
            "credential" in text
            or "route" in text
            or "admitted" in text
            or "provider" in text
        ):
            return "provider_or_route_failure"
    return "trusted_service_failure"


class TrustedProviderService:
    def __init__(
        self,
        *,
        socket_path: Path,
        state_root: Path,
        public_key_path: Path,
        queue_root: Path | None = None,
        response_signing_key: SigningKey | None = None,
    ) -> None:
        # Offline injection only. No operational response identity is inferred or created.
        if not isinstance(response_signing_key, SigningKey):
            raise RuntimeError("provider response signing identity is unavailable")
        self._response_signing_key = response_signing_key
        self.socket_path = _safe_path(socket_path, label="launcher socket")
        self.state_root = _safe_path(state_root, label="launcher state root")
        self.public_key_path = _safe_path(public_key_path, label="launcher public key")
        self.queue_root = _safe_path(
            queue_root if queue_root is not None else self.socket_path.parent / "queue",
            label="launcher queue root",
        )
        self.state_root.mkdir(mode=0o700, parents=True, exist_ok=True)
        os.chmod(self.state_root, 0o700)
        raw_key = self.public_key_path.read_text(encoding="ascii").strip()
        if len(raw_key) != 64:
            raise RuntimeError("launcher verification key is malformed")
        try:
            self._verify_key = VerifyKey(bytes.fromhex(raw_key))
        except ValueError as exc:
            raise RuntimeError("launcher verification key is malformed") from exc
        self._seen: set[str] = set()
        self._seen_lock = threading.Lock()

    def _signed_response(self, response: dict[str, object], request_bytes: bytes) -> bytes:
        payload = {
            "schema": "paeos.trusted-worker-signed-response/1",
            "request_sha256": _sha256(request_bytes),
            "response": response,
        }
        signature = self._response_signing_key.sign(
            b"PAEOS-PROVIDER-RESPONSE-V1\0" + _canonical_bytes(payload)
        ).signature.hex()
        return _canonical_bytes({"payload": payload, "signature": signature})

    def process_queue(self) -> None:
        self.queue_root.mkdir(mode=0o700, parents=True, exist_ok=True)
        os.chmod(self.queue_root, 0o700)
        for request_path in sorted(self.queue_root.glob("*.request.json")):
            if request_path.is_symlink() or not request_path.is_file():
                continue
            name = request_path.name[: -len(".request.json")]
            if CAPABILITY_ID_RE.fullmatch(name) is None:
                continue
            try:
                raw = request_path.read_bytes()
                if len(raw) > MAX_FRAME_BYTES:
                    raise RuntimeError("capability frame exceeded bounded size")
                response = self.handle(raw)
                response_doc = json.loads(response.decode("utf-8"))
                response_doc = response_doc["payload"]["response"]
                response_id = (
                    _capability_id(response_doc.get("capability_id"))
                    if isinstance(response_doc, dict)
                    else None
                )
                if response_id != name:
                    raise RuntimeError("capability response attribution mismatch")
                response_path = self.queue_root / f"{name}.response.json"
                temporary_path = self.queue_root / f".{name}.response.tmp"
                if response_path.exists() or temporary_path.exists():
                    request_path.unlink()
                    continue
                _write_exclusive(temporary_path, response)
                os.replace(temporary_path, response_path)
                request_path.unlink()
            except Exception:
                # The request remains for a bounded retry only when its response could not be
                # attributed. Invalid capabilities never become a successful response.
                continue

    def _validate_capability(self, document: object) -> tuple[dict[str, object], str]:
        if not isinstance(document, dict):
            raise RuntimeError("capability envelope is malformed")
        signature = document.pop("signature", None)
        if not isinstance(signature, str) or len(signature) != 128:
            raise RuntimeError("capability signature is malformed")
        try:
            signature_bytes = bytes.fromhex(signature)
        except ValueError as exc:
            raise RuntimeError("capability signature is malformed") from exc
        if len(signature_bytes) != 64:
            raise RuntimeError("capability signature is malformed")
        try:
            self._verify_key.verify(_canonical_bytes(document), signature_bytes)
        except BadSignatureError as exc:
            raise RuntimeError("capability signature is not valid") from exc
        required = {
            "schema",
            "operation",
            "capability_id",
            "issued_at",
            "expires_at",
            "provider_id",
            "model_id",
            "model_family",
            "data_class",
            "task_class",
            "prompt",
        }
        if set(document) != required or document.get("schema") != CAPABILITY_SCHEMA:
            raise RuntimeError("capability fields are not exact")
        capability_id = _capability_id(document.get("capability_id"))
        if capability_id is None or document.get("operation") != OPERATION:
            raise RuntimeError("capability operation is invalid")
        if (
            document.get("provider_id") != PROVIDER
            or document.get("model_id") != MODEL
            or document.get("model_family") != FAMILY
            or document.get("data_class") != DataClass.PUBLIC.value
            or document.get("task_class") != TaskClass.ROUTINE.value
        ):
            raise RuntimeError("capability route or data class is invalid")
        issued = document.get("issued_at")
        expires = document.get("expires_at")
        if (
            isinstance(issued, bool)
            or isinstance(expires, bool)
            or not isinstance(issued, (int, float))
            or not isinstance(expires, (int, float))
            or expires <= issued
            or expires - issued > CAPABILITY_TTL_SECONDS
            or issued > time.time() + 15.0
            or expires < time.time()
        ):
            raise RuntimeError("capability is expired or outside its bounded lifetime")
        prompt = document.get("prompt")
        if not isinstance(prompt, str) or not prompt.strip() or "\x00" in prompt:
            raise RuntimeError("capability prompt is malformed")
        if len(prompt.encode("utf-8")) > MAX_PROMPT_BYTES:
            raise RuntimeError("capability prompt is oversized")
        with self._seen_lock:
            if capability_id in self._seen:
                raise RuntimeError("capability replay was rejected")
            self._seen.add(capability_id)
            if len(self._seen) > 2048:
                self._seen.clear()
                self._seen.add(capability_id)
        return document, capability_id

    def _validate_cline_capability(
        self, document: object
    ) -> tuple[dict[str, object], str]:
        if not isinstance(document, dict):
            raise RuntimeError("Cline capability envelope is malformed")
        signature = document.pop("signature", None)
        if not isinstance(signature, str) or len(signature) != 128:
            raise RuntimeError("Cline capability signature is malformed")
        try:
            signature_bytes = bytes.fromhex(signature)
            self._verify_key.verify(_canonical_bytes(document), signature_bytes)
        except (ValueError, BadSignatureError) as exc:
            raise RuntimeError("Cline capability signature is not valid") from exc
        required = {
            "schema",
            "operation",
            "capability_id",
            "task_id",
            "goal_id",
            "run_id",
            "stage",
            "role",
            "issued_at",
            "expires_at",
            "provider_id",
            "model_id",
            "model_family",
            "prompt",
        }
        if (
            set(document) != required
            or document.get("schema") != CLINE_CAPABILITY_SCHEMA
        ):
            raise RuntimeError("Cline capability fields are not exact")
        capability_id = _capability_id(document.get("capability_id"))
        if capability_id is None or document.get("operation") != CLINE_OPERATION:
            raise RuntimeError("Cline capability operation is invalid")
        if (
            document.get("provider_id"),
            document.get("model_id"),
            document.get("model_family"),
            document.get("role"),
        ) != (CLINE_PROVIDER, CLINE_MODEL, CLINE_FAMILY, "CRITIC"):
            raise RuntimeError("Cline capability route or role is invalid")
        for name in ("task_id", "goal_id", "run_id"):
            value = document.get(name)
            if not isinstance(value, str) or not value.strip() or "\x00" in value:
                raise RuntimeError("Cline task identity is malformed")
        if document.get("stage") != "CRITIQUE":
            raise RuntimeError("Cline capability stage is not CRITIQUE")
        issued, expires = document.get("issued_at"), document.get("expires_at")
        now = time.time()
        if (
            isinstance(issued, bool)
            or isinstance(expires, bool)
            or not isinstance(issued, (int, float))
            or not isinstance(expires, (int, float))
            or expires <= issued
            or expires - issued > CAPABILITY_TTL_SECONDS
            or issued > now + 15.0
            or expires < now
        ):
            raise RuntimeError(
                "Cline capability is expired or outside its bounded lifetime"
            )
        prompt = document.get("prompt")
        if (
            not isinstance(prompt, str)
            or not prompt.strip()
            or "\x00" in prompt
            or len(prompt.encode("utf-8")) > MAX_PROMPT_BYTES
        ):
            raise RuntimeError("Cline capability prompt is malformed")
        with self._seen_lock:
            if capability_id in self._seen:
                raise RuntimeError("Cline capability replay was rejected")
            self._seen.add(capability_id)
        return document, capability_id

    def _validate_nvidia_critic_capability(
        self, document: object
    ) -> tuple[dict[str, object], str]:
        if not isinstance(document, dict):
            raise RuntimeError("NVIDIA critic capability envelope is malformed")
        signature = document.pop("signature", None)
        if not isinstance(signature, str) or SIGNATURE_RE.fullmatch(signature) is None:
            raise RuntimeError("NVIDIA critic capability signature is malformed")
        try:
            self._verify_key.verify(
                _canonical_bytes(document), bytes.fromhex(signature)
            )
        except (ValueError, BadSignatureError) as exc:
            raise RuntimeError(
                "NVIDIA critic capability signature is not valid"
            ) from exc
        required = {
            "schema",
            "operation",
            "capability_id",
            "task_id",
            "goal_id",
            "run_id",
            "stage",
            "role",
            "issued_at",
            "expires_at",
            "provider_id",
            "model_id",
            "model_family",
            "prompt",
        }
        if (
            set(document) != required
            or document.get("schema") != NVIDIA_CRITIC_CAPABILITY_SCHEMA
        ):
            raise RuntimeError("NVIDIA critic capability fields are not exact")
        capability_id = _capability_id(document.get("capability_id"))
        if capability_id is None or document.get("operation") != "critic":
            raise RuntimeError("NVIDIA critic capability operation is invalid")
        if (
            document.get("stage") != "CRITIQUE"
            or document.get("role") != "CRITIC"
            or document.get("provider_id") != NVIDIA_CRITIC_PROVIDER
            or document.get("model_id") != NVIDIA_CRITIC_MODEL
            or document.get("model_family") != NVIDIA_CRITIC_FAMILY
        ):
            raise RuntimeError("NVIDIA critic capability route is invalid")
        for name in ("task_id", "goal_id", "run_id"):
            value = document.get(name)
            if not isinstance(value, str) or not value.strip() or "\x00" in value:
                raise RuntimeError("NVIDIA critic task identity is malformed")
        issued, expires = document.get("issued_at"), document.get("expires_at")
        now = time.time()
        if (
            isinstance(issued, bool)
            or isinstance(expires, bool)
            or not isinstance(issued, (int, float))
            or not isinstance(expires, (int, float))
            or not math.isfinite(issued)
            or not math.isfinite(expires)
            or expires <= issued
            or expires - issued > CAPABILITY_TTL_SECONDS
            or issued > now + 15.0
            or expires <= now
        ):
            raise RuntimeError(
                "NVIDIA critic capability is expired or outside its bounded lifetime"
            )
        prompt = document.get("prompt")
        if (
            not isinstance(prompt, str)
            or not prompt.strip()
            or "\x00" in prompt
            or len(prompt.encode("utf-8")) > MAX_PROMPT_BYTES
        ):
            raise RuntimeError("NVIDIA critic capability prompt is malformed")
        with self._seen_lock:
            if capability_id in self._seen:
                raise RuntimeError("NVIDIA critic capability replay was rejected")
            self._seen.add(capability_id)
        return document, capability_id

    def _validate_gemini38_critic_capability(
        self, document: object
    ) -> tuple[dict[str, object], str]:
        if not isinstance(document, dict):
            raise RuntimeError("Gemini 3.8 critic capability envelope is malformed")
        signature = document.pop("signature", None)
        if not isinstance(signature, str) or SIGNATURE_RE.fullmatch(signature) is None:
            raise RuntimeError("Gemini 3.8 critic capability signature is malformed")
        try:
            self._verify_key.verify(
                _canonical_bytes(document), bytes.fromhex(signature)
            )
        except (ValueError, BadSignatureError) as exc:
            raise RuntimeError(
                "Gemini 3.8 critic capability signature is not valid"
            ) from exc
        required = {
            "schema",
            "operation",
            "capability_id",
            "task_id",
            "goal_id",
            "run_id",
            "stage",
            "role",
            "issued_at",
            "expires_at",
            "provider_id",
            "model_id",
            "model_family",
            "prompt",
            "builder_family",
            "critic_family",
            "read_only",
            "allow_tools",
            "allow_fallback",
            "require_confinement",
        }
        if (
            set(document) != required
            or document.get("schema") != GEMINI38_CRITIC_CAPABILITY_SCHEMA
        ):
            raise RuntimeError("Gemini 3.8 critic capability fields are not exact")
        capability_id = _capability_id(document.get("capability_id"))
        if (
            capability_id is None
            or document.get("operation") != GEMINI38_CRITIC_OPERATION
        ):
            raise RuntimeError("Gemini 3.8 critic capability operation is invalid")
        if (
            document.get("role") != "CRITIC"
            or document.get("provider_id") != GEMINI38_CRITIC_PROVIDER
            or document.get("model_id") != GEMINI38_CRITIC_MODEL
            or document.get("model_family") != GEMINI38_CRITIC_FAMILY
            or document.get("critic_family") != GEMINI38_CRITIC_FAMILY
            or document.get("read_only") is not True
            or document.get("allow_tools") is not False
            or document.get("allow_fallback") is not False
            or document.get("require_confinement") is not True
        ):
            raise RuntimeError(
                "Gemini 3.8 critic capability route or policy is invalid"
            )
        for name in ("task_id", "goal_id", "run_id", "stage", "builder_family"):
            value = document.get(name)
            if (
                not isinstance(value, str)
                or not value.strip()
                or "\x00" in value
                or len(value.encode("utf-8")) > MAX_PROMPT_BYTES
            ):
                raise RuntimeError("Gemini 3.8 critic capability identity is malformed")
        if document.get("builder_family") == GEMINI38_CRITIC_FAMILY:
            raise RuntimeError(
                "Gemini 3.8 critic capability violates A-08 independence"
            )
        issued, expires = document.get("issued_at"), document.get("expires_at")
        now = time.time()
        if (
            isinstance(issued, bool)
            or isinstance(expires, bool)
            or not isinstance(issued, (int, float))
            or not isinstance(expires, (int, float))
            or not math.isfinite(issued)
            or not math.isfinite(expires)
            or expires <= issued
            or expires - issued > CAPABILITY_TTL_SECONDS
            or issued > now + 15.0
            or expires <= now
        ):
            raise RuntimeError(
                "Gemini 3.8 critic capability is expired or outside its bounded lifetime"
            )
        prompt = document.get("prompt")
        if (
            not isinstance(prompt, str)
            or not prompt.strip()
            or "\x00" in prompt
            or len(prompt.encode("utf-8")) > MAX_PROMPT_BYTES
        ):
            raise RuntimeError("Gemini 3.8 critic capability prompt is malformed")
        with self._seen_lock:
            if capability_id in self._seen:
                raise RuntimeError("Gemini 3.8 critic capability replay was rejected")
            self._seen.add(capability_id)
        return document, capability_id

    def _validate_gemini38_adversary_capability(
        self, document: object
    ) -> tuple[dict[str, object], str]:
        """Verify one exact signed Gemini 3.8 adversary capability before provider I/O."""
        if not isinstance(document, dict):
            raise RuntimeError("Gemini 3.8 adversary capability envelope is malformed")
        signature = document.pop("signature", None)
        if not isinstance(signature, str) or SIGNATURE_RE.fullmatch(signature) is None:
            raise RuntimeError("Gemini 3.8 adversary capability signature is malformed")
        try:
            self._verify_key.verify(_canonical_bytes(document), bytes.fromhex(signature))
        except (ValueError, BadSignatureError) as exc:
            raise RuntimeError("Gemini 3.8 adversary capability signature is not valid") from exc
        required = {
            "schema", "operation", "capability_id", "task_id", "goal_id", "run_id", "stage",
            "role", "issued_at", "expires_at", "provider_id", "model_id", "model_family",
            "prompt", "builder_family", "adversary_family", "read_only", "allow_tools",
            "allow_fallback", "require_confinement",
        }
        if set(document) != required or document.get("schema") != GEMINI38_ADVERSARY_CAPABILITY_SCHEMA:
            raise RuntimeError("Gemini 3.8 adversary capability fields are not exact")
        capability_id = _capability_id(document.get("capability_id"))
        if capability_id is None or document.get("operation") != GEMINI38_ADVERSARY_OPERATION:
            raise RuntimeError("Gemini 3.8 adversary capability operation is invalid")
        if (
            document.get("role") != "ADVERSARY"
            or document.get("stage") != "ADVERSARIAL_REVIEW"
            or document.get("provider_id") != GEMINI38_ADVERSARY_PROVIDER
            or document.get("model_id") != GEMINI38_ADVERSARY_MODEL
            or document.get("model_family") != GEMINI38_ADVERSARY_FAMILY
            or document.get("adversary_family") != GEMINI38_ADVERSARY_FAMILY
            or document.get("read_only") is not True
            or document.get("allow_tools") is not False
            or document.get("allow_fallback") is not False
            or document.get("require_confinement") is not True
        ):
            raise RuntimeError("Gemini 3.8 adversary capability route or policy is invalid")
        for name in ("task_id", "goal_id", "run_id", "stage", "builder_family"):
            value = document.get(name)
            if not isinstance(value, str) or not value.strip() or "\x00" in value or len(value.encode("utf-8")) > MAX_PROMPT_BYTES:
                raise RuntimeError("Gemini 3.8 adversary capability identity is malformed")
        if document.get("builder_family") == GEMINI38_ADVERSARY_FAMILY:
            raise RuntimeError("Gemini 3.8 adversary capability violates A-08 independence")
        prompt = document.get("prompt")
        if not isinstance(prompt, str) or not prompt.strip() or "\x00" in prompt or "context/" not in prompt or len(prompt.encode("utf-8")) > MAX_PROMPT_BYTES:
            raise RuntimeError("Gemini 3.8 adversary capability prompt is malformed")
        issued, expires = document.get("issued_at"), document.get("expires_at")
        now = time.time()
        if (
            isinstance(issued, bool) or isinstance(expires, bool)
            or not isinstance(issued, (int, float)) or not isinstance(expires, (int, float))
            or not math.isfinite(issued) or not math.isfinite(expires)
            or expires <= issued or expires - issued > CAPABILITY_TTL_SECONDS
            or issued > now + 15.0 or expires <= now
        ):
            raise RuntimeError("Gemini 3.8 adversary capability is expired or outside its bounded lifetime")
        with self._seen_lock:
            if capability_id in self._seen:
                raise RuntimeError("Gemini 3.8 adversary capability replay was rejected")
            self._seen.add(capability_id)
        return document, capability_id

    def _validate_gemini36_adversary_capability(
        self, document: object
    ) -> tuple[dict[str, object], str]:
        """Verify one exact signed Gemini 3.6 adversary capability before provider I/O."""
        if not isinstance(document, dict):
            raise RuntimeError("Gemini 3.6 adversary capability envelope is malformed")
        signature = document.pop("signature", None)
        if not isinstance(signature, str) or SIGNATURE_RE.fullmatch(signature) is None:
            raise RuntimeError("Gemini 3.6 adversary capability signature is malformed")
        try:
            self._verify_key.verify(_canonical_bytes(document), bytes.fromhex(signature))
        except (ValueError, BadSignatureError) as exc:
            raise RuntimeError("Gemini 3.6 adversary capability signature is not valid") from exc
        required = {
            "schema", "operation", "capability_id", "task_id", "goal_id", "run_id", "stage",
            "role", "issued_at", "expires_at", "provider_id", "model_id", "model_family",
            "prompt", "builder_family", "adversary_family", "read_only", "allow_tools",
            "allow_fallback", "require_confinement",
        }
        if set(document) != required or document.get("schema") != GEMINI36_ADVERSARY_CAPABILITY_SCHEMA:
            raise RuntimeError("Gemini 3.6 adversary capability fields are not exact")
        capability_id = _capability_id(document.get("capability_id"))
        if capability_id is None or document.get("operation") != GEMINI36_ADVERSARY_OPERATION:
            raise RuntimeError("Gemini 3.6 adversary capability operation is invalid")
        if (
            document.get("role") != "ADVERSARY"
            or document.get("stage") != "ADVERSARIAL_REVIEW"
            or document.get("provider_id") != GEMINI36_ADVERSARY_PROVIDER
            or document.get("model_id") != GEMINI36_ADVERSARY_MODEL
            or document.get("model_family") != GEMINI36_ADVERSARY_FAMILY
            or document.get("adversary_family") != GEMINI36_ADVERSARY_FAMILY
            or document.get("builder_family") == GEMINI36_ADVERSARY_FAMILY
            or document.get("read_only") is not True
            or document.get("allow_tools") is not False
            or document.get("allow_fallback") is not False
            or document.get("require_confinement") is not True
        ):
            raise RuntimeError("Gemini 3.6 adversary capability route or policy is invalid")
        for name in ("task_id", "goal_id", "run_id", "stage", "builder_family", "prompt"):
            value = document.get(name)
            maximum = GEMINI36_ADVERSARY_MAX_PROMPT_BYTES if name == "prompt" else MAX_PROMPT_BYTES
            if not isinstance(value, str) or not value.strip() or "\0" in value or len(value.encode()) > maximum:
                raise RuntimeError("Gemini 3.6 adversary capability content is malformed")
        if "context/" not in str(document.get("prompt")):
            raise RuntimeError("Gemini 3.6 adversary capability requires sealed context")
        issued, expires, now = document.get("issued_at"), document.get("expires_at"), time.time()
        if (
            isinstance(issued, bool) or isinstance(expires, bool)
            or not isinstance(issued, (int, float)) or not isinstance(expires, (int, float))
            or not math.isfinite(issued) or not math.isfinite(expires)
            or expires <= issued or expires - issued > CAPABILITY_TTL_SECONDS
            or issued > now + 15 or expires <= now
        ):
            raise RuntimeError("Gemini 3.6 adversary capability is expired or outside its bounded lifetime")
        with self._seen_lock:
            if capability_id in self._seen:
                raise RuntimeError("Gemini 3.6 adversary capability replay was rejected")
            self._seen.add(capability_id)
        return document, capability_id

    def _validate_gemini36_critic_capability(
        self, document: object
    ) -> tuple[dict[str, object], str]:
        """Verify the exact signed, stage-agnostic Gemini 3.6 CRITIC grant once."""
        if not isinstance(document, dict):
            raise RuntimeError("Gemini 3.6 critic capability envelope is malformed")
        signature = document.pop("signature", None)
        if not isinstance(signature, str) or SIGNATURE_RE.fullmatch(signature) is None:
            raise RuntimeError("Gemini 3.6 critic capability signature is malformed")
        try:
            self._verify_key.verify(
                _canonical_bytes(document), bytes.fromhex(signature)
            )
        except (ValueError, BadSignatureError) as exc:
            raise RuntimeError(
                "Gemini 3.6 critic capability signature is not valid"
            ) from exc
        required = {
            "schema",
            "operation",
            "capability_id",
            "task_id",
            "goal_id",
            "run_id",
            "stage",
            "role",
            "issued_at",
            "expires_at",
            "provider_id",
            "model_id",
            "model_family",
            "prompt",
            "builder_family",
            "critic_family",
            "read_only",
            "allow_tools",
            "allow_fallback",
            "require_confinement",
        }
        if (
            set(document) != required
            or document.get("schema") != GEMINI36_CRITIC_CAPABILITY_SCHEMA
        ):
            raise RuntimeError("Gemini 3.6 critic capability fields are not exact")
        capability_id = _capability_id(document.get("capability_id"))
        if (
            capability_id is None
            or document.get("operation") != "critic"
            or document.get("role") != "CRITIC"
            or document.get("provider_id") != GEMINI36_CRITIC_PROVIDER
            or document.get("model_id") != GEMINI36_CRITIC_MODEL
            or document.get("model_family") != GEMINI36_CRITIC_FAMILY
            or document.get("critic_family") != GEMINI36_CRITIC_FAMILY
            or document.get("builder_family") == GEMINI36_CRITIC_FAMILY
            or document.get("read_only") is not True
            or document.get("allow_tools") is not False
            or document.get("allow_fallback") is not False
            or document.get("require_confinement") is not True
        ):
            raise RuntimeError(
                "Gemini 3.6 critic capability route or policy is invalid"
            )
        for name in (
            "task_id",
            "goal_id",
            "run_id",
            "stage",
            "builder_family",
            "prompt",
        ):
            value = document.get(name)
            if (
                not isinstance(value, str)
                or not value.strip()
                or "\0" in value
                or len(value.encode()) > MAX_PROMPT_BYTES
            ):
                raise RuntimeError("Gemini 3.6 critic capability content is malformed")
        issued, expires, now = (
            document.get("issued_at"),
            document.get("expires_at"),
            time.time(),
        )
        if (
            isinstance(issued, bool)
            or isinstance(expires, bool)
            or not isinstance(issued, (int, float))
            or not isinstance(expires, (int, float))
            or not math.isfinite(issued)
            or not math.isfinite(expires)
            or expires <= issued
            or expires - issued > CAPABILITY_TTL_SECONDS
            or issued > now + 15
            or expires <= now
        ):
            raise RuntimeError(
                "Gemini 3.6 critic capability is expired or outside its bounded lifetime"
            )
        with self._seen_lock:
            if capability_id in self._seen:
                raise RuntimeError("Gemini 3.6 critic capability replay was rejected")
            self._seen.add(capability_id)
        return document, capability_id

    def _run_gemini36_critic_provider(
        self,
        capability: dict[str, object],
        capability_id: str,
        signature: str,
        *,
        adversary: bool = False,
    ) -> dict[str, object]:
        """Redeem one fixed Gemini 3.6 capability through parent-owned Google transport."""
        response_role = "ADVERSARY" if adversary else "CRITIC"
        response_operation = GEMINI36_ADVERSARY_OPERATION if adversary else "critic"
        response_schema = (
            "paeos.parent-google-gemini36-adversary-observation/1"
            if adversary
            else "paeos.parent-google-gemini36-critic-observation/1"
        )
        response_model = GEMINI36_ADVERSARY_MODEL if adversary else GEMINI36_CRITIC_MODEL
        response_provider = GEMINI36_ADVERSARY_PROVIDER if adversary else GEMINI36_CRITIC_PROVIDER
        response_family = GEMINI36_ADVERSARY_FAMILY if adversary else GEMINI36_CRITIC_FAMILY
        credentials = CredentialStore()
        if not credentials.has_key(ProviderId.GOOGLE):
            raise RuntimeError("parent-owned Google credential is unavailable")
        task_root = _safe_path(
            self.state_root
            / ("gemini36-adversary-tasks" if adversary else "gemini36-critic-tasks")
            / capability_id,
            label=(
                "Gemini 3.6 adversary task workspace"
                if adversary
                else "Gemini 3.6 critic task workspace"
            ),
        )
        task_root.mkdir(mode=0o700, parents=True, exist_ok=False)
        os.chmod(task_root, 0o700)
        forbidden_root = self.state_root / "canary-forbidden" / capability_id
        control = task_root / "control"
        runtime_home, temp_root = task_root / ".home", task_root / ".tmp"
        control.mkdir(mode=0o700)
        request_path, config_path = control / "request.json", control / "curl.conf"
        state_path = task_root / "process-observation.json"
        task_bearer = hashlib.sha256(os.urandom(32)).hexdigest()
        server = None
        server_thread = None
        signed_capability = dict(capability)
        signed_capability["signature"] = signature
        request_sha256 = _sha256(_canonical_bytes(signed_capability))
        try:
            self._run_confinement_canary(task_root, capability_id, forbidden_root)
            router = ModelRouter(
                credentials=credentials,
                state_db=RouterStateDB(self.state_root / "router.sqlite3"),
            )
            fixed_router = _FixedGemini36CriticRouter(router, adversary=adversary)
            server = run_gateway_server(
                host="127.0.0.1", port=0, router=fixed_router, api_key=task_bearer
            )
            host, port = server.server_address[:2]
            if (
                host != "127.0.0.1"
                or not isinstance(port, int)
                or not 1 <= port <= 65535
            ):
                raise RuntimeError(
                    "Gemini 3.6 gateway did not bind exact loopback"
                )
            server_thread = threading.Thread(
                target=server.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True
            )
            server_thread.start()
            broker_url = f"http://127.0.0.1:{port}/v1/chat/completions"
            provider_request = {
                "model": response_model,
                "messages": [{"role": "user", "content": capability["prompt"]}],
                "data_class": (
                    DataClass.INTERNAL.value if adversary else DataClass.PUBLIC.value
                ),
                "task_class": (
                    TaskClass.AUDIT.value if adversary else TaskClass.ROUTINE.value
                ),
                "stream": False,
                "tools": None,
                "retry_policy": RetryPolicy.NONE.value,
                "allow_fallback": False,
                "max_tokens": (
                    GEMINI36_ADVERSARY_MAX_COMPLETION_TOKENS
                    if adversary
                    else GEMINI36_CRITIC_MAX_COMPLETION_TOKENS
                ),
                "temperature": 0.0,
            }
            _write_exclusive(request_path, _canonical_bytes(provider_request))
            _write_exclusive(
                config_path,
                (
                    f'url = "{broker_url}"\nrequest = "POST"\n'
                    f'header = "Authorization: Bearer {task_bearer}"\n'
                    'header = "Content-Type: application/json"\n'
                    f'data-binary = "@{request_path}"\nfail-with-body\nsilent\nshow-error\n'
                    "ipv4\nconnect-timeout = 5\nmax-time = 70\n"
                ).encode(),
            )
            policy = policy_for_worker(
                workspace=task_root,
                read_roots=(task_root,),
                write_roots=(task_root,),
                runtime_home=runtime_home,
                temp_root=temp_root,
                loopback_port=port,
            )
            environment = build_provider_environment(
                {},
                runtime_home=runtime_home,
                temp_root=temp_root,
                task_environment={
                    "PAEOS_TASK_BEARER": task_bearer,
                    "PAEOS_TASK_BROKER_URL": broker_url,
                },
            )
            environment_keys = {
                "HOME",
                "LANG",
                "LC_ALL",
                "PATH",
                "TMPDIR",
                "PAEOS_TASK_BEARER",
                "PAEOS_TASK_BROKER_URL",
            }
            if set(environment) != environment_keys:
                raise RuntimeError("Gemini 3.6 critic worker environment is not exact")
            if any(name.endswith("_API_KEY") for name in environment):
                raise RuntimeError("Google credential entered worker environment")
            argv = policy.wrap_argv(("/usr/bin/curl", "--config", str(config_path)))
            if task_bearer in "\0".join(argv):
                raise RuntimeError("task bearer entered worker argv")
            physical = run_bounded_process(
                argv,
                cwd=task_root,
                environment=environment,
                start_timeout_s=5.0,
                execution_timeout_s=75.0,
                state_path=state_path,
            )
            if (
                physical.lifecycle_state is not ProcessLifecycleState.RETURNED
                or physical.exit_code != 0
            ):
                if fixed_router.failure_observation is not None:
                    raise _Gemini36ProviderFailure(
                        fixed_router.failure_observation,
                        error_code=fixed_router.failure_code,
                    )
                raise _ProcessFailure(
                    {
                        "lifecycle_state": physical.lifecycle_state.value,
                        "exit_code": physical.exit_code,
                        "stdout_bytes": len(physical.stdout),
                        "stdout_sha256": _sha256(physical.stdout),
                        "stderr_bytes": len(physical.stderr),
                        "stderr_sha256": _sha256(physical.stderr),
                    }
                )
            bearer_bytes = task_bearer.encode("ascii")
            if bearer_bytes in physical.stdout or bearer_bytes in physical.stderr:
                raise RuntimeError("task bearer leaked into worker output")
            routed = fixed_router.response
            if routed is None:
                raise RuntimeError("Gemini 3.6 router response was not captured")
            try:
                raw_document = json.loads(physical.stdout.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise RuntimeError("Gemini 3.6 gateway response is not strict JSON") from exc
            choices = (
                raw_document.get("choices") if isinstance(raw_document, dict) else None
            )
            choice = (
                choices[0] if isinstance(choices, list) and len(choices) == 1 else None
            )
            message = choice.get("message") if isinstance(choice, dict) else None
            response_text = routed.content
            if (
                not isinstance(raw_document, dict)
                or raw_document.get("object") != "chat.completion"
                or raw_document.get("model") != response_model
                or raw_document.get("provider") != response_provider
                or raw_document.get("system_fingerprint") != "paeos-router-gemini"
                or raw_document.get("fallback_chain")
                != [f"{response_provider}:{response_model}"]
                or not isinstance(choice, dict)
                or choice.get("finish_reason") != "stop"
                or not isinstance(message, dict)
                or message.get("role") != "assistant"
                or message.get("content") != response_text
                or message.get("tool_calls")
                or not isinstance(response_text, str)
                or not response_text.strip()
                or len(response_text.encode()) > MAX_RESPONSE_BYTES
            ):
                raise RuntimeError("Gemini 3.6 gateway response attribution is malformed")
            if adversary:
                verdicts = [
                    line.strip()
                    for line in response_text.splitlines()
                    if line.strip() in {"VERDICT: PASS", "VERDICT: BLOCK"}
                ]
                if len(verdicts) != 1:
                    raise RuntimeError("Gemini 3.6 adversary verdict contract is malformed")
            return {
                "schema": response_schema,
                "capability_id": capability_id,
                "task_id": capability["task_id"],
                "goal_id": capability["goal_id"],
                "run_id": capability["run_id"],
                "stage": capability["stage"],
                "role": response_role,
                "operation": response_operation,
                "provider_id": response_provider,
                "model_id": response_model,
                "model_family": response_family,
                "actual_provider": response_provider,
                "actual_model": response_model,
                "actual_family": response_family,
                "fallback_used": False,
                "tools_used": False,
                "production_writes": False,
                "trusted_parent_confinement": True,
                "response_content": response_text,
                "request_sha256": request_sha256,
                "response_sha256": _sha256(response_text.encode()),
            }
        except (_ProcessFailure, _Gemini36ProviderFailure):
            raise
        except NormalizedError as exc:
            raise _Gemini36ProviderFailure(
                _gemini36_provider_failure_observation(exc)
            ) from None
        except (
            OSError,
            ValueError,
            RuntimeError,
            WorkerConfinementError,
            ProcessSupervisorError,
        ) as exc:
            raise RuntimeError("Gemini 3.6 critic execution failed closed") from exc
        finally:
            if server is not None:
                server.shutdown()
                server.server_close()
            if server_thread is not None:
                server_thread.join(timeout=2.0)
            cleanup_error: Exception | None = None
            if server_thread is not None and server_thread.is_alive():
                cleanup_error = RuntimeError(
                    "Gemini 3.6 gateway thread remained after shutdown"
                )
            for root, label in (
                (task_root, "Gemini 3.6 critic task workspace"),
                (forbidden_root, "Gemini 3.6 critic canary forbidden root"),
            ):
                try:
                    if root.is_symlink():
                        raise RuntimeError(f"{label} became a symlink")
                    if root.exists():
                        shutil.rmtree(root, ignore_errors=False)
                    if root.exists():
                        raise RuntimeError(f"{label} remained after cleanup")
                except Exception as exc:
                    cleanup_error = exc
            if cleanup_error is not None:
                raise RuntimeError(
                    "Gemini 3.6 critic transient cleanup failed"
                ) from cleanup_error

    def _run_gemini36_adversary_provider(
        self, capability: dict[str, object], capability_id: str, signature: str
    ) -> dict[str, object]:
        """Execute one exact Gemini 3.6 adversary capability over the existing service."""
        return self._run_gemini36_critic_provider(
            capability, capability_id, signature, adversary=True
        )

    def _run_gemini38_critic_provider(
        self,
        capability: dict[str, object],
        capability_id: str,
        signature: str,
        *,
        adversary: bool = False,
    ) -> dict[str, object]:
        """Run one fixed Google/Gemini 3.8 request through parent-owned transport."""
        response_role = "ADVERSARY" if adversary else "CRITIC"
        response_operation = GEMINI38_ADVERSARY_OPERATION if adversary else GEMINI38_CRITIC_OPERATION
        response_schema = (
            "paeos.parent-google-gemini38-adversary-observation/1"
            if adversary else "paeos.parent-google-gemini38-critic-observation/1"
        )
        response_model = GEMINI38_ADVERSARY_MODEL if adversary else GEMINI38_CRITIC_MODEL
        response_provider = GEMINI38_ADVERSARY_PROVIDER if adversary else GEMINI38_CRITIC_PROVIDER
        response_family = GEMINI38_ADVERSARY_FAMILY if adversary else GEMINI38_CRITIC_FAMILY

        credentials = CredentialStore()
        if not credentials.has_key(ProviderId.GOOGLE):
            raise RuntimeError("parent-owned Google credential is unavailable")
        task_root = _safe_path(
            self.state_root
            / ("gemini38-adversary-tasks" if adversary else "gemini38-critic-tasks")
            / capability_id,
            label=("Gemini 3.8 adversary task workspace" if adversary else "Gemini 3.8 critic task workspace"),
        )
        task_root.mkdir(mode=0o700, parents=True, exist_ok=False)
        os.chmod(task_root, 0o700)
        forbidden_root = self.state_root / "canary-forbidden" / capability_id
        control = task_root / "control"
        runtime_home, temp_root = task_root / ".home", task_root / ".tmp"
        control.mkdir(mode=0o700)
        request_path, config_path = control / "request.json", control / "curl.conf"
        state_path = task_root / "process-observation.json"
        task_bearer = hashlib.sha256(os.urandom(32)).hexdigest()
        server = None
        server_thread = None
        signed_capability = dict(capability)
        signed_capability["signature"] = signature
        request_sha256 = _sha256(_canonical_bytes(signed_capability))
        try:
            self._run_confinement_canary(task_root, capability_id, forbidden_root)
            router = ModelRouter(
                credentials=credentials,
                state_db=RouterStateDB(self.state_root / "router.sqlite3"),
            )
            fixed_router = _FixedGemini38CriticRouter(router)
            server = run_gateway_server(
                host="127.0.0.1", port=0, router=fixed_router, api_key=task_bearer
            )
            host, port = server.server_address[:2]
            if (
                host != "127.0.0.1"
                or not isinstance(port, int)
                or not 1 <= port <= 65535
            ):
                raise RuntimeError(
                    "Gemini 3.8 critic gateway did not bind exact loopback"
                )
            server_thread = threading.Thread(
                target=server.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True
            )
            server_thread.start()
            broker_url = f"http://127.0.0.1:{port}/v1/chat/completions"
            provider_request = {
                "model": response_model,
                "messages": [{"role": "user", "content": capability["prompt"]}],
                "data_class": DataClass.PUBLIC.value,
                "task_class": TaskClass.ROUTINE.value,
                "stream": False,
                "tools": None,
                "retry_policy": RetryPolicy.NONE.value,
                "allow_fallback": False,
                "max_tokens": GEMINI38_ADVERSARY_MAX_COMPLETION_TOKENS if adversary else GEMINI38_CRITIC_MAX_COMPLETION_TOKENS,
                "temperature": 0.0,
            }
            _write_exclusive(request_path, _canonical_bytes(provider_request))
            _write_exclusive(
                config_path,
                (
                    f'url = "{broker_url}"\nrequest = "POST"\n'
                    f'header = "Authorization: Bearer {task_bearer}"\n'
                    'header = "Content-Type: application/json"\n'
                    f'data-binary = "@{request_path}"\nfail-with-body\nsilent\nshow-error\n'
                    "ipv4\nconnect-timeout = 5\nmax-time = 70\n"
                ).encode(),
            )
            policy = policy_for_worker(
                workspace=task_root,
                read_roots=(task_root,),
                write_roots=(task_root,),
                runtime_home=runtime_home,
                temp_root=temp_root,
                loopback_port=port,
            )
            environment = build_provider_environment(
                {},
                runtime_home=runtime_home,
                temp_root=temp_root,
                task_environment={
                    "PAEOS_TASK_BEARER": task_bearer,
                    "PAEOS_TASK_BROKER_URL": broker_url,
                },
            )
            environment_keys = [
                "HOME",
                "LANG",
                "LC_ALL",
                "PATH",
                "TMPDIR",
                "PAEOS_TASK_BEARER",
                "PAEOS_TASK_BROKER_URL",
            ]
            if set(environment) != set(environment_keys):
                raise RuntimeError("Gemini 3.8 critic worker environment is not exact")
            if any(name.endswith("_API_KEY") for name in environment):
                raise RuntimeError("Google credential entered worker environment")
            argv = policy.wrap_argv(("/usr/bin/curl", "--config", str(config_path)))
            if task_bearer in "\0".join(argv):
                raise RuntimeError("task bearer entered worker argv")
            physical = run_bounded_process(
                argv,
                cwd=task_root,
                environment=environment,
                start_timeout_s=5.0,
                execution_timeout_s=75.0,
                state_path=state_path,
            )
            if (
                physical.lifecycle_state is not ProcessLifecycleState.RETURNED
                or physical.exit_code != 0
            ):
                if fixed_router.failure_observation is not None:
                    raise _Gemini38ProviderFailure(fixed_router.failure_observation)
                response_contract_failure_code = (
                    fixed_router.failure_code
                    if physical.exit_code != 0 and fixed_router.failure_code is not None
                    else None
                )
                process_failure = _ProcessFailure(
                    {
                        "lifecycle_state": physical.lifecycle_state.value,
                        "exit_code": physical.exit_code,
                        "stdout_bytes": len(physical.stdout),
                        "stdout_sha256": _sha256(physical.stdout),
                        "stderr_bytes": len(physical.stderr),
                        "stderr_sha256": _sha256(physical.stderr),
                    },
                    error_code=response_contract_failure_code,
                )
                if physical.exit_code != 0 and fixed_router.failure_code is not None:
                    _persist_gemini38_response_contract_diagnostic(
                        self.state_root,
                        capability_id,
                        fixed_router.failure_code,
                        fixed_router.failure_detail,
                        fixed_router.finish_reason_class,
                        process_failure.observation,
                        router_response_observed=fixed_router.router_response_observed,
                    )
                else:
                    _persist_gemini38_process_observation(
                        self.state_root, capability_id, process_failure.observation
                    )
                raise process_failure
            bearer_bytes = task_bearer.encode("ascii")
            if bearer_bytes in physical.stdout or bearer_bytes in physical.stderr:
                raise RuntimeError("task bearer leaked into worker output")
            routed = fixed_router.response
            if routed is None:
                raise RuntimeError("Gemini 3.8 critic router response was not captured")
            try:
                raw_document = json.loads(physical.stdout.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise RuntimeError(
                    "Gemini 3.8 gateway response is not strict JSON"
                ) from exc
            choices = (
                raw_document.get("choices") if isinstance(raw_document, dict) else None
            )
            choice = (
                choices[0] if isinstance(choices, list) and len(choices) == 1 else None
            )
            message = choice.get("message") if isinstance(choice, dict) else None
            response_text = routed.content
            if (
                not isinstance(raw_document, dict)
                or raw_document.get("object") != "chat.completion"
                or raw_document.get("model") != response_model
                or raw_document.get("provider") != response_provider
                or raw_document.get("system_fingerprint") != "paeos-router-gemini"
                or raw_document.get("fallback_chain")
                != [f"{response_provider}:{response_model}"]
                or not isinstance(choice, dict)
                or choice.get("finish_reason") != "stop"
                or not isinstance(message, dict)
                or message.get("role") != "assistant"
                or message.get("content") != response_text
                or message.get("tool_calls")
                or not isinstance(response_text, str)
                or not response_text.strip()
                or len(response_text.encode("utf-8")) > MAX_RESPONSE_BYTES
            ):
                raise RuntimeError(
                    "Gemini 3.8 critic gateway response attribution is malformed"
                )
            return {
                "schema": response_schema,
                "capability_id": capability_id,
                "task_id": capability["task_id"],
                "goal_id": capability["goal_id"],
                "run_id": capability["run_id"],
                "stage": capability["stage"],
                "role": response_role,
                "operation": response_operation,
                "provider_id": response_provider,
                "model_id": response_model,
                "model_family": response_family,
                "actual_provider": response_provider,
                "actual_model": response_model,
                "actual_family": response_family,
                "fallback_used": False,
                "tools_used": False,
                "production_writes": False,
                "trusted_parent_confinement": True,
                "response_content": response_text,
                "request_sha256": request_sha256,
                "response_sha256": _sha256(response_text.encode("utf-8")),
            }
        except (_ProcessFailure, _Gemini38ProviderFailure):
            raise
        except NormalizedError as exc:
            raise _Gemini38ProviderFailure(
                _gemini38_provider_failure_observation(exc)
            ) from None
        except (
            OSError,
            ValueError,
            RuntimeError,
            WorkerConfinementError,
            ProcessSupervisorError,
        ) as exc:
            raise RuntimeError("Gemini 3.8 critic execution failed closed") from exc
        finally:
            if server is not None:
                server.shutdown()
                server.server_close()
            if server_thread is not None:
                server_thread.join(timeout=2.0)
            cleanup_error: Exception | None = None
            if server_thread is not None and server_thread.is_alive():
                cleanup_error = RuntimeError(
                    "Gemini 3.8 gateway thread remained after shutdown"
                )
            for root, label in (
                (task_root, "Gemini 3.8 critic task workspace"),
                (forbidden_root, "Gemini 3.8 critic canary forbidden root"),
            ):
                try:
                    if root.is_symlink():
                        raise RuntimeError(f"{label} became a symlink")
                    if root.exists():
                        shutil.rmtree(root, ignore_errors=False)
                    if root.exists():
                        raise RuntimeError(f"{label} remained after cleanup")
                except Exception as exc:
                    cleanup_error = exc
            if cleanup_error is not None:
                raise RuntimeError(
                    "Gemini 3.8 critic transient cleanup failed"
                ) from cleanup_error

    def _run_gemini38_adversary_provider(
        self, capability: dict[str, object], capability_id: str, signature: str
    ) -> dict[str, object]:
        """Execute the distinct adversary capability over fixed parent Gemini mechanics."""
        return self._run_gemini38_critic_provider(
            capability, capability_id, signature, adversary=True
        )

    def _run_cline_provider(
        self, capability: dict[str, object], capability_id: str
    ) -> dict[str, object]:
        """Run shell-free curl against a one-shot loopback broker; Cline auth stays parent-owned."""
        entry = _fixed_cline_entry()
        credentials = CredentialStore()
        if not credentials.has_key(ProviderId.CLINE):
            raise RuntimeError("parent-owned Cline credential is unavailable")
        api_key = credentials.get_key(ProviderId.CLINE)
        transport = ClineEnvelopeTransport(
            "https://api.cline.bot/api/v1", ModelCatalog([entry])
        )
        task_root = _safe_path(
            self.state_root / "cline-tasks" / capability_id,
            label="Cline task workspace",
        )
        task_root.mkdir(mode=0o700, parents=True, exist_ok=False)
        observation_root = self.state_root / "cline-observations"
        observation_root.mkdir(mode=0o700, parents=True, exist_ok=True)
        os.chmod(observation_root, 0o700)
        runtime_home, temp_root = task_root / ".home", task_root / ".tmp"
        broker_token = hashlib.sha256(os.urandom(32)).hexdigest()
        request_path, config_path = task_root / "request.json", task_root / "curl.conf"
        response_box: dict[str, Any] = {}
        forbidden_root = self.state_root / "canary-forbidden" / capability_id

        class Broker(BaseHTTPRequestHandler):
            def do_POST(self) -> None:
                if (
                    self.path != "/critic"
                    or self.headers.get("Authorization") != f"Bearer {broker_token}"
                ):
                    self.send_error(403)
                    return
                try:
                    length = int(self.headers.get("Content-Length", "0"))
                    received = json.loads(self.rfile.read(length).decode("utf-8"))
                    if received != {"capability_id": capability_id}:
                        raise RuntimeError("broker task identity mismatch")
                    request = TaskRequest(
                        messages=[{"role": "user", "content": capability["prompt"]}],
                        explicit_model=CLINE_MODEL,
                        allow_fallback=False,
                        stream=False,
                        max_tokens=128,
                        temperature=0.0,
                    )
                    routed = transport.dispatch(
                        entry, request, api_key=api_key, timeout=70.0
                    )
                    if (
                        routed.provider_id is not ProviderId.CLINE
                        or routed.model_id != CLINE_MODEL
                        or routed.actual_model != CLINE_MODEL
                        or routed.actual_family is not ModelFamily.GLM
                        or routed.tool_calls
                        or routed.finish_reason != "stop"
                        or not isinstance(routed.content, str)
                        or not routed.content.strip()
                    ):
                        raise RuntimeError("Cline selected and observed routes differ")
                    response_box.update(content=routed.content)
                    body = _canonical_bytes({"ok": True})
                    self.send_response(200)
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
                except Exception as exc:
                    response_box["error"] = exc
                    self.send_error(502)

            def log_message(self, _format: str, *args: object) -> None:
                return

        server = ThreadingHTTPServer(("127.0.0.1", 0), Broker)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        port = server.server_address[1]
        try:
            confinement_canaries = self._run_confinement_canary(
                task_root, capability_id, forbidden_root
            )
            _write_exclusive(
                request_path, _canonical_bytes({"capability_id": capability_id})
            )
            _write_exclusive(
                config_path,
                (
                    f'url = "http://127.0.0.1:{port}/critic"\nrequest = "POST"\n'
                    f'header = "Authorization: Bearer {broker_token}"\ndata-binary = "@{request_path}"\n'
                    "fail-with-body\nsilent\nshow-error\nipv4\nconnect-timeout = 5\nmax-time = 75\n"
                ).encode(),
            )
            policy = policy_for_worker(
                workspace=task_root,
                read_roots=(task_root,),
                write_roots=(task_root,),
                runtime_home=runtime_home,
                temp_root=temp_root,
                loopback_port=port,
            )
            environment = build_provider_environment(
                {}, runtime_home=runtime_home, temp_root=temp_root
            )
            argv = policy.wrap_argv(("/usr/bin/curl", "--config", str(config_path)))
            try:
                physical = run_bounded_process(
                    argv,
                    cwd=task_root,
                    environment=environment,
                    start_timeout_s=5.0,
                    execution_timeout_s=80.0,
                    state_path=observation_root / f"{capability_id}.json",
                )
            except Exception as exc:
                _persist_cline_http_diagnostic(
                    observation_root,
                    capability_id,
                    exc,
                    transport_exit_code=None,
                    loopback_http_status=502 if "error" in response_box else None,
                )
                raise
            if (
                physical.lifecycle_state is not ProcessLifecycleState.RETURNED
                or physical.exit_code != 0
                or "error" in response_box
            ):
                provider_error = response_box.get("error")
                if not isinstance(provider_error, BaseException):
                    provider_error = RuntimeError(
                        "upstream HTTP status was not observed"
                    )
                _persist_cline_http_diagnostic(
                    observation_root,
                    capability_id,
                    provider_error,
                    transport_exit_code=physical.exit_code,
                    loopback_http_status=502 if "error" in response_box else None,
                )
                raise RuntimeError("Cline provider or confined broker worker failed")
            content = response_box.get("content")
            if (
                not isinstance(content, str)
                or len(content.encode("utf-8")) > MAX_RESPONSE_BYTES
            ):
                raise RuntimeError("Cline response is empty or oversized")
            return {
                "capability_id": capability_id,
                "operation": CLINE_OPERATION,
                "provider_id": CLINE_PROVIDER,
                "model_id": CLINE_MODEL,
                "model_family": CLINE_FAMILY,
                "actual_provider": CLINE_PROVIDER,
                "actual_model": CLINE_MODEL,
                "actual_family": CLINE_FAMILY,
                "fallback_used": False,
                "lifecycle_state": physical.lifecycle_state.value,
                "exit_code": physical.exit_code,
                "response_content": content,
                "stdout_sha256": _sha256(physical.stdout),
                "stderr_sha256": _sha256(physical.stderr),
                "stdout_bytes": len(physical.stdout),
                "stderr_bytes": len(physical.stderr),
                "executable": physical.executable,
                "executable_version": physical.executable_version,
                "environment_fingerprint": physical.environment_fingerprint,
                "argv": list(physical.argv),
                "profile_sha256": _sha256(policy.seatbelt_profile.encode("utf-8")),
                "workspace": physical.cwd,
                "confinement_canaries": confinement_canaries,
            }
        finally:
            cleanup_error: Exception | None = None
            try:
                server.shutdown()
                server.server_close()
                thread.join(timeout=2.0)
                if thread.is_alive():
                    raise RuntimeError("Cline broker thread remained after shutdown")
            except Exception as exc:
                cleanup_error = exc
            for root, label in (
                (task_root, "Cline task workspace"),
                (forbidden_root, "Cline canary forbidden root"),
            ):
                try:
                    if root.is_symlink():
                        raise RuntimeError(f"{label} became a symlink")
                    if root.exists():
                        shutil.rmtree(root, ignore_errors=False)
                    if root.exists():
                        raise RuntimeError(f"{label} remained after cleanup")
                except Exception as exc:
                    cleanup_error = exc
            if cleanup_error is not None:
                raise RuntimeError("Cline transient cleanup failed") from cleanup_error

    def _run_confinement_canary(
        self, task_root: Path, capability_id: str, forbidden_root: Path
    ) -> dict[str, object]:
        forbidden_root.mkdir(mode=0o700, parents=True, exist_ok=False)
        os.chmod(forbidden_root, 0o700)
        forbidden_file = forbidden_root / "secret.txt"
        forbidden_file.write_bytes(b"DEBT0124_FORBIDDEN_SYNTHETIC")
        os.chmod(forbidden_file, 0o600)
        approved_read = task_root / "canary-approved-read.txt"
        approved_write = task_root / "canary-approved-write.txt"
        symlink_file = task_root / "canary-escape-link"
        traversal_file = (
            task_root
            / "nested"
            / ".."
            / ".."
            / ".."
            / "canary-forbidden"
            / capability_id
            / "secret.txt"
        )
        forbidden_write = forbidden_root / "forbidden-write.txt"
        approved_read.write_bytes(b"DEBT0124_APPROVED_READ")
        os.chmod(approved_read, 0o600)
        (task_root / "nested").mkdir(mode=0o700)
        symlink_file.symlink_to(forbidden_file)
        script_path = task_root / "confinement-canary.sh"
        _write_exclusive(script_path, _CANARY_SCRIPT.encode("utf-8"))
        runtime_home = task_root / ".canary-runtime"
        temp_root = task_root / ".canary-tmp"
        policy = policy_for_worker(
            workspace=task_root,
            read_roots=(task_root,),
            write_roots=(task_root,),
            runtime_home=runtime_home,
            temp_root=temp_root,
        )
        environment = build_provider_environment(
            {}, runtime_home=runtime_home, temp_root=temp_root
        )
        argv = policy.wrap_argv(
            (
                "/bin/sh",
                str(script_path),
                str(approved_read),
                str(approved_write),
                str(forbidden_file),
                str(forbidden_root),
                str(symlink_file),
                str(traversal_file),
                str(forbidden_write),
            )
        )
        physical = run_bounded_process(
            argv,
            cwd=task_root,
            environment=environment,
            start_timeout_s=5.0,
            execution_timeout_s=20.0,
            state_path=task_root / "canary-process-observation.json",
        )
        if (
            physical.lifecycle_state is not ProcessLifecycleState.RETURNED
            or physical.exit_code != 0
        ):
            raise _ProcessFailure(
                {
                    "lifecycle_state": physical.lifecycle_state.value,
                    "exit_code": physical.exit_code,
                    "stdout_bytes": len(physical.stdout),
                    "stdout_sha256": _sha256(physical.stdout),
                    "stderr_bytes": len(physical.stderr),
                    "stderr_sha256": _sha256(physical.stderr),
                }
            )
        try:
            observed = dict(
                line.split("=", 1)
                for line in physical.stdout.decode("utf-8").splitlines()
                if "=" in line
            )
        except UnicodeDecodeError as exc:
            raise RuntimeError("confinement canary output is not UTF-8") from exc
        if set(observed) != _CANARY_KEYS or any(
            value != "PASS" for value in observed.values()
        ):
            raise RuntimeError("confinement canary failed closed")
        return {
            "results": observed,
            "process": {
                "exit_code": physical.exit_code,
                "lifecycle_state": physical.lifecycle_state.value,
                "stdout_bytes": len(physical.stdout),
                "stdout_sha256": _sha256(physical.stdout),
                "stderr_bytes": len(physical.stderr),
                "stderr_sha256": _sha256(physical.stderr),
                "environment_fingerprint": physical.environment_fingerprint,
                "profile_sha256": _sha256(policy.seatbelt_profile.encode("utf-8")),
            },
        }

    def _run_nvidia_critic_provider(
        self,
        capability: dict[str, object],
        capability_id: str,
        signature: str,
    ) -> dict[str, object]:
        """Redeem one signed critic capability through the parent-owned NVIDIA router."""

        credentials = CredentialStore()
        if not credentials.has_key(ProviderId.NVIDIA):
            raise RuntimeError("parent-owned NVIDIA credential is unavailable")
        task_root = _safe_path(
            self.state_root / "nvidia-critic-tasks" / capability_id,
            label="NVIDIA critic task workspace",
        )
        task_root.mkdir(mode=0o700, parents=True, exist_ok=False)
        os.chmod(task_root, 0o700)
        forbidden_root = self.state_root / "canary-forbidden" / capability_id
        control = task_root / "control"
        runtime_home = task_root / ".home"
        temp_root = task_root / ".tmp"
        control.mkdir(mode=0o700)
        request_path = control / "request.json"
        config_path = control / "curl.conf"
        state_path = task_root / "process-observation.json"
        task_bearer = hashlib.sha256(os.urandom(32)).hexdigest()
        server = None
        server_thread = None
        signed_capability = dict(capability)
        signed_capability["signature"] = signature
        canonical_request = {
            "capability": signed_capability,
            "prompt": capability["prompt"],
            "goal_id": capability["goal_id"],
            "run_id": capability["run_id"],
            "tools": None,
        }
        request_sha256 = _sha256(_canonical_bytes(canonical_request))
        try:
            self._run_confinement_canary(task_root, capability_id, forbidden_root)
            router = ModelRouter(
                credentials=credentials,
                state_db=RouterStateDB(self.state_root / "router.sqlite3"),
            )
            fixed_router = _FixedNvidiaCriticRouter(router)
            server = run_gateway_server(
                host="127.0.0.1", port=0, router=fixed_router, api_key=task_bearer
            )
            host, port = server.server_address[:2]
            if (
                host != "127.0.0.1"
                or not isinstance(port, int)
                or not 1 <= port <= 65535
            ):
                raise RuntimeError("NVIDIA critic gateway did not bind exact loopback")
            server_thread = threading.Thread(
                target=server.serve_forever,
                kwargs={"poll_interval": 0.05},
                daemon=True,
            )
            server_thread.start()
            broker_url = f"http://127.0.0.1:{port}/v1/chat/completions"
            provider_request = {
                "model": NVIDIA_CRITIC_MODEL,
                "messages": [{"role": "user", "content": capability["prompt"]}],
                "data_class": DataClass.PUBLIC.value,
                "task_class": TaskClass.ROUTINE.value,
                "stream": False,
                "tools": None,
                "retry_policy": RetryPolicy.NONE.value,
                "allow_fallback": False,
                "max_tokens": 128,
                "temperature": 0.0,
            }
            _write_exclusive(request_path, _canonical_bytes(provider_request))
            _write_exclusive(
                config_path,
                (
                    f'url = "{broker_url}"\nrequest = "POST"\n'
                    f'header = "Authorization: Bearer {task_bearer}"\n'
                    'header = "Content-Type: application/json"\n'
                    f'data-binary = "@{request_path}"\nfail-with-body\nsilent\nshow-error\n'
                    "ipv4\nconnect-timeout = 5\nmax-time = 70\n"
                ).encode(),
            )
            policy = policy_for_worker(
                workspace=task_root,
                read_roots=(task_root,),
                write_roots=(task_root,),
                runtime_home=runtime_home,
                temp_root=temp_root,
                loopback_port=port,
            )
            environment = build_provider_environment(
                {},
                runtime_home=runtime_home,
                temp_root=temp_root,
                task_environment={
                    "PAEOS_TASK_BEARER": task_bearer,
                    "PAEOS_TASK_BROKER_URL": broker_url,
                },
            )
            environment_keys = [
                "HOME",
                "LANG",
                "LC_ALL",
                "PATH",
                "TMPDIR",
                "PAEOS_TASK_BEARER",
                "PAEOS_TASK_BROKER_URL",
            ]
            expected_environment = set(environment_keys)
            if set(environment) != expected_environment:
                raise RuntimeError("NVIDIA critic worker environment is not exact")
            if any(name.endswith("_API_KEY") for name in environment):
                raise RuntimeError("NVIDIA credential entered worker environment")
            argv = policy.wrap_argv(("/usr/bin/curl", "--config", str(config_path)))
            if task_bearer in "\0".join(argv):
                raise RuntimeError("task bearer entered worker argv")
            physical = run_bounded_process(
                argv,
                cwd=task_root,
                environment=environment,
                start_timeout_s=5.0,
                execution_timeout_s=75.0,
                state_path=state_path,
            )
            if (
                physical.lifecycle_state is not ProcessLifecycleState.RETURNED
                or physical.exit_code != 0
            ):
                if fixed_router.failure_observation is not None:
                    raise _ProviderFailure(fixed_router.failure_observation)
                raise _ProcessFailure(
                    {
                        "lifecycle_state": physical.lifecycle_state.value,
                        "exit_code": physical.exit_code,
                        "stdout_bytes": len(physical.stdout),
                        "stdout_sha256": _sha256(physical.stdout),
                        "stderr_bytes": len(physical.stderr),
                        "stderr_sha256": _sha256(physical.stderr),
                    }
                )
            if (
                task_bearer.encode("ascii") in physical.stdout
                or task_bearer.encode("ascii") in physical.stderr
            ):
                raise RuntimeError("task bearer leaked into worker output")
            routed = fixed_router.response
            if routed is None:
                raise RuntimeError("NVIDIA critic router response was not captured")
            response_text = routed.content
            if not isinstance(response_text, str) or not response_text.strip():
                raise RuntimeError("NVIDIA critic response is empty")
            # Parse the loopback response too; success requires agreement with the captured route.
            raw_document = json.loads(physical.stdout.decode("utf-8"))
            choices = (
                raw_document.get("choices") if isinstance(raw_document, dict) else None
            )
            message = (
                choices[0].get("message")
                if isinstance(choices, list)
                and len(choices) == 1
                and isinstance(choices[0], dict)
                else None
            )
            if (
                not isinstance(raw_document, dict)
                or raw_document.get("object") != "chat.completion"
                or raw_document.get("model") != NVIDIA_CRITIC_MODEL
                or raw_document.get("provider") != NVIDIA_CRITIC_PROVIDER
                or raw_document.get("system_fingerprint") != "paeos-router-llama"
                or raw_document.get("fallback_chain")
                != [f"{NVIDIA_CRITIC_PROVIDER}:{NVIDIA_CRITIC_MODEL}"]
                or not isinstance(choices, list)
                or len(choices) != 1
                or not isinstance(choices[0], dict)
                or choices[0].get("finish_reason") != "stop"
                or not isinstance(message, dict)
                or message.get("role") != "assistant"
                or not isinstance(message.get("content"), str)
                or not message["content"].strip()
                or message.get("content") != response_text
                or message.get("tool_calls")
            ):
                raise RuntimeError(
                    "NVIDIA critic gateway response attribution is malformed"
                )
            return {
                "schema": "paeos.parent-nvidia-llama-critic-observation/1",
                "capability_id": capability_id,
                "task_id": capability["task_id"],
                "operation": "critic",
                "role": "CRITIC",
                "provider_id": NVIDIA_CRITIC_PROVIDER,
                "model_id": NVIDIA_CRITIC_MODEL,
                "model_family": NVIDIA_CRITIC_FAMILY,
                "actual_provider": NVIDIA_CRITIC_PROVIDER,
                "actual_model": NVIDIA_CRITIC_MODEL,
                "actual_family": NVIDIA_CRITIC_FAMILY,
                "fallback_used": False,
                "tools_used": False,
                "production_writes": False,
                "lifecycle_state": "RETURNED",
                "exit_code": 0,
                "response_content": response_text,
                "request_sha256": request_sha256,
                "response_sha256": _sha256(response_text.encode("utf-8")),
                "environment_keys": environment_keys,
            }
        except (_ProcessFailure, _ProviderFailure):
            raise
        except NormalizedError as exc:
            raise _ProviderFailure(_nvidia_provider_failure_observation(exc)) from None
        except (
            OSError,
            ValueError,
            RuntimeError,
            WorkerConfinementError,
            ProcessSupervisorError,
        ) as exc:
            raise RuntimeError("NVIDIA critic execution failed closed") from exc
        finally:
            if server is not None:
                server.shutdown()
                server.server_close()
            if server_thread is not None:
                server_thread.join(timeout=2.0)
            cleanup_error: Exception | None = None
            for root, label in (
                (task_root, "NVIDIA critic task workspace"),
                (forbidden_root, "NVIDIA critic canary forbidden root"),
            ):
                try:
                    if root.is_symlink():
                        raise RuntimeError(f"{label} became a symlink")
                    if root.exists():
                        shutil.rmtree(root, ignore_errors=False)
                    if root.exists():
                        raise RuntimeError(f"{label} remained after cleanup")
                except Exception as exc:
                    cleanup_error = exc
            if cleanup_error is not None:
                raise RuntimeError(
                    "NVIDIA critic transient cleanup failed"
                ) from cleanup_error

    def _run_provider(
        self, capability: dict[str, object], capability_id: str
    ) -> dict[str, object]:
        entry = _fixed_entry()
        credentials = CredentialStore()
        if not credentials.has_key(ProviderId.OPENROUTER):
            raise RuntimeError("parent-owned provider credential is unavailable")
        task_root = self.state_root / "tasks" / capability_id
        task_root = _safe_path(task_root, label="task workspace")
        task_root.mkdir(mode=0o700, parents=True, exist_ok=False)
        os.chmod(task_root, 0o700)
        forbidden_root = self.state_root / "canary-forbidden" / capability_id
        control = task_root / "control"
        runtime_home = task_root / ".paeos-provider-runtime"
        temp_root = task_root / ".paeos-provider-tmp"
        control.mkdir(mode=0o700)
        token = secrets_token = hashlib.sha256(os.urandom(32)).hexdigest()
        request_path = control / "request.json"
        config_path = control / "curl.conf"
        state_path = task_root / "process-observation.json"
        server = None
        server_thread = None
        try:
            confinement_canaries = self._run_confinement_canary(
                task_root, capability_id, forbidden_root
            )
            router = ModelRouter(
                credentials=credentials,
                catalog=ModelCatalog([entry]),
                state_db=RouterStateDB(self.state_root / "router.sqlite3"),
            )
            fixed_router = _FixedRouter(router, entry)
            server = run_gateway_server(
                host="127.0.0.1", port=0, router=fixed_router, api_key=token
            )
            host, port = server.server_address[:2]
            if (
                host != "127.0.0.1"
                or not isinstance(port, int)
                or not 1 <= port <= 65535
            ):
                raise RuntimeError("gateway did not bind exact loopback")
            server_thread = threading.Thread(
                target=server.serve_forever,
                kwargs={"poll_interval": 0.05},
                daemon=True,
            )
            server_thread.start()
            request = {
                "model": MODEL,
                "messages": [{"role": "user", "content": capability["prompt"]}],
                "data_class": DataClass.PUBLIC.value,
                "task_class": TaskClass.ROUTINE.value,
                "stream": False,
                "max_tokens": 128,
                "temperature": 0.0,
            }
            _write_exclusive(request_path, _canonical_bytes(request))
            config = (
                f'url = "http://127.0.0.1:{port}/v1/chat/completions"\n'
                'request = "POST"\n'
                f'header = "Authorization: Bearer {secrets_token}"\n'
                'header = "Content-Type: application/json"\n'
                f'data-binary = "@{request_path}"\n'
                "fail-with-body\n"
                "silent\n"
                "show-error\n"
                "ipv4\n"
                "connect-timeout = 5\n"
                "max-time = 70\n"
            ).encode()
            _write_exclusive(config_path, config)
            policy = policy_for_worker(
                workspace=task_root,
                read_roots=(task_root,),
                write_roots=(task_root,),
                runtime_home=runtime_home,
                temp_root=temp_root,
                loopback_port=port,
            )
            environment = build_provider_environment(
                {}, runtime_home=runtime_home, temp_root=temp_root
            )
            if set(environment) != {"HOME", "LANG", "LC_ALL", "PATH", "TMPDIR"}:
                raise RuntimeError("worker environment is not exact")
            if not environment["LANG"] == "C.UTF-8" or environment["LC_ALL"] != "C":
                raise RuntimeError("worker locale is not canonical")
            if any(name.endswith("_API_KEY") for name in environment):
                raise RuntimeError("provider credential entered worker environment")
            argv = policy.wrap_argv(("/usr/bin/curl", "--config", str(config_path)))
            if secrets_token in "\0".join(argv):
                raise RuntimeError("broker token entered worker argv")
            physical = run_bounded_process(
                argv,
                cwd=task_root,
                environment=environment,
                start_timeout_s=5.0,
                execution_timeout_s=75.0,
                state_path=state_path,
            )
            if (
                physical.lifecycle_state is not ProcessLifecycleState.RETURNED
                or physical.exit_code != 0
            ):
                raise _ProcessFailure(
                    {
                        "lifecycle_state": physical.lifecycle_state.value,
                        "exit_code": physical.exit_code,
                        "stdout_bytes": len(physical.stdout),
                        "stdout_sha256": _sha256(physical.stdout),
                        "stderr_bytes": len(physical.stderr),
                        "stderr_sha256": _sha256(physical.stderr),
                    }
                )
            if (
                secrets_token.encode("ascii") in physical.stdout
                or secrets_token.encode("ascii") in physical.stderr
            ):
                raise RuntimeError("broker token leaked into worker output")
            content = _parse_provider_response(physical.stdout)
            routed_response = fixed_router.response
            if routed_response is None:
                raise RuntimeError("provider router response was not captured")
            if routed_response.actual_family in (
                None,
                ModelFamily.GPT,
                ModelFamily.UNKNOWN,
            ):
                raise RuntimeError("actual provider family is not known non-GPT")
            return {
                "provider_id": PROVIDER,
                "model_id": MODEL,
                "model_family": routed_response.actual_family.value,
                "actual_model": routed_response.actual_model,
                "actual_family": routed_response.actual_family.value,
                "response_content": content,
                "stdout_sha256": _sha256(physical.stdout),
                "stderr_sha256": _sha256(physical.stderr),
                "stdout_bytes": len(physical.stdout),
                "stderr_bytes": len(physical.stderr),
                "exit_code": physical.exit_code,
                "lifecycle_state": physical.lifecycle_state.value,
                "executable": physical.executable,
                "executable_version": physical.executable_version,
                "environment_fingerprint": physical.environment_fingerprint,
                "argv": list(physical.argv),
                "profile_sha256": _sha256(policy.seatbelt_profile.encode("utf-8")),
                "workspace": str(task_root),
                "confinement_canaries": confinement_canaries,
            }
        except _ProcessFailure:
            raise
        except (
            OSError,
            ValueError,
            RuntimeError,
            WorkerConfinementError,
            ProcessSupervisorError,
        ) as exc:
            raise RuntimeError("provider execution failed closed") from exc
        finally:
            if server is not None:
                server.shutdown()
                server.server_close()
            if server_thread is not None:
                server_thread.join(timeout=2.0)
            cleanup_error: Exception | None = None
            for path in (config_path, request_path):
                try:
                    if path.is_symlink():
                        raise RuntimeError("transient provider file became a symlink")
                    if path.exists():
                        _remove_exact(path)
                except Exception as exc:  # converted to fail-closed response
                    cleanup_error = exc
            if cleanup_error is not None:
                raise RuntimeError(
                    "provider transient cleanup failed"
                ) from cleanup_error

    def handle(self, raw: bytes) -> bytes:
        capability_id: str | None = None
        gemini38_execution_entered = False
        gemini36_execution_entered = False
        try:
            document = json.loads(raw.decode("utf-8"))
            if isinstance(document, dict):
                capability_id = _capability_id(document.get("capability_id"))
            # Restoring the producer must not restore any unauthorised egress route.
            # A signer authenticates a refusal; it supplies no disclosure authority.
            raise RuntimeError("trusted disclosure authority is unavailable")
            if (
                isinstance(document, dict)
                and document.get("schema") == CLINE_CAPABILITY_SCHEMA
            ):
                capability, capability_id = self._validate_cline_capability(document)
                observation = self._run_cline_provider(capability, capability_id)
            elif (
                isinstance(document, dict)
                and document.get("schema") == NVIDIA_CRITIC_CAPABILITY_SCHEMA
            ):
                signature = document.get("signature")
                if not isinstance(signature, str):
                    raise RuntimeError(
                        "NVIDIA critic capability signature is malformed"
                    )
                capability, capability_id = self._validate_nvidia_critic_capability(
                    document
                )
                observation = self._run_nvidia_critic_provider(
                    capability, capability_id, signature
                )
            elif (
                isinstance(document, dict)
                and document.get("schema") == GEMINI36_CRITIC_CAPABILITY_SCHEMA
            ):
                signature = document.get("signature")
                if not isinstance(signature, str):
                    raise RuntimeError(
                        "Gemini 3.6 critic capability signature is malformed"
                    )
                capability, capability_id = self._validate_gemini36_critic_capability(
                    document
                )
                gemini36_execution_entered = True
                observation = self._run_gemini36_critic_provider(
                    capability, capability_id, signature
                )
            elif (
                isinstance(document, dict)
                and document.get("schema") == GEMINI36_ADVERSARY_CAPABILITY_SCHEMA
            ):
                signature = document.get("signature")
                if not isinstance(signature, str):
                    raise RuntimeError(
                        "Gemini 3.6 adversary capability signature is malformed"
                    )
                capability, capability_id = self._validate_gemini36_adversary_capability(
                    document
                )
                gemini36_execution_entered = True
                observation = self._run_gemini36_adversary_provider(
                    capability, capability_id, signature
                )
            elif (
                isinstance(document, dict)
                and document.get("schema") == GEMINI38_CRITIC_CAPABILITY_SCHEMA
            ):
                signature = document.get("signature")
                if not isinstance(signature, str):
                    raise RuntimeError(
                        "Gemini 3.8 critic capability signature is malformed"
                    )
                capability, capability_id = self._validate_gemini38_critic_capability(
                    document
                )
                gemini38_execution_entered = True
                observation = self._run_gemini38_critic_provider(
                    capability, capability_id, signature
                )
            elif (
                isinstance(document, dict)
                and document.get("schema") == GEMINI38_ADVERSARY_CAPABILITY_SCHEMA
            ):
                signature = document.get("signature")
                if not isinstance(signature, str):
                    raise RuntimeError(
                        "Gemini 3.8 adversary capability signature is malformed"
                    )
                capability, capability_id = self._validate_gemini38_adversary_capability(
                    document
                )
                gemini38_execution_entered = True
                observation = self._run_gemini38_adversary_provider(
                    capability, capability_id, signature
                )
            else:
                capability, capability_id = self._validate_capability(document)
                observation = self._run_provider(capability, capability_id)
            response: dict[str, object] = {
                "schema": SERVICE_SCHEMA,
                "ok": True,
                "capability_id": capability_id,
                "observation": observation,
            }
        except Exception as exc:
            process_failure_code: str | None = None
            gemini36_failure_observation: Mapping[str, object] | None = None
            if gemini36_execution_entered:
                if isinstance(exc, _ProcessFailure):
                    process_failure_code = _failure_code(exc)
                    gemini36_failure_observation = {
                        "schema": PROVIDER_FAILURE_OBSERVATION_SCHEMA,
                        "provider_id": GEMINI36_CRITIC_PROVIDER,
                        "model_id": GEMINI36_CRITIC_MODEL,
                        "error_type": NormalizedErrorType.UNKNOWN.value,
                        "http_status": None,
                        "retry_after": None,
                        "response_bytes": None,
                        "response_sha256": None,
                        "raw_response_persisted": False,
                    }
                elif isinstance(exc, _Gemini36ProviderFailure):
                    gemini36_failure_observation = exc.observation
                    if exc.error_code is not None:
                        process_failure_code = exc.error_code
                    elif exc.observation.get("http_status") == 200:
                        process_failure_code = "gateway_response_failure"
                else:
                    gemini36_failure_observation = {
                        "schema": PROVIDER_FAILURE_OBSERVATION_SCHEMA,
                        "provider_id": GEMINI36_CRITIC_PROVIDER,
                        "model_id": GEMINI36_CRITIC_MODEL,
                        "error_type": NormalizedErrorType.UNKNOWN.value,
                        "http_status": None,
                        "retry_after": None,
                        "response_bytes": None,
                        "response_sha256": None,
                        "raw_response_persisted": False,
                    }
            if gemini38_execution_entered and isinstance(exc, _ProcessFailure):
                process_failure_code = _failure_code(exc)
                exc = _Gemini38ProviderFailure(
                    {
                        "schema": PROVIDER_FAILURE_OBSERVATION_SCHEMA,
                        "provider_id": GEMINI38_CRITIC_PROVIDER,
                        "model_id": GEMINI38_CRITIC_MODEL,
                        "error_type": NormalizedErrorType.UNKNOWN.value,
                        "http_status": None,
                        "retry_after": None,
                        "response_bytes": None,
                        "response_sha256": None,
                        "raw_response_persisted": False,
                    }
                )
            if (
                gemini38_execution_entered
                and isinstance(
                    exc,
                    (
                        OSError,
                        ValueError,
                        RuntimeError,
                        WorkerConfinementError,
                        ProcessSupervisorError,
                    ),
                )
                and not isinstance(
                    exc, (_ProcessFailure, _Gemini38ProviderFailure, NormalizedError)
                )
            ):
                exc = _Gemini38ProviderFailure(
                    {
                        "schema": PROVIDER_FAILURE_OBSERVATION_SCHEMA,
                        "provider_id": GEMINI38_CRITIC_PROVIDER,
                        "model_id": GEMINI38_CRITIC_MODEL,
                        "error_type": NormalizedErrorType.UNKNOWN.value,
                        "http_status": None,
                        "retry_after": None,
                        "response_bytes": None,
                        "response_sha256": None,
                        "raw_response_persisted": False,
                    }
                )
            response = {
                "schema": SERVICE_SCHEMA,
                "ok": False,
                "capability_id": capability_id,
                "error": "provider capability rejected or execution failed closed",
                "error_code": (
                    process_failure_code
                    if process_failure_code is not None
                    else _failure_code(exc)
                ),
            }
            if gemini36_failure_observation is not None:
                response["failure_observation"] = dict(gemini36_failure_observation)
            elif isinstance(exc, (_ProcessFailure, _ProviderFailure)):
                response["failure_observation"] = dict(exc.observation)
            elif isinstance(exc, NormalizedError):
                with contextlib.suppress(RuntimeError):
                    response["failure_observation"] = (
                        _nvidia_provider_failure_observation(exc)
                    )
        return self._signed_response(response, raw)


def serve(service: TrustedProviderService) -> None:
    parent = service.socket_path.parent
    parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(parent, 0o700)
    if service.socket_path.exists():
        if not stat.S_ISSOCK(service.socket_path.stat().st_mode):
            raise RuntimeError("launcher socket path is occupied by a non-socket")
        service.socket_path.unlink()
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as listener:
        listener.bind(str(service.socket_path))
        os.chmod(service.socket_path, 0o600)
        listener.listen(8)
        listener.settimeout(0.1)
        while True:
            try:
                channel, _address = listener.accept()
            except TimeoutError:
                service.process_queue()
                continue
            with channel:
                channel.settimeout(90.0)
                chunks: list[bytes] = []
                total = 0
                while True:
                    chunk = channel.recv(65536)
                    if not chunk:
                        break
                    total += len(chunk)
                    if total > MAX_FRAME_BYTES:
                        raise RuntimeError("capability frame exceeded bounded size")
                    chunks.append(chunk)
                try:
                    channel.sendall(service.handle(b"".join(chunks)))
                except (BrokenPipeError, ConnectionResetError):
                    pass
            service.process_queue()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="PAEOS trusted provider-worker supervisor"
    )
    parser.add_argument("--bundle-root", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--public-key", type=Path, required=True)
    parser.add_argument("--socket-path", type=Path, required=True)
    parser.add_argument("--queue-root", type=Path, required=True)
    parser.add_argument("--state-root", type=Path, required=True)
    args = parser.parse_args()
    verify_bundle_manifest(args.bundle_root, args.manifest)
    service = TrustedProviderService(
        socket_path=args.socket_path,
        state_root=args.state_root,
        public_key_path=args.public_key,
        queue_root=args.queue_root,
    )
    serve(service)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
