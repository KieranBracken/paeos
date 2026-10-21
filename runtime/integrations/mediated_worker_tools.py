"""Closed parent-issued tool envelope for an isolated Codex worker.

The worker receives only three MCP tools. Paths and test commands come from a
parent-owned immutable scope; the model cannot supply a path, executable,
environment, sandbox profile, or receipt-signing key.
"""

from __future__ import annotations

import base64
import contextlib
import fcntl
import hashlib
import json
import os
import re
import selectors
import signal
import stat
import subprocess
import sys
import time
import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from types import MappingProxyType
from typing import Any

__all__ = [
    "MediatedWorkerError",
    "MediatedWorkerTools",
    "WorkerToolScope",
    "main",
]

SCOPE_SCHEMA = "paeos.mediated-worker-scope/1"
MCP_PROTOCOL_VERSION = "2025-03-26"
SCOPE_ENV = "PAEOS_TASK_SCOPE_B64"
MAX_SCOPE_BYTES = 128 * 1024
MAX_RPC_LINE_BYTES = 2 * 1024 * 1024
MAX_ARTIFACT_BYTES = 1024 * 1024
MAX_PATCH_BYTES = 1024 * 1024
MAX_TEST_OUTPUT_BYTES = 64 * 1024
TEST_TIMEOUT_SECONDS = 120.0
_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_HUNK_RE = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@(?: .*)?\n$")
_FIXED_PATH = "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"


class MediatedWorkerError(RuntimeError):
    """A parent-scoped worker operation was invalid or could not be completed."""


def _canonical_workspace(path: Path) -> Path:
    path = Path(path)
    if not path.is_absolute() or path.is_symlink() or not path.is_dir():
        raise MediatedWorkerError("workspace must be an existing absolute non-symlink directory")
    try:
        resolved = path.resolve(strict=True)
    except OSError as exc:
        raise MediatedWorkerError("workspace is unavailable") from exc
    if resolved != path:
        raise MediatedWorkerError("workspace is not canonical")
    return resolved


def _relative_path(value: object, *, label: str) -> str:
    if not isinstance(value, str) or not value or "\x00" in value or "\\" in value:
        raise MediatedWorkerError(f"{label} is not a safe relative path")
    path = PurePosixPath(value)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise MediatedWorkerError(f"{label} is not a safe relative path")
    if path.as_posix() != value:
        raise MediatedWorkerError(f"{label} is not canonical")
    return value


def _id_map(value: object, *, label: str) -> Mapping[str, str]:
    if not isinstance(value, Mapping):
        raise MediatedWorkerError(f"{label} must be an object")
    normalized: dict[str, str] = {}
    for item_id, relative in value.items():
        if not isinstance(item_id, str) or _ID_RE.fullmatch(item_id) is None:
            raise MediatedWorkerError(f"{label} contains an invalid identifier")
        if item_id in normalized:
            raise MediatedWorkerError(f"{label} contains a duplicate identifier")
        normalized[item_id] = _relative_path(relative, label=label)
    return MappingProxyType(dict(sorted(normalized.items())))


@dataclass(frozen=True, slots=True)
class WorkerToolScope:
    """Parent-issued workspace and operation allowlists for one worker process."""

    workspace: Path
    artifacts: Mapping[str, str]
    patch_targets: Mapping[str, str]
    tests: Mapping[str, tuple[str, ...]]

    def __post_init__(self) -> None:
        workspace = _canonical_workspace(self.workspace)
        artifacts = _id_map(self.artifacts, label="artifacts")
        patch_targets = _id_map(self.patch_targets, label="patch_targets")
        if not isinstance(self.tests, Mapping):
            raise MediatedWorkerError("tests must be an object")
        tests: dict[str, tuple[str, ...]] = {}
        for test_id, raw_argv in self.tests.items():
            if not isinstance(test_id, str) or _ID_RE.fullmatch(test_id) is None:
                raise MediatedWorkerError("tests contains an invalid identifier")
            if not isinstance(raw_argv, (tuple, list)) or not raw_argv:
                raise MediatedWorkerError("each named test must have a fixed non-empty argv")
            argv = tuple(raw_argv)
            if any(not isinstance(item, str) or not item or "\x00" in item for item in argv):
                raise MediatedWorkerError("test argv must contain non-empty strings")
            executable = Path(argv[0])
            if not executable.is_absolute():
                raise MediatedWorkerError("test executable must be an absolute pinned path")
            try:
                resolved = executable.resolve(strict=True)
            except OSError as exc:
                raise MediatedWorkerError("test executable is unavailable") from exc
            if not resolved.is_file() or not os.access(resolved, os.X_OK):
                raise MediatedWorkerError("test executable is not executable")
            tests[test_id] = (str(resolved), *argv[1:])
        object.__setattr__(self, "workspace", workspace)
        object.__setattr__(self, "artifacts", artifacts)
        object.__setattr__(self, "patch_targets", patch_targets)
        object.__setattr__(self, "tests", MappingProxyType(dict(sorted(tests.items()))))

    def to_json(self) -> str:
        value = {
            "schema": SCOPE_SCHEMA,
            "workspace": str(self.workspace),
            "artifacts": dict(self.artifacts),
            "patch_targets": dict(self.patch_targets),
            "tests": {test_id: list(argv) for test_id, argv in self.tests.items()},
        }
        return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)

    @classmethod
    def from_mapping(cls, value: object) -> WorkerToolScope:
        expected = {"schema", "workspace", "artifacts", "patch_targets", "tests"}
        if not isinstance(value, dict) or set(value) != expected:
            raise MediatedWorkerError("scope fields are incomplete or unsupported")
        if value.get("schema") != SCOPE_SCHEMA or not isinstance(value.get("workspace"), str):
            raise MediatedWorkerError("scope schema or workspace is invalid")
        raw_tests = value.get("tests")
        if not isinstance(raw_tests, dict):
            raise MediatedWorkerError("tests must be an object")
        return cls(
            workspace=Path(value["workspace"]),
            artifacts=value["artifacts"],
            patch_targets=value["patch_targets"],
            tests={
                test_id: tuple(argv) if isinstance(argv, list) else argv
                for test_id, argv in raw_tests.items()
            },
        )

    @classmethod
    def from_json(cls, value: str) -> WorkerToolScope:
        if not isinstance(value, str) or len(value.encode("utf-8")) > MAX_SCOPE_BYTES:
            raise MediatedWorkerError("scope is missing or exceeds its size limit")

        def unique_pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
            result: dict[str, object] = {}
            for key, item in pairs:
                if key in result:
                    raise MediatedWorkerError("scope contains duplicate fields")
                result[key] = item
            return result

        try:
            parsed = json.loads(value, object_pairs_hook=unique_pairs)
        except (json.JSONDecodeError, UnicodeError) as exc:
            raise MediatedWorkerError("scope JSON is malformed") from exc
        return cls.from_mapping(parsed)


def _tool_definitions() -> list[dict[str, object]]:
    return [
        {
            "name": "read_artifact",
            "description": "Read one artifact selected by its parent-issued identifier.",
            "annotations": {
                "readOnlyHint": True,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            },
            "inputSchema": {
                "type": "object",
                "properties": {"artifact_id": {"type": "string", "pattern": _ID_RE.pattern}},
                "required": ["artifact_id"],
                "additionalProperties": False,
            },
        },
        {
            "name": "propose_patch",
            "description": "Apply one unified patch to its parent-authorized target after base-hash verification.",
            "annotations": {
                "readOnlyHint": False,
                "destructiveHint": True,
                "idempotentHint": False,
                "openWorldHint": False,
            },
            "inputSchema": {
                "type": "object",
                "properties": {
                    "patch_id": {"type": "string", "pattern": _ID_RE.pattern},
                    "expected_sha256": {"type": "string", "pattern": _SHA256_RE.pattern},
                    "unified_diff": {"type": "string", "maxLength": MAX_PATCH_BYTES},
                },
                "required": ["patch_id", "expected_sha256", "unified_diff"],
                "additionalProperties": False,
            },
        },
        {
            "name": "run_test",
            "description": "Run one parent-named acceptance test using its fixed executable and arguments.",
            "annotations": {
                "readOnlyHint": False,
                "destructiveHint": True,
                "idempotentHint": False,
                "openWorldHint": False,
            },
            "inputSchema": {
                "type": "object",
                "properties": {"test_id": {"type": "string", "pattern": _ID_RE.pattern}},
                "required": ["test_id"],
                "additionalProperties": False,
            },
        },
    ]


class MediatedWorkerTools:
    """Implements the closed tool envelope behind a local MCP stdio server."""

    def __init__(self, scope: WorkerToolScope):
        if not isinstance(scope, WorkerToolScope):
            raise MediatedWorkerError("a parent-issued WorkerToolScope is required")
        self._scope = scope

    def list_tools(self) -> list[dict[str, object]]:
        return _tool_definitions()

    def invoke(self, name: object, arguments: object) -> dict[str, object]:
        if not isinstance(name, str) or not isinstance(arguments, dict):
            raise MediatedWorkerError("tool name and arguments are malformed")
        if name == "read_artifact":
            if set(arguments) != {"artifact_id"}:
                raise MediatedWorkerError("read_artifact arguments are incomplete or unsupported")
            artifact_id = arguments["artifact_id"]
            if not isinstance(artifact_id, str) or artifact_id not in self._scope.artifacts:
                raise MediatedWorkerError("artifact identifier is not parent-authorized")
            data = self._read_relative(self._scope.artifacts[artifact_id])
            try:
                text = data.decode("utf-8")
            except UnicodeDecodeError as exc:
                raise MediatedWorkerError("artifact is not UTF-8 text") from exc
            return {
                "artifact_id": artifact_id,
                "text": text,
                "sha256": hashlib.sha256(data).hexdigest(),
            }
        if name == "propose_patch":
            if set(arguments) != {"patch_id", "expected_sha256", "unified_diff"}:
                raise MediatedWorkerError("propose_patch arguments are incomplete or unsupported")
            patch_id = arguments["patch_id"]
            expected = arguments["expected_sha256"]
            unified_diff = arguments["unified_diff"]
            if not isinstance(patch_id, str) or patch_id not in self._scope.patch_targets:
                raise MediatedWorkerError("patch identifier is not parent-authorized")
            if not isinstance(expected, str) or _SHA256_RE.fullmatch(expected) is None:
                raise MediatedWorkerError("base digest is malformed")
            if (
                not isinstance(unified_diff, str)
                or len(unified_diff.encode("utf-8")) > MAX_PATCH_BYTES
            ):
                raise MediatedWorkerError("patch is missing or exceeds its size limit")
            relative = self._scope.patch_targets[patch_id]
            current = self._read_relative(relative)
            observed = hashlib.sha256(current).hexdigest()
            if observed != expected:
                raise MediatedWorkerError("patch base digest does not match current artifact")
            replacement = _apply_unified_diff(relative, current, unified_diff)
            self._atomic_replace(relative, current, replacement)
            return {
                "applied": True,
                "patch_id": patch_id,
                "sha256": hashlib.sha256(replacement).hexdigest(),
            }
        if name == "run_test":
            if set(arguments) != {"test_id"}:
                raise MediatedWorkerError("run_test arguments are incomplete or unsupported")
            test_id = arguments["test_id"]
            if not isinstance(test_id, str) or test_id not in self._scope.tests:
                raise MediatedWorkerError("test identifier is not parent-authorized")
            return self._run_test(test_id)
        raise MediatedWorkerError("tool is not in the parent-mediated interface")

    def _parent_fd(self, relative: str) -> tuple[int, str]:
        parts = PurePosixPath(relative).parts
        if not parts:
            raise MediatedWorkerError("empty relative path")
        directory_flag = getattr(os, "O_DIRECTORY", 0)
        nofollow_flag = getattr(os, "O_NOFOLLOW", 0)
        fd = os.open(self._scope.workspace, os.O_RDONLY | directory_flag)
        try:
            for component in parts[:-1]:
                next_fd = os.open(
                    component,
                    os.O_RDONLY | directory_flag | nofollow_flag,
                    dir_fd=fd,
                )
                os.close(fd)
                fd = next_fd
            return fd, parts[-1]
        except OSError as exc:
            os.close(fd)
            raise MediatedWorkerError(
                "artifact path contains a missing or symlinked directory"
            ) from exc

    def _read_relative(self, relative: str) -> bytes:
        parent_fd, name = self._parent_fd(relative)
        try:
            fd = os.open(name, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0), dir_fd=parent_fd)
            try:
                info = os.fstat(fd)
                if not stat.S_ISREG(info.st_mode) or info.st_size > MAX_ARTIFACT_BYTES:
                    raise MediatedWorkerError("artifact is not a bounded regular file")
                data = bytearray()
                while len(data) <= MAX_ARTIFACT_BYTES:
                    chunk = os.read(fd, min(65536, MAX_ARTIFACT_BYTES + 1 - len(data)))
                    if not chunk:
                        break
                    data.extend(chunk)
                if len(data) > MAX_ARTIFACT_BYTES:
                    raise MediatedWorkerError("artifact exceeds its size limit")
                return bytes(data)
            finally:
                os.close(fd)
        except OSError as exc:
            raise MediatedWorkerError("artifact is missing or symlinked") from exc
        finally:
            os.close(parent_fd)

    def _atomic_replace(self, relative: str, before: bytes, after: bytes) -> None:
        parent_fd, name = self._parent_fd(relative)
        current_fd = -1
        temporary = f".{name}.{uuid.uuid4().hex}.tmp"
        try:
            current_fd = os.open(name, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0), dir_fd=parent_fd)
            fcntl.flock(current_fd, fcntl.LOCK_EX)
            info = os.fstat(current_fd)
            if not stat.S_ISREG(info.st_mode) or info.st_size > MAX_ARTIFACT_BYTES:
                raise MediatedWorkerError("patch target is not a bounded regular file")
            latest = self._read_relative(relative)
            if latest != before:
                raise MediatedWorkerError("patch target changed before atomic replacement")
            write_fd = os.open(
                temporary,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
                stat.S_IMODE(info.st_mode),
                dir_fd=parent_fd,
            )
            try:
                view = memoryview(after)
                while view:
                    written = os.write(write_fd, view)
                    if written <= 0:
                        raise MediatedWorkerError("patch write made no progress")
                    view = view[written:]
                os.fsync(write_fd)
            finally:
                os.close(write_fd)
            os.replace(temporary, name, src_dir_fd=parent_fd, dst_dir_fd=parent_fd)
            os.fsync(parent_fd)
        except OSError as exc:
            raise MediatedWorkerError("patch target could not be atomically replaced") from exc
        finally:
            if current_fd >= 0:
                os.close(current_fd)
            with contextlib.suppress(FileNotFoundError):
                os.unlink(temporary, dir_fd=parent_fd)
            os.close(parent_fd)

    def _run_test(self, test_id: str) -> dict[str, object]:
        argv = self._scope.tests[test_id]
        runtime_dir = self._scope.workspace / ".paeos-worker-tools"
        home = runtime_dir / "home"
        temp = runtime_dir / "tmp"
        runtime_dir.mkdir(mode=0o700, exist_ok=True)
        home.mkdir(mode=0o700, exist_ok=True)
        temp.mkdir(mode=0o700, exist_ok=True)
        for path in (runtime_dir, home, temp):
            if path.is_symlink() or path.resolve(strict=True) != path:
                raise MediatedWorkerError("test runtime directory is not canonical")
        environment = {
            "HOME": str(home),
            "LANG": "C.UTF-8",
            "LC_ALL": "C",
            "PATH": _FIXED_PATH,
            "TMPDIR": str(temp),
        }
        started = time.monotonic()
        try:
            process = subprocess.Popen(
                argv,
                cwd=self._scope.workspace,
                env=environment,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                shell=False,
                start_new_session=True,
                bufsize=0,
            )
        except (OSError, ValueError) as exc:
            raise MediatedWorkerError("named test failed to start") from exc
        assert process.stdout is not None and process.stderr is not None
        selector = selectors.DefaultSelector()
        selector.register(process.stdout, selectors.EVENT_READ, "stdout")
        selector.register(process.stderr, selectors.EVENT_READ, "stderr")
        captured = {"stdout": bytearray(), "stderr": bytearray()}
        overflow = False
        timed_out = False
        deadline = started + TEST_TIMEOUT_SECONDS
        try:
            while selector.get_map():
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    timed_out = True
                    break
                for key, _ in selector.select(timeout=min(0.25, remaining)):
                    chunk = os.read(key.fileobj.fileno(), 65536)
                    if not chunk:
                        selector.unregister(key.fileobj)
                        continue
                    output = captured[key.data]
                    room = MAX_TEST_OUTPUT_BYTES - len(output)
                    output.extend(chunk[: max(0, room)])
                    if len(chunk) > room:
                        overflow = True
                        break
                if overflow:
                    break
            if process.poll() is None and (timed_out or overflow):
                os.killpg(process.pid, signal.SIGTERM)
                try:
                    process.wait(timeout=0.5)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait(timeout=0.5)
            else:
                process.wait(timeout=max(0.1, deadline - time.monotonic()))
        except (OSError, subprocess.TimeoutExpired) as exc:
            with contextlib.suppress(OSError):
                os.killpg(process.pid, signal.SIGKILL)
            process.wait(timeout=0.5)
            raise MediatedWorkerError("named test process could not be observed") from exc
        finally:
            selector.close()
            process.stdout.close()
            process.stderr.close()
        stdout = bytes(captured["stdout"])
        stderr = bytes(captured["stderr"])
        return {
            "test_id": test_id,
            "exit_code": process.returncode,
            "timed_out": timed_out,
            "output_limit_exceeded": overflow,
            "stdout": stdout.decode("utf-8", errors="replace"),
            "stderr": stderr.decode("utf-8", errors="replace"),
            "stdout_sha256": hashlib.sha256(stdout).hexdigest(),
            "stderr_sha256": hashlib.sha256(stderr).hexdigest(),
            "duration_ms": int((time.monotonic() - started) * 1000),
        }


def _apply_unified_diff(relative: str, before: bytes, unified_diff: str) -> bytes:
    if "\x00" in unified_diff or "\r" in unified_diff:
        raise MediatedWorkerError("patch encoding or line endings are unsupported")
    try:
        original = before.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise MediatedWorkerError("patch target is not UTF-8 text") from exc
    lines = unified_diff.splitlines(keepends=True)
    if len(lines) < 3 or lines[0] != f"--- a/{relative}\n" or lines[1] != f"+++ b/{relative}\n":
        raise MediatedWorkerError("patch must name exactly its parent-authorized target")
    old_lines = original.splitlines(keepends=True)
    output: list[str] = []
    cursor = 0
    index = 2
    changed = False
    while index < len(lines):
        match = _HUNK_RE.fullmatch(lines[index])
        if match is None:
            raise MediatedWorkerError("patch contains unsupported headers or malformed hunks")
        old_start = int(match.group(1))
        old_count = int(match.group(2) or "1")
        new_count = int(match.group(4) or "1")
        old_index = old_start - 1 if old_count else old_start
        if old_index < cursor or old_index > len(old_lines):
            raise MediatedWorkerError("patch hunk range is invalid")
        output.extend(old_lines[cursor:old_index])
        index += 1
        expected_old: list[str] = []
        replacement: list[str] = []
        observed_old = observed_new = 0
        while index < len(lines) and not lines[index].startswith("@@ "):
            line = lines[index]
            if not line.endswith("\n") or line.startswith("\\"):
                raise MediatedWorkerError("patch has unsupported no-newline or truncated records")
            marker, body = line[0], line[1:]
            if marker == " ":
                expected_old.append(body)
                replacement.append(body)
                observed_old += 1
                observed_new += 1
            elif marker == "-":
                expected_old.append(body)
                observed_old += 1
                changed = True
            elif marker == "+":
                replacement.append(body)
                observed_new += 1
                changed = True
            else:
                raise MediatedWorkerError("patch contains an unsupported record")
            index += 1
        if observed_old != old_count or observed_new != new_count:
            raise MediatedWorkerError("patch hunk counts do not match its records")
        if old_lines[old_index : old_index + old_count] != expected_old:
            raise MediatedWorkerError("patch context does not match the current file")
        output.extend(replacement)
        cursor = old_index + old_count
    if not changed:
        raise MediatedWorkerError("empty patches are not accepted")
    output.extend(old_lines[cursor:])
    return "".join(output).encode("utf-8")


def _json_object(raw: str) -> dict[str, object]:
    def unique_pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in pairs:
            if key in result:
                raise MediatedWorkerError("RPC message contains duplicate fields")
            result[key] = value
        return result

    parsed = json.loads(raw, object_pairs_hook=unique_pairs)
    if not isinstance(parsed, dict):
        raise MediatedWorkerError("RPC message must be an object")
    return parsed


def _handle_rpc(tools: MediatedWorkerTools, request: dict[str, object]) -> dict[str, object] | None:
    if request.get("jsonrpc") != "2.0" or not isinstance(request.get("method"), str):
        raise MediatedWorkerError("RPC envelope is malformed")
    method = request["method"]
    request_id = request.get("id")
    if request_id is None and method.startswith("notifications/"):
        return None
    if method == "initialize":
        params = request.get("params", {})
        version = (
            params.get("protocolVersion", MCP_PROTOCOL_VERSION)
            if isinstance(params, dict)
            else MCP_PROTOCOL_VERSION
        )
        if not isinstance(version, str):
            version = MCP_PROTOCOL_VERSION
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "protocolVersion": version,
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "paeos-mediated-worker", "version": "1"},
            },
        }
    if method == "ping":
        return {"jsonrpc": "2.0", "id": request_id, "result": {}}
    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": request_id, "result": {"tools": tools.list_tools()}}
    if method == "tools/call":
        params = request.get("params")
        if not isinstance(params, dict) or set(params) != {"name", "arguments"}:
            raise MediatedWorkerError("tool call parameters are incomplete or unsupported")
        result = tools.invoke(params["name"], params["arguments"])
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {"content": [{"type": "text", "text": json.dumps(result, sort_keys=True)}]},
        }
    if request_id is None:
        return None
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "error": {"code": -32601, "message": "method not found"},
    }


def serve_stdio(tools: MediatedWorkerTools, *, stdin: Any = None, stdout: Any = None) -> int:
    source = stdin or sys.stdin.buffer
    target = stdout or sys.stdout.buffer
    for raw in source:
        if len(raw) > MAX_RPC_LINE_BYTES:
            return 2
        try:
            request = _json_object(raw.decode("utf-8"))
            response = _handle_rpc(tools, request)
        except (MediatedWorkerError, UnicodeError, json.JSONDecodeError) as exc:
            request_id = None
            with contextlib.suppress(Exception):
                request_id = _json_object(raw.decode("utf-8")).get("id")
            response = {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {"code": -32602, "message": str(exc)},
            }
        if response is not None:
            target.write(
                json.dumps(response, sort_keys=True, separators=(",", ":")).encode() + b"\n"
            )
            target.flush()
    return 0


def main() -> int:
    if sys.argv[1:] != ["--stdio"]:
        return 2
    raw_scope = os.environ.get(SCOPE_ENV)
    if not isinstance(raw_scope, str) or len(raw_scope) > (MAX_SCOPE_BYTES * 2):
        return 2
    try:
        decoded = base64.b64decode(raw_scope, validate=True)
        scope = WorkerToolScope.from_json(decoded.decode("utf-8"))
    except (ValueError, UnicodeError, MediatedWorkerError):
        return 2
    return serve_stdio(MediatedWorkerTools(scope))


if __name__ == "__main__":  # pragma: no cover - exercised by the real MCP stdio test
    raise SystemExit(main())
