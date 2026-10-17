"""Physical prerequisite qualification for the host-supervised Codex Builder path.

Exit 0 is reserved for a genuine supervisor response plus all required confinement observations.
Any missing service, provider failure, malformed response, or canary failure exits 17 so the Court
can classify the attempt as REMAND. Each attempt keeps its signed request and response receipts in
its private workspace; the only provider content in this qualification is the synthetic nonce.
Credential material and arbitrary project content are never copied into the attempt record.
"""

from __future__ import annotations

import errno
import hashlib
import json
import os
import plistlib
import re
import stat
import subprocess
import time
import uuid
from pathlib import Path

from nacl.exceptions import BadSignatureError
from nacl.signing import SigningKey, VerifyKey
from runtime.builder_transport import (
    REQUIRED_CANARIES,
    BuilderTransportReadiness,
)
from runtime.integrations import SessionSpec
from runtime.integrations.trusted_codex_transport import (
    DEFAULT_BUILDER_TRANSPORT_QUALIFICATION,
    DEFAULT_BUILDER_TRANSPORT_VERIFY_KEY,
    DEFAULT_CODEX_REQUEST_KEY,
    DEFAULT_CODEX_RESPONSE_VERIFY_KEY,
    DEFAULT_CODEX_WORKSPACE_ROOT,
    HostCodexWorkerTransport,
    TrustedCodexTransportError,
)

from ops.trusted_codex_worker_supervisor import _canonical_bytes, verify_bundle_manifest

SUPERVISOR_LABEL = "com.paeos.trusted-codex-worker-supervisor"
LAUNCH_AGENT = Path(
    "/Users/bob/Library/LaunchAgents/com.paeos.trusted-codex-worker-supervisor.plist"
)
_QUALIFICATION_ID_RE = re.compile(r"^[0-9a-f]{32}$")


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _read_key(path: Path, *, private: bool) -> bytes:
    if not path.is_absolute() or path.is_symlink() or not path.is_file():
        raise RuntimeError(f"identity unavailable: {path.name}")
    mode = stat.S_IMODE(path.stat().st_mode)
    if mode & 0o077 if private else mode & 0o022:
        raise RuntimeError(f"identity permissions invalid: {path.name}")
    raw = path.read_text(encoding="ascii").strip()
    if len(raw) != 64:
        raise RuntimeError(f"identity length invalid: {path.name}")
    try:
        return bytes.fromhex(raw)
    except ValueError as exc:
        raise RuntimeError(f"identity encoding invalid: {path.name}") from exc


def _write_private(path: Path, payload: bytes) -> None:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        os.write(fd, payload)
        os.fsync(fd)
    finally:
        os.close(fd)
    os.replace(temporary, path)
    os.chmod(path, 0o600)


def _classify_nested_seatbelt() -> dict[str, object]:
    """Reproduce the known outer-context failure without exposing the OS error text."""

    if not Path("/usr/bin/sandbox-exec").is_file():
        return {"available": False, "classification": "mechanism_unavailable"}
    parent_environment = dict(os.environ)
    parent_environment["PAEOS_SYNTHETIC_PARENT_SECRET"] = "synthetic-only-probe"
    try:
        result = subprocess.run(
            [
                "/usr/bin/sandbox-exec",
                "-p",
                "(version 1)\n(deny default)\n",
                "/opt/homebrew/bin/codex",
                "--version",
            ],
            capture_output=True,
            check=False,
            timeout=10,
            env=parent_environment,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return {"available": True, "classification": type(exc).__name__}
    stderr = result.stderr
    classification = "unexpected_success" if result.returncode == 0 else "nested_seatbelt_denied"
    if b"Operation not permitted" not in stderr and result.returncode != 0:
        classification = "nested_seatbelt_nonzero"
    return {
        "available": True,
        "classification": classification,
        "exit_code": result.returncode,
        "stderr_sha256": _sha256(stderr),
        "stderr_bytes": len(stderr),
    }


def _record_attempt(workspace: Path, document: dict[str, object]) -> None:
    _write_private(
        workspace / "attempt.json",
        (json.dumps(document, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8"),
    )


def _launch_argument(arguments: list[object], name: str) -> Path:
    try:
        index = arguments.index(name)
        value = arguments[index + 1]
    except (ValueError, IndexError) as exc:
        raise RuntimeError("trusted Codex LaunchAgent argument is missing") from exc
    if not isinstance(value, str):
        raise RuntimeError("trusted Codex LaunchAgent argument is malformed")
    return Path(value)


def _signed_supervisor_identity(path: Path, verify_key: VerifyKey) -> dict[str, object]:
    if path.is_symlink() or not path.is_file():
        raise RuntimeError("trusted Codex supervisor identity is unavailable")
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError("trusted Codex supervisor identity is malformed") from exc
    if not isinstance(document, dict):
        raise RuntimeError("trusted Codex supervisor identity is malformed")
    signature = document.pop("signature", None)
    expected_fields = {
        "schema",
        "supervisor_identity_sha256",
        "provider_id",
        "model_id",
        "family",
        "codex_executable",
        "workspace_root",
        "boot_id",
    }
    if set(document) != expected_fields or not isinstance(signature, str):
        raise RuntimeError("trusted Codex supervisor identity fields are invalid")
    try:
        verify_key.verify(_canonical_bytes(document), bytes.fromhex(signature))
    except (BadSignatureError, ValueError) as exc:
        raise RuntimeError("trusted Codex supervisor identity signature is invalid") from exc
    if (
        document.get("schema") != "paeos.trusted-codex-worker-service/1"
        or document.get("provider_id") != "codex"
        or document.get("model_id") != "gpt-5.6-sol"
        or document.get("family") != "gpt"
        or document.get("workspace_root") != str(DEFAULT_CODEX_WORKSPACE_ROOT)
        or not isinstance(document.get("boot_id"), str)
        or not document["boot_id"]
        or document.get("supervisor_identity_sha256") != _sha256(bytes(verify_key))
    ):
        raise RuntimeError("trusted Codex supervisor identity binding is invalid")
    return document


def _stale_lifecycle_records(state_root: Path) -> list[dict[str, object]]:
    """Return inactive historical records only when their recorded worker PID is gone."""

    stale: list[dict[str, object]] = []
    for lifecycle_path in state_root.glob("*/lifecycle.json"):
        if lifecycle_path.is_symlink() or not lifecycle_path.is_file():
            raise RuntimeError("trusted Codex lifecycle state is unsafe")
        try:
            lifecycle = json.loads(lifecycle_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise RuntimeError("trusted Codex lifecycle state is malformed") from exc
        if not isinstance(lifecycle, dict):
            raise RuntimeError("trusted Codex lifecycle state is malformed")
        lifecycle_state = lifecycle.get("state")
        if lifecycle_state not in {"STARTING", "RUNNING", "PROGRESS"}:
            continue

        process_path = lifecycle_path.parent / "process.json"
        if process_path.is_symlink() or not process_path.is_file():
            raise RuntimeError("active lifecycle record has no trustworthy process receipt")
        try:
            process = json.loads(process_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise RuntimeError("active lifecycle process receipt is malformed") from exc
        if not isinstance(process, dict):
            raise RuntimeError("active lifecycle process receipt is malformed")
        pid = process.get("pid")
        terminal_state = process.get("terminal_state")
        if (
            not isinstance(pid, int)
            or isinstance(pid, bool)
            or pid <= 0
            or not isinstance(terminal_state, str)
            or not terminal_state
        ):
            raise RuntimeError("active lifecycle process identity is incomplete")
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            pass
        except PermissionError:
            raise RuntimeError("active request process is not verifiably stopped") from None
        except OSError as exc:
            if exc.errno != errno.ESRCH:
                raise RuntimeError("active request process state is unavailable") from None
        else:
            raise RuntimeError("active request process is still running; restart withheld")

        stale.append(
            {
                "request_identity_sha256": _sha256(lifecycle_path.parent.name.encode("ascii")),
                "lifecycle_state": lifecycle_state,
                "worker_pid": pid,
                "worker_terminal_state": terminal_state,
                "classification": "STALE_WORKER_PID_NOT_RUNNING",
            }
        )
    return stale


def _restart_supervisor() -> dict[str, object]:
    if LAUNCH_AGENT.is_symlink() or not LAUNCH_AGENT.is_file():
        raise RuntimeError("trusted Codex LaunchAgent is unavailable")
    if stat.S_IMODE(LAUNCH_AGENT.stat().st_mode) != 0o600:
        raise RuntimeError("trusted Codex LaunchAgent permissions are invalid")
    try:
        agent = plistlib.loads(LAUNCH_AGENT.read_bytes())
    except (OSError, plistlib.InvalidFileException) as exc:
        raise RuntimeError("trusted Codex LaunchAgent is malformed") from exc
    arguments = agent.get("ProgramArguments") if isinstance(agent, dict) else None
    if (
        not isinstance(agent, dict)
        or agent.get("Label") != SUPERVISOR_LABEL
        or not isinstance(arguments, list)
        or not all(isinstance(value, str) for value in arguments)
    ):
        raise RuntimeError("trusted Codex LaunchAgent identity is invalid")
    bundle = _launch_argument(arguments, "--bundle-root")
    manifest = _launch_argument(arguments, "--bundle-manifest")
    state_root = _launch_argument(arguments, "--state-root")
    queue_root = _launch_argument(arguments, "--queue-root")
    workspace_root = _launch_argument(arguments, "--workspace-root")
    request_verify_key = _launch_argument(arguments, "--request-verify-key")
    qualification_path = _launch_argument(arguments, "--qualification-path")
    environment = agent.get("EnvironmentVariables")
    if (
        not state_root.is_absolute()
        or state_root.is_symlink()
        or not state_root.is_dir()
        or state_root.resolve(strict=True) != state_root
        or not queue_root.is_absolute()
        or queue_root.is_symlink()
        or not queue_root.is_dir()
        or queue_root.resolve(strict=True) != queue_root
        or queue_root != DEFAULT_CODEX_REQUEST_KEY.parent / "queue"
        or workspace_root != DEFAULT_CODEX_WORKSPACE_ROOT
        or request_verify_key != bundle / "request-verify.key"
        or qualification_path != DEFAULT_BUILDER_TRANSPORT_QUALIFICATION
        or len(arguments) < 2
        or arguments[0] != "/Users/bob/GitHub/paeos/.venv/bin/python3"
        or arguments[1] != str(bundle / "ops" / "trusted_codex_worker_supervisor.py")
        or agent.get("RunAtLoad") is not True
        or agent.get("KeepAlive") is not True
        or not isinstance(environment, dict)
        or set(environment) != {"HOME", "LANG", "LC_ALL", "PATH", "PYTHONPATH"}
        or any(str(name).endswith("_API_KEY") for name in environment)
    ):
        raise RuntimeError("trusted Codex queue binding is invalid")
    verify_bundle_manifest(bundle, manifest)
    response_key = VerifyKey(_read_key(DEFAULT_CODEX_RESPONSE_VERIFY_KEY, private=False))
    identity_path = state_root / "identity.json"
    previous = _signed_supervisor_identity(identity_path, response_key)

    if any(queue_root.glob("*.request.json")):
        raise RuntimeError("trusted Codex queue is not idle; supervisor restart withheld")
    stale_lifecycle_records = _stale_lifecycle_records(state_root)

    active = subprocess.run(
        ["/bin/launchctl", "print", f"gui/{os.getuid()}/{SUPERVISOR_LABEL}"],
        capture_output=True,
        check=False,
        timeout=10,
    )
    if active.returncode != 0:
        raise RuntimeError("trusted Codex supervisor is not active")
    result = subprocess.run(
        ["/bin/launchctl", "kickstart", "-k", f"gui/{os.getuid()}/{SUPERVISOR_LABEL}"],
        capture_output=True,
        check=False,
        timeout=15,
    )
    if result.returncode != 0:
        raise RuntimeError("trusted Codex supervisor restart failed")
    deadline = time.monotonic() + 10.0
    while time.monotonic() < deadline:
        try:
            current = _signed_supervisor_identity(identity_path, response_key)
        except RuntimeError:
            time.sleep(0.1)
            continue
        if current.get("boot_id") != previous.get("boot_id"):
            if current.get("supervisor_identity_sha256") != previous.get(
                "supervisor_identity_sha256"
            ):
                raise RuntimeError("trusted Codex supervisor identity changed during restart")
            return {
                "previous_boot_id": str(previous["boot_id"]),
                "current_boot_id": str(current["boot_id"]),
                "supervisor_identity_sha256": str(current["supervisor_identity_sha256"]),
                "stale_lifecycle_records": stale_lifecycle_records,
            }
        time.sleep(0.1)
    raise RuntimeError("trusted Codex supervisor did not publish a fresh signed boot identity")


def qualify() -> int:
    workspace_root = DEFAULT_CODEX_WORKSPACE_ROOT
    workspace_root.mkdir(mode=0o700, parents=True, exist_ok=True)
    attempt_id = uuid.uuid4().hex
    if _QUALIFICATION_ID_RE.fullmatch(attempt_id) is None:
        raise RuntimeError("qualification attempt identity generator is malformed")
    workspace = workspace_root / f"ws-qualification-{attempt_id}"
    workspace.mkdir(mode=0o700)
    nonce = uuid.uuid4().hex
    (workspace / "transport-probe.txt").write_text(nonce + "\n", encoding="utf-8")
    evidence_root = workspace / "qualification-evidence"
    evidence_root.mkdir(mode=0o700)
    task_id = f"t-builder-transport-qualification-{attempt_id}"
    goal_id = f"g-builder-transport-qualification-{attempt_id}"
    run_id = f"r-builder-transport-qualification-{attempt_id}"
    attempt: dict[str, object] = {
        "schema": "paeos.builder-transport-qualification-attempt/1",
        "attempt_id": attempt_id,
        "status": "PREPARED_NOT_SUBMITTED",
        "task_id": task_id,
        "goal_id": goal_id,
        "run_id": run_id,
        "workspace_id": workspace.name,
        "workspace": str(workspace),
    }
    _record_attempt(workspace, attempt)
    client: HostCodexWorkerTransport | None = None
    try:
        nested = _classify_nested_seatbelt()
        attempt["nested_seatbelt"] = nested
        attempt["supervisor_restart"] = _restart_supervisor()
        _record_attempt(workspace, attempt)
        request_key = SigningKey(_read_key(DEFAULT_CODEX_REQUEST_KEY, private=True))
        response_key = VerifyKey(_read_key(DEFAULT_CODEX_RESPONSE_VERIFY_KEY, private=False))
        client = HostCodexWorkerTransport(
            queue_root=DEFAULT_CODEX_REQUEST_KEY.parent / "queue",
            workspace_root=workspace_root,
            request_signing_key=request_key,
            response_verify_key=response_key,
            timeout_s=660,
            evidence_root=evidence_root,
        )
        spec = SessionSpec(
            workspace=workspace,
            prompt=(
                "Read transport-probe.txt and return the nonce exactly once in your final response. "
                "Do not read any other file and do not use network tools beyond the model request."
            ),
            allowed_tools=(),
            read_scopes=("transport-probe.txt",),
            timeout_s=600,
            task_id=task_id,
            goal_id=goal_id,
            run_id=run_id,
            stage="IMPLEMENT",
        )
        attempt["status"] = "SUBMITTED"
        _record_attempt(workspace, attempt)
        result = client.run(spec)
        observation = client.last_observation
        if observation is None:
            raise RuntimeError("supervisor returned no observation")
        if (
            result.exit_code != 0
            or result.failure_code is not None
            or result.lifecycle_state != "RETURNED"
        ):
            raise RuntimeError("bounded provider process did not complete successfully")
        if result.transcript.count(nonce) != 1:
            raise RuntimeError("bounded provider response did not contain the task nonce")
        if set(observation.get("canaries", {})) < REQUIRED_CANARIES:
            raise RuntimeError("supervisor canary set is incomplete")
        canaries = observation["canaries"]
        if not isinstance(canaries, dict) or any(
            canaries.get(key) != "PASS" for key in REQUIRED_CANARIES
        ):
            raise RuntimeError("supervisor confinement canary failed")
        if observation.get("broker_request_count") != 1:
            raise RuntimeError("qualification used more than one model request")
        readiness = BuilderTransportReadiness(
            DEFAULT_BUILDER_TRANSPORT_QUALIFICATION,
            VerifyKey(_read_key(DEFAULT_BUILDER_TRANSPORT_VERIFY_KEY, private=False)),
        )
        qualified = readiness.require()
        if (
            qualified.request_sha256 != client.last_request_sha256
            or qualified.response_sha256 != client.last_response_sha256
            or qualified.supervisor_identity_sha256 != observation["supervisor_identity_sha256"]
        ):
            raise RuntimeError("readiness record is not bound to the observed supervisor response")
        qualification_sha256 = _sha256(DEFAULT_BUILDER_TRANSPORT_QUALIFICATION.read_bytes())
        attempt.update(
            {
                "status": "PROVEN",
                "request_sha256": client.last_request_sha256,
                "response_sha256": client.last_response_sha256,
                "supervisor_identity_sha256": qualified.supervisor_identity_sha256,
                "qualification_sha256": qualification_sha256,
                "evidence_sha256": qualified.evidence_sha256,
            }
        )
        _record_attempt(workspace, attempt)
        print(
            json.dumps(
                {
                    "status": "PROVEN",
                    "attempt_id": attempt_id,
                    "workspace_id": workspace.name,
                    "request_sha256": client.last_request_sha256,
                    "response_sha256": client.last_response_sha256,
                    "qualification_sha256": qualification_sha256,
                    "evidence_sha256": qualified.evidence_sha256,
                },
                sort_keys=True,
            )
        )
        return 0
    except (OSError, RuntimeError, TrustedCodexTransportError, ValueError, TypeError) as exc:
        request_sha256 = client.last_request_sha256 if client is not None else None
        response_sha256 = client.last_response_sha256 if client is not None else None
        status = "UNKNOWN" if request_sha256 is not None and response_sha256 is None else "REMAND"
        attempt.update(
            {
                "status": status,
                "request_sha256": request_sha256,
                "response_sha256": response_sha256,
                "failure_class": type(exc).__name__,
            }
        )
        _record_attempt(workspace, attempt)
        print(
            json.dumps(
                {
                    "status": status,
                    "attempt_id": attempt_id,
                    "workspace_id": workspace.name,
                    "request_sha256": request_sha256,
                    "response_sha256": response_sha256,
                    "failure_class": type(exc).__name__,
                },
                sort_keys=True,
            )
        )
        return 17


if __name__ == "__main__":
    raise SystemExit(qualify())
