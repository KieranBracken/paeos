"""One-time host bootstrap for the trusted Codex Builder supervisor.

This installer is deliberately separate from ``install_trusted_worker_launcher.py``.  It creates
only the Codex supervisor LaunchAgent and its fixed capability material.  The auth file is copied
without being parsed or printed; no credential value is stored in this source or emitted by the
health result.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import plistlib
import shutil
import subprocess
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path

from nacl.signing import SigningKey

REPO_ROOT = Path(__file__).resolve().parents[1]
INSTALL_BASE = Path("/Users/bob/Library/Application Support/PAEOS/trusted-codex-worker")
LAUNCH_AGENT = Path(
    "/Users/bob/Library/LaunchAgents/com.paeos.trusted-codex-worker-supervisor.plist"
)
LABEL = "com.paeos.trusted-codex-worker-supervisor"
WORKSPACE_ROOT = REPO_ROOT / "ops" / ".trusted-codex-worker" / "workspaces"
QUEUE_ROOT = REPO_ROOT / "ops" / ".trusted-codex-worker" / "queue"
REPO_REQUEST_KEY = REPO_ROOT / "ops" / ".trusted-codex-worker" / "request.key"
REPO_RESPONSE_VERIFY_KEY = REPO_ROOT / "ops" / ".trusted-codex-worker" / "response-verify.key"
REPO_QUALIFICATION_VERIFY_KEY = (
    REPO_ROOT / "ops" / ".trusted-codex-worker" / "qualification-verify.key"
)
REPO_PLANNER_QUALIFICATION = (
    REPO_ROOT / "ops" / ".trusted-codex-worker" / "planner-qualification-v2.json"
)
CODEX_AUTH_SOURCE = Path("/Users/bob/.codex/auth.json")
PYTHON = REPO_ROOT / ".venv" / "bin" / "python3"


def _resolved_directory(path: Path, *, label: str) -> Path:
    if not path.is_absolute():
        raise ValueError(f"{label} must be an absolute path")
    try:
        resolved = path.resolve(strict=True)
    except OSError as exc:
        raise RuntimeError(f"{label} is unavailable") from exc
    if not resolved.is_dir():
        raise RuntimeError(f"{label} is not a directory")
    return resolved


@dataclass(frozen=True, slots=True)
class RootBindings:
    """Resolved, immutable separation between bundle code and host runtime roots."""

    source_root: Path
    runtime_root: Path

    @classmethod
    def resolve(
        cls,
        *,
        source_root: Path | None = None,
        runtime_root: Path | None = None,
    ) -> RootBindings:
        default = _resolved_directory(REPO_ROOT, label="repository root")
        return cls(
            source_root=_resolved_directory(
                default if source_root is None else source_root, label="source root"
            ),
            runtime_root=_resolved_directory(
                default if runtime_root is None else runtime_root, label="runtime root"
            ),
        )


@dataclass(frozen=True, slots=True)
class RuntimePaths:
    """Repository-local runtime paths derived only from the selected runtime root."""

    root: Path

    @classmethod
    def from_root(cls, root: Path) -> RuntimePaths:
        return cls(_resolved_directory(root, label="runtime root"))

    @property
    def python(self) -> Path:
        return self.root / ".venv" / "bin" / "python3"

    @property
    def workspace_root(self) -> Path:
        return self.root / "ops" / ".trusted-codex-worker" / "workspaces"

    @property
    def queue_root(self) -> Path:
        return self.root / "ops" / ".trusted-codex-worker" / "queue"

    @property
    def request_key(self) -> Path:
        return self.root / "ops" / ".trusted-codex-worker" / "request.key"

    @property
    def response_verify_key(self) -> Path:
        return self.root / "ops" / ".trusted-codex-worker" / "response-verify.key"

    @property
    def qualification_verify_key(self) -> Path:
        return self.root / "ops" / ".trusted-codex-worker" / "qualification-verify.key"

    @property
    def qualification_path(self) -> Path:
        return self.root / "ops" / ".trusted-codex-worker" / "qualification.json"

    @property
    def planner_qualification_path(self) -> Path:
        return self.root / "ops" / ".trusted-codex-worker" / "planner-qualification-v2.json"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path)
    parser.add_argument("--runtime-root", type=Path)
    return parser.parse_args(argv)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_regular(path: Path, *, label: str) -> None:
    if not path.is_absolute() or path.is_symlink() or not path.is_file():
        raise RuntimeError(f"{label} is unavailable")


def _read_private_key(path: Path) -> SigningKey:
    _safe_regular(path, label="request signing key")
    mode = path.stat().st_mode & 0o777
    if mode & 0o077:
        raise RuntimeError("request signing key permissions are too broad")
    raw = path.read_text(encoding="ascii").strip()
    if len(raw) != 64:
        raise RuntimeError("request signing key is malformed")
    try:
        return SigningKey(bytes.fromhex(raw))
    except ValueError as exc:
        raise RuntimeError("request signing key is malformed") from exc


def _read_public_key(path: Path, *, label: str) -> bytes:
    _safe_regular(path, label=label)
    if path.stat().st_mode & 0o022:
        raise RuntimeError(f"{label} permissions are too broad")
    raw = path.read_text(encoding="ascii").strip()
    if len(raw) != 64:
        raise RuntimeError(f"{label} is malformed")
    try:
        return bytes.fromhex(raw)
    except ValueError as exc:
        raise RuntimeError(f"{label} is malformed") from exc


def _existing_response_signing_key(
    runtime_paths: RuntimePaths | None = None,
) -> SigningKey | None:
    """Load the active supervisor identity for a versioned, key-stable upgrade."""

    runtime_paths = runtime_paths or RuntimePaths.from_root(REPO_ROOT)
    identity_paths = (
        LAUNCH_AGENT,
        runtime_paths.response_verify_key,
        runtime_paths.qualification_verify_key,
    )
    present = tuple(path.exists() or path.is_symlink() for path in identity_paths)
    if not any(present):
        return None
    if not all(present):
        raise RuntimeError("installed response identity is incomplete")
    _safe_regular(LAUNCH_AGENT, label="trusted Codex LaunchAgent")
    try:
        payload = plistlib.loads(LAUNCH_AGENT.read_bytes())
    except (OSError, plistlib.InvalidFileException) as exc:
        raise RuntimeError("trusted Codex LaunchAgent is malformed") from exc
    arguments = payload.get("ProgramArguments") if isinstance(payload, dict) else None
    if payload.get("Label") != LABEL or not isinstance(arguments, list):
        raise RuntimeError("trusted Codex LaunchAgent identity is invalid")
    if arguments.count("--response-signing-key") != 1:
        raise RuntimeError("trusted Codex response key binding is invalid")
    index = arguments.index("--response-signing-key")
    if index + 1 >= len(arguments) or not isinstance(arguments[index + 1], str):
        raise RuntimeError("trusted Codex response key binding is invalid")
    response_key_path = Path(arguments[index + 1])
    _safe_regular(response_key_path, label="response signing key")
    try:
        install_root = INSTALL_BASE.resolve(strict=True)
        canonical_key = response_key_path.resolve(strict=True)
        canonical_key.relative_to(install_root)
    except (OSError, ValueError) as exc:
        raise RuntimeError("response signing key escaped the install root") from exc
    if response_key_path != canonical_key or response_key_path.stat().st_mode & 0o077:
        raise RuntimeError("response signing key permissions or path are invalid")
    raw = response_key_path.read_text(encoding="ascii").strip()
    try:
        response_key = SigningKey(bytes.fromhex(raw))
    except (ValueError, TypeError) as exc:
        raise RuntimeError("response signing key is malformed") from exc
    expected = bytes(response_key.verify_key)
    if (
        _read_public_key(runtime_paths.response_verify_key, label="response verification key")
        != expected
        or _read_public_key(
            runtime_paths.qualification_verify_key, label="qualification verification key"
        )
        != expected
    ):
        raise RuntimeError("installed response identity mismatch")
    return response_key


def _ensure_request_key(runtime_paths: RuntimePaths | None = None) -> SigningKey:
    runtime_paths = runtime_paths or RuntimePaths.from_root(REPO_ROOT)
    request_key_path = runtime_paths.request_key
    request_key_path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    if request_key_path.exists() or request_key_path.is_symlink():
        return _read_private_key(request_key_path)
    key = SigningKey.generate()
    fd = os.open(request_key_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        os.write(fd, (bytes(key).hex() + "\n").encode("ascii"))
        os.fsync(fd)
    finally:
        os.close(fd)
    return key


def _copy_auth_state(destination: Path) -> None:
    _safe_regular(CODEX_AUTH_SOURCE, label="Codex auth state")
    source_mode = CODEX_AUTH_SOURCE.stat().st_mode & 0o777
    if source_mode & 0o077:
        raise RuntimeError("Codex auth state permissions are too broad")
    destination.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    if destination.exists() or destination.is_symlink():
        raise RuntimeError("dedicated Codex auth destination already exists")
    shutil.copyfile(CODEX_AUTH_SOURCE, destination)
    os.chmod(destination, 0o600)


def _copy_source(source: Path, destination: Path) -> None:
    _safe_regular(source, label=f"supervisor source {source.name}")
    destination.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    shutil.copyfile(source, destination)
    os.chmod(destination, 0o444)


def _build_bundle(
    staging: Path,
    request_key: SigningKey,
    *,
    source_root: Path | None = None,
) -> tuple[Path, Path, str]:
    bundle = staging / "bundle"
    source_root = _resolved_directory(
        REPO_ROOT if source_root is None else source_root, label="source root"
    )
    for relative in (
        "ops/trusted_codex_worker_supervisor.py",
        "runtime/integrations/process_supervisor.py",
        "runtime/integrations/task_scoped_responses_broker.py",
        "runtime/integrations/worker_confinement.py",
        "runtime/builder_transport.py",
        "runtime/planner_transport.py",
        "kernel/sandbox_backend.py",
        "kernel/sandbox.py",
        "kernel/ledger.py",
    ):
        _copy_source(source_root / relative, bundle / relative)
    for package in ("ops", "runtime", "runtime/integrations", "kernel"):
        package_init = bundle / package / "__init__.py"
        if not package_init.exists():
            package_init.write_text("", encoding="utf-8")
            os.chmod(package_init, 0o444)
    request_public = bundle / "request-verify.key"
    request_public.write_text(bytes(request_key.verify_key).hex() + "\n", encoding="ascii")
    os.chmod(request_public, 0o444)
    files = {
        str(path.relative_to(bundle)): _sha256(path)
        for path in sorted(bundle.rglob("*"))
        if path.is_file()
    }
    manifest = {
        "schema": "paeos.trusted-codex-bundle/1",
        "installer_revision": 1,
        "files": files,
    }
    manifest_bytes = (json.dumps(manifest, sort_keys=True, separators=(",", ":")) + "\n").encode(
        "utf-8"
    )
    manifest_path = staging / "manifest.json"
    manifest_path.write_bytes(manifest_bytes)
    os.chmod(manifest_path, 0o444)
    version = hashlib.sha256(manifest_bytes).hexdigest()[:20]
    return bundle, manifest_path, version


def _write_plist(
    path: Path,
    *,
    bundle: Path,
    manifest: Path,
    state: Path,
    logs: Path,
    codex_home: Path,
    response_key: Path,
    planner_qualification: Path,
    runtime_paths: RuntimePaths | None = None,
) -> None:
    runtime_paths = runtime_paths or RuntimePaths.from_root(REPO_ROOT)
    if planner_qualification != runtime_paths.planner_qualification_path:
        raise ValueError("planner qualification path must belong to the runtime root")
    payload = {
        "Label": LABEL,
        "ProgramArguments": [
            str(runtime_paths.python),
            str(bundle / "ops" / "trusted_codex_worker_supervisor.py"),
            "--bundle-root",
            str(bundle),
            "--bundle-manifest",
            str(manifest),
            "--queue-root",
            str(runtime_paths.queue_root),
            "--state-root",
            str(state),
            "--workspace-root",
            str(runtime_paths.workspace_root),
            "--codex-home",
            str(codex_home),
            "--request-verify-key",
            str(bundle / "request-verify.key"),
            "--response-signing-key",
            str(response_key),
            "--qualification-path",
            str(runtime_paths.qualification_path),
            "--planner-qualification-path",
            str(planner_qualification),
        ],
        "EnvironmentVariables": {
            "HOME": str(INSTALL_BASE / "supervisor-home"),
            "LANG": "C.UTF-8",
            "LC_ALL": "C",
            "PATH": "/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin",
            "PYTHONPATH": str(bundle),
        },
        "RunAtLoad": True,
        "KeepAlive": True,
        "ProcessType": "Background",
        "Umask": 63,
        "StandardOutPath": str(logs / "stdout.log"),
        "StandardErrorPath": str(logs / "stderr.log"),
    }
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    path.write_bytes(plistlib.dumps(payload, fmt=plistlib.FMT_XML, sort_keys=True))
    os.chmod(path, 0o600)


def _launchctl(args: list[str]) -> tuple[int, bytes, bytes]:
    result = subprocess.run(
        ["/bin/launchctl", *args],
        capture_output=True,
        check=False,
        timeout=15,
    )
    return result.returncode, result.stdout, result.stderr


def _activate_agent(domain: str) -> None:
    existing, _stdout, _stderr = _launchctl(["print", f"{domain}/{LABEL}"])
    if existing == 0:
        _launchctl(["bootout", f"{domain}/{LABEL}"])
        for delay in (0.2, 0.5, 1.0, 2.0, 4.0):
            visible, _stdout, _stderr = _launchctl(["print", f"{domain}/{LABEL}"])
            if visible != 0:
                break
            time.sleep(delay)
        else:
            raise RuntimeError("trusted Codex supervisor did not stop cleanly")
    for delay in (0.2, 0.5, 1.0):
        bootstrapped, _stdout, _stderr = _launchctl(["bootstrap", domain, str(LAUNCH_AGENT)])
        visible, _stdout, _stderr = _launchctl(["print", f"{domain}/{LABEL}"])
        if bootstrapped == 0 and visible == 0:
            break
        time.sleep(delay)
    else:
        raise RuntimeError("trusted Codex supervisor bootstrap failed")
    for delay in (0.2, 0.5, 1.0):
        kicked, _stdout, _stderr = _launchctl(["kickstart", "-k", f"{domain}/{LABEL}"])
        if kicked == 0:
            return
        time.sleep(delay)
    raise RuntimeError("trusted Codex supervisor start failed")


def install(
    *,
    source_root: Path | None = None,
    runtime_root: Path | None = None,
) -> dict[str, str]:
    roots = RootBindings.resolve(source_root=source_root, runtime_root=runtime_root)
    runtime_paths = RuntimePaths.from_root(roots.runtime_root)
    if not runtime_paths.python.is_file() or not os.access(runtime_paths.python, os.X_OK):
        raise RuntimeError("runtime-root virtualenv interpreter is unavailable")
    _safe_regular(CODEX_AUTH_SOURCE, label="Codex auth state")
    request_key = _ensure_request_key(runtime_paths)
    existing_response_key = _existing_response_signing_key(runtime_paths)
    INSTALL_BASE.mkdir(mode=0o700, parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="trusted-codex-install-", dir=INSTALL_BASE) as raw:
        staging = Path(raw)
        bundle, manifest, version = _build_bundle(
            staging, request_key, source_root=roots.source_root
        )
        final_root = INSTALL_BASE / f"supervisor-{version}"
        if final_root.exists() or final_root.is_symlink():
            raise RuntimeError("exact trusted Codex supervisor bundle already exists")
        final_root.mkdir(mode=0o700)
        state = final_root / "state"
        logs = final_root / "logs"
        codex_home = final_root / "codex-home"
        response_key_path = final_root / "response-signing.key"
        for directory in (state, logs, codex_home):
            directory.mkdir(mode=0o700)
        response_key = existing_response_key or SigningKey.generate()
        response_key_fd = os.open(response_key_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        try:
            os.write(response_key_fd, (bytes(response_key).hex() + "\n").encode("ascii"))
            os.fsync(response_key_fd)
        finally:
            os.close(response_key_fd)
        _copy_auth_state(codex_home / "auth.json")
        shutil.copytree(bundle, final_root / "bundle")
        shutil.copy2(manifest, final_root / "manifest.json")
        os.chmod(final_root / "manifest.json", 0o444)
        for path in (final_root / "bundle").rglob("*"):
            if path.is_dir():
                os.chmod(path, 0o555)
            elif not path.is_symlink():
                os.chmod(path, 0o444)
        os.chmod(final_root / "bundle", 0o555)
        _write_plist(
            LAUNCH_AGENT,
            bundle=final_root / "bundle",
            manifest=final_root / "manifest.json",
            state=state,
            logs=logs,
            codex_home=codex_home,
            response_key=response_key_path,
            planner_qualification=runtime_paths.planner_qualification_path,
            runtime_paths=runtime_paths,
        )
        response_public = runtime_paths.response_verify_key
        qualification_public = runtime_paths.qualification_verify_key
        public_values = {
            response_public: bytes(response_key.verify_key).hex() + "\n",
            qualification_public: bytes(response_key.verify_key).hex() + "\n",
        }
        for public_path, public_value in public_values.items():
            if public_path.exists() or public_path.is_symlink():
                if _read_public_key(public_path, label=public_path.name) != bytes(
                    response_key.verify_key
                ):
                    raise RuntimeError(f"identity path mismatch: {public_path.name}")
                continue
            public_path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            public_path.write_text(public_value, encoding="ascii")
            os.chmod(public_path, 0o600)
    _activate_agent(f"gui/{os.getuid()}")
    identity_path = final_root / "state" / "identity.json"
    deadline = time.monotonic() + 10.0
    while time.monotonic() < deadline:
        if identity_path.is_file() and not identity_path.is_symlink():
            identity = json.loads(identity_path.read_text(encoding="utf-8"))
            if isinstance(identity, dict) and isinstance(
                identity.get("supervisor_identity_sha256"), str
            ):
                return {
                    "status": "ACTIVE",
                    "label": LABEL,
                    "supervisor_identity_sha256": identity["supervisor_identity_sha256"],
                    "bundle_sha256": _sha256(final_root / "manifest.json"),
                }
        time.sleep(0.2)
    raise RuntimeError("trusted Codex supervisor health identity was not published")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    result = install(source_root=args.source_root, runtime_root=args.runtime_root)
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
