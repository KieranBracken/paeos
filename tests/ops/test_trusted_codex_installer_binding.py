from __future__ import annotations

import hashlib
import json
import os
import plistlib
import shutil
import stat
import subprocess
import sys
import time
from pathlib import Path

import pytest
from nacl.signing import SigningKey, VerifyKey

from ops import install_trusted_codex_worker_supervisor as installer

BUNDLE_MEMBERS = (
    "ops/trusted_codex_worker_supervisor.py",
    "runtime/integrations/mediated_worker_tools.py",
    "runtime/integrations/disclosure_frame.py",
    "runtime/integrations/process_supervisor.py",
    "runtime/integrations/task_scoped_responses_broker.py",
    "runtime/integrations/worker_confinement.py",
    "runtime/builder_transport.py",
    "runtime/planner_transport.py",
    "kernel/sandbox_backend.py",
    "kernel/sandbox.py",
    "kernel/ledger.py",
    "kernel/capability.py",
    "kernel/evidence.py",
    "kernel/types.py",
    "runtime/task_package.py",
)

EXPECTED_BUNDLE_IMPORT_CLOSURE = frozenset(
    {
        "ops/trusted_codex_worker_supervisor.py",
        "runtime/integrations/mediated_worker_tools.py",
        "runtime/integrations/disclosure_frame.py",
        "runtime/integrations/process_supervisor.py",
        "runtime/integrations/task_scoped_responses_broker.py",
        "runtime/integrations/worker_confinement.py",
        "runtime/builder_transport.py",
        "runtime/planner_transport.py",
        "runtime/task_package.py",
        "kernel/sandbox_backend.py",
        "kernel/sandbox.py",
        "kernel/ledger.py",
        "kernel/evidence.py",
        "kernel/capability.py",
        "kernel/types.py",
    }
)


def _write(path: Path, payload: bytes, mode: int = 0o600) -> None:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    path.write_bytes(payload)
    path.chmod(mode)


def _snapshot(root: Path) -> dict[str, tuple[bytes | None, int, bool]]:
    entries: dict[str, tuple[bytes | None, int, bool]] = {}
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root).as_posix()
        mode = stat.S_IMODE(path.lstat().st_mode)
        entries[relative] = (path.read_bytes() if path.is_file() else None, mode, path.is_symlink())
    return entries


def test_root_binding_defaults_and_partial_overrides(tmp_path: Path) -> None:
    source = tmp_path / "source"
    runtime = tmp_path / "runtime"
    source.mkdir()
    runtime.mkdir()
    default = installer.REPO_ROOT.resolve()

    legacy = installer.RootBindings.resolve()
    assert legacy.source_root == default
    assert legacy.runtime_root == default
    assert installer.RuntimePaths.from_root(legacy.runtime_root).python == installer.PYTHON

    source_only = installer.RootBindings.resolve(source_root=source)
    assert source_only.source_root == source.resolve()
    assert source_only.runtime_root == default
    runtime_only = installer.RootBindings.resolve(runtime_root=runtime)
    assert runtime_only.source_root == default
    assert runtime_only.runtime_root == runtime.resolve()

    parsed = installer.parse_args(["--source-root", str(source), "--runtime-root", str(runtime)])
    assert parsed.source_root == source
    assert parsed.runtime_root == runtime
    assert installer.parse_args([]).source_root is None
    assert installer.parse_args([]).runtime_root is None


def test_distinct_roots_bind_bundle_runtime_and_preserve_inputs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "reviewed-source"
    runtime = tmp_path / "host-runtime"
    output = tmp_path / "test-output"
    source.mkdir()
    runtime.mkdir()
    output.mkdir()

    expected_source: dict[str, bytes] = {}
    for index, relative in enumerate(BUNDLE_MEMBERS):
        payload = f"source-sentinel-{index}:{relative}\n".encode()
        expected_source[relative] = payload
        _write(source / relative, payload, 0o640)

    request_key = SigningKey.generate()
    request_key_bytes = (bytes(request_key).hex() + "\n").encode("ascii")
    request_path = runtime / "ops/.trusted-codex-worker/request.key"
    _write(request_path, request_key_bytes)
    (runtime / ".venv/bin").mkdir(parents=True)
    python_path = runtime / ".venv/bin/python3"
    _write(python_path, b"test interpreter marker\n", 0o700)

    response_key = SigningKey.generate()
    response_seed = (bytes(response_key).hex() + "\n").encode("ascii")
    host_install = tmp_path / "host-install"
    response_key_path = host_install / "supervisor-test/response-signing.key"
    _write(response_key_path, response_seed)
    launch_agent = tmp_path / "host-launch-agents/agent.plist"
    launch_agent.parent.mkdir(mode=0o700, parents=True)
    launch_agent.write_bytes(
        plistlib.dumps(
            {
                "Label": installer.LABEL,
                "ProgramArguments": [
                    "python3",
                    "supervisor.py",
                    "--response-signing-key",
                    str(response_key_path),
                ],
            }
        )
    )
    public = (bytes(response_key.verify_key).hex() + "\n").encode("ascii")
    _write(runtime / "ops/.trusted-codex-worker/response-verify.key", public)
    _write(runtime / "ops/.trusted-codex-worker/qualification-verify.key", public)
    _write(runtime / "ops/.trusted-codex-worker/qualification.json", b"qualification fixture\n")
    _write(
        runtime / "ops/.trusted-codex-worker/planner-qualification-v2.json", b"planner fixture\n"
    )

    roots = installer.RootBindings.resolve(source_root=source, runtime_root=runtime)
    runtime_paths = installer.RuntimePaths.from_root(roots.runtime_root)
    source_before = _snapshot(source)
    runtime_before = _snapshot(runtime)

    loaded_request_key = installer._ensure_request_key(runtime_paths)
    assert bytes(loaded_request_key) == bytes(request_key)
    monkeypatch.setattr(installer, "LAUNCH_AGENT", launch_agent)
    monkeypatch.setattr(installer, "INSTALL_BASE", host_install)
    loaded_response_key = installer._existing_response_signing_key(runtime_paths)
    assert loaded_response_key is not None
    assert bytes(loaded_response_key.verify_key) == bytes(response_key.verify_key)

    bundle, manifest, _version = installer._build_bundle(
        output / "staging", loaded_request_key, source_root=roots.source_root
    )
    manifest_payload = json.loads(manifest.read_text(encoding="utf-8"))
    for relative, expected in expected_source.items():
        assert (bundle / relative).read_bytes() == expected
        assert manifest_payload["files"][relative] == hashlib.sha256(expected).hexdigest()
    assert (bundle / "request-verify.key").read_text(encoding="ascii") == (
        bytes(request_key.verify_key).hex() + "\n"
    )

    plist_path = output / "launch-agent.plist"
    install_state = output / "install/supervisor-test/state"
    install_logs = output / "install/supervisor-test/logs"
    codex_home = output / "install/supervisor-test/codex-home"
    response_signer = output / "install/supervisor-test/response-signing.key"
    installer._write_plist(
        plist_path,
        bundle=bundle,
        manifest=manifest,
        state=install_state,
        logs=install_logs,
        codex_home=codex_home,
        response_key=response_signer,
        planner_qualification=runtime_paths.planner_qualification_path,
        runtime_paths=runtime_paths,
    )
    payload = plistlib.loads(plist_path.read_bytes())
    arguments = payload["ProgramArguments"]

    def argument_value(name: str) -> str:
        return arguments[arguments.index(name) + 1]

    assert arguments[0] == str(runtime_paths.python)
    assert argument_value("--queue-root") == str(runtime_paths.queue_root)
    assert argument_value("--workspace-root") == str(runtime_paths.workspace_root)
    assert argument_value("--qualification-path") == str(runtime_paths.qualification_path)
    assert argument_value("--planner-qualification-path") == str(
        runtime_paths.planner_qualification_path
    )
    assert argument_value("--request-verify-key") == str(bundle / "request-verify.key")
    assert argument_value("--response-signing-key") == str(response_signer)
    assert Path(payload["EnvironmentVariables"]["PYTHONPATH"]) == bundle
    assert source_before == _snapshot(source)
    assert runtime_before == _snapshot(runtime)


def test_explicit_root_arguments_fail_closed(tmp_path: Path) -> None:
    not_a_directory = tmp_path / "file"
    not_a_directory.write_text("x", encoding="utf-8")
    with pytest.raises(ValueError, match="absolute"):
        installer.RootBindings.resolve(source_root=Path("relative/source"))
    with pytest.raises(RuntimeError, match="source root"):
        installer.RootBindings.resolve(source_root=tmp_path / "missing")
    with pytest.raises(RuntimeError, match="runtime root"):
        installer.RootBindings.resolve(runtime_root=not_a_directory)


def test_built_bundle_starts_real_supervisor_and_signs_identity(tmp_path: Path) -> None:
    staging = tmp_path / "staging"
    staging.mkdir()
    request_signer = SigningKey.generate()
    bundle, manifest, _version = installer._build_bundle(
        staging, request_signer, source_root=installer.REPO_ROOT
    )
    assert frozenset(BUNDLE_MEMBERS) == EXPECTED_BUNDLE_IMPORT_CLOSURE
    manifest_payload = json.loads(manifest.read_text(encoding="utf-8"))
    assert set(manifest_payload["files"]) >= EXPECTED_BUNDLE_IMPORT_CLOSURE
    for path in bundle.rglob("*"):
        if path.is_dir():
            path.chmod(0o555)
        else:
            path.chmod(0o444)
    bundle.chmod(0o555)

    runtime = tmp_path / "runtime"
    codex_home = runtime / "codex-home"
    codex_home.mkdir(parents=True, mode=0o700)
    response_signer = SigningKey.generate()
    response_key_path = runtime / "response-signing.key"
    _write(response_key_path, (bytes(response_signer).hex() + "\n").encode("ascii"))
    queue_root = runtime / "queue"
    state_root = runtime / "state"
    workspace_root = runtime / "workspaces"
    args = [
        sys.executable,
        str(bundle / "ops/trusted_codex_worker_supervisor.py"),
        "--bundle-root",
        str(bundle),
        "--bundle-manifest",
        str(manifest),
        "--queue-root",
        str(queue_root),
        "--state-root",
        str(state_root),
        "--workspace-root",
        str(workspace_root),
        "--codex-home",
        str(codex_home),
        "--request-verify-key",
        str(bundle / "request-verify.key"),
        "--response-signing-key",
        str(response_key_path),
        "--qualification-path",
        str(runtime / "qualification.json"),
    ]
    environment = {
        "HOME": str(codex_home),
        "LANG": "C.UTF-8",
        "PATH": os.defpath,
        "PYTHONPATH": str(bundle),
    }
    process = subprocess.Popen(
        args,
        cwd=tmp_path,
        env=environment,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    identity_path = state_root / "identity.json"
    try:
        deadline = time.monotonic() + 10
        while not identity_path.exists() and process.poll() is None and time.monotonic() < deadline:
            time.sleep(0.05)
        if process.poll() is not None:
            stdout, stderr = process.communicate(timeout=2)
            pytest.fail(
                "supervisor exited before publishing identity; "
                f"stdout={stdout.decode(errors='replace')} "
                f"stderr={stderr.decode(errors='replace')}"
            )
        assert identity_path.is_file()
        assert process.poll() is None
        envelope = json.loads(identity_path.read_text(encoding="utf-8"))
        signature = bytes.fromhex(envelope.pop("signature"))
        canonical = (
            json.dumps(envelope, sort_keys=True, separators=(",", ":"), ensure_ascii=True) + "\n"
        ).encode("ascii")
        VerifyKey(bytes(response_signer.verify_key)).verify(canonical, signature)
        assert (
            envelope["supervisor_identity_sha256"]
            == hashlib.sha256(bytes(response_signer.verify_key)).hexdigest()
        )
        assert not list(queue_root.iterdir())
    finally:
        if process.poll() is None:
            process.terminate()
            process.wait(timeout=5)
        process.communicate(timeout=2)

    for index, (missing_path, missing_module) in enumerate(
        (
            ("kernel/types.py", b"kernel.types"),
            ("runtime/integrations/mediated_worker_tools.py", b"mediated_worker_tools"),
            ("runtime/integrations/disclosure_frame.py", b"disclosure_frame"),
        )
    ):
        incomplete_bundle = tmp_path / f"incomplete-bundle-{index}"
        shutil.copytree(bundle, incomplete_bundle)
        missing = incomplete_bundle / missing_path
        missing.parent.chmod(0o755)
        missing.unlink()
        negative_environment = {
            "PATH": os.defpath,
            "PYTHONPATH": str(incomplete_bundle),
        }
        negative = subprocess.run(
            [sys.executable, "-c", "import ops.trusted_codex_worker_supervisor"],
            cwd=tmp_path,
            env=negative_environment,
            capture_output=True,
            check=False,
            timeout=5,
        )
        assert negative.returncode != 0
        assert missing_module in negative.stderr


def test_bundle_rejects_symlinked_source_ancestor(tmp_path: Path) -> None:
    source = tmp_path / "reviewed-source"
    source.mkdir()
    outside_ops = tmp_path / "outside" / "ops"
    _write(outside_ops / "trusted_codex_worker_supervisor.py", b"outside bytes\n")
    (source / "ops").symlink_to(outside_ops, target_is_directory=True)
    for relative in BUNDLE_MEMBERS:
        if relative.startswith("ops/"):
            continue
        _write(source / relative, f"reviewed:{relative}\n".encode())

    staging = tmp_path / "staging"
    staging.mkdir()
    with pytest.raises(RuntimeError, match=r"symlink|source"):
        installer._build_bundle(staging, SigningKey.generate(), source_root=source)
    assert (outside_ops / "trusted_codex_worker_supervisor.py").read_bytes() == b"outside bytes\n"


def test_runtime_paths_reject_symlinked_ancestors_without_reading_or_creating_outside(
    tmp_path: Path,
) -> None:
    runtime = tmp_path / "runtime"
    runtime.mkdir()
    outside = tmp_path / "outside"
    outside_key = outside / "ops/.trusted-codex-worker/request.key"
    outside_signer = SigningKey.generate()
    _write(outside_key, (bytes(outside_signer).hex() + "\n").encode("ascii"))
    (runtime / "ops").symlink_to(outside / "ops", target_is_directory=True)
    runtime_paths = installer.RuntimePaths.from_root(runtime)
    original_key = outside_key.read_bytes()

    with pytest.raises(RuntimeError, match=r"symlink|runtime path"):
        installer._ensure_request_key(runtime_paths)
    with pytest.raises(RuntimeError, match=r"symlink|response key"):
        installer._read_public_key(runtime_paths.response_verify_key, label="response key")
    assert outside_key.read_bytes() == original_key
    assert not (outside / "ops/.trusted-codex-worker/response-verify.key").exists()


def test_runtime_paths_reject_symlinked_final_key_file(tmp_path: Path) -> None:
    runtime = tmp_path / "runtime"
    external = tmp_path / "external.key"
    runtime.mkdir()
    signer = SigningKey.generate()
    _write(external, (bytes(signer).hex() + "\n").encode("ascii"))
    key_path = runtime / "ops/.trusted-codex-worker/request.key"
    key_path.parent.mkdir(parents=True)
    key_path.symlink_to(external)
    runtime_paths = installer.RuntimePaths.from_root(runtime)

    with pytest.raises(RuntimeError, match=r"symlink|request signing key"):
        installer._ensure_request_key(runtime_paths)
    assert external.read_bytes() == (bytes(signer).hex() + "\n").encode("ascii")


@pytest.mark.parametrize("leaf", ["queue", "workspaces"])
def test_runtime_paths_validate_rejects_symlinked_worker_directories(
    tmp_path: Path, leaf: str
) -> None:
    runtime = tmp_path / "runtime"
    parent = runtime / "ops/.trusted-codex-worker"
    parent.mkdir(parents=True)
    outside = tmp_path / "outside"
    outside.mkdir()
    (parent / leaf).symlink_to(outside, target_is_directory=True)

    with pytest.raises(RuntimeError, match="symlink"):
        installer.RuntimePaths.from_root(runtime).validate()


def test_install_uses_reviewed_source_and_preserves_runtime_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "reviewed-source"
    runtime = tmp_path / "host-runtime"
    host = tmp_path / "host-install"
    launch_agents = tmp_path / "launch-agents"
    auth = tmp_path / "auth.json"
    source.mkdir()
    runtime.mkdir()
    host.mkdir()
    launch_agents.mkdir()

    for index, relative in enumerate(BUNDLE_MEMBERS):
        _write(source / relative, f"reviewed-source-{index}\n".encode(), 0o640)
        _write(runtime / relative, f"untracked-runtime-{index}\n".encode(), 0o600)

    request_key = SigningKey.generate()
    request_key_path = runtime / "ops/.trusted-codex-worker/request.key"
    _write(request_key_path, (bytes(request_key).hex() + "\n").encode())
    runtime_python = runtime / ".venv/bin/python3"
    _write(runtime_python, b"runtime interpreter fixture\n", 0o700)

    response_key = SigningKey.generate()
    previous_root = host / "supervisor-prior"
    previous_key = previous_root / "response-signing.key"
    _write(previous_key, (bytes(response_key).hex() + "\n").encode())
    launch_agent = launch_agents / "com.paeos.trusted-codex-worker-supervisor.plist"
    launch_agent.write_bytes(
        plistlib.dumps(
            {
                "Label": installer.LABEL,
                "ProgramArguments": [
                    "python3",
                    "supervisor.py",
                    "--response-signing-key",
                    str(previous_key),
                ],
            }
        )
    )
    verify_key_bytes = (bytes(response_key.verify_key).hex() + "\n").encode()
    _write(runtime / "ops/.trusted-codex-worker/response-verify.key", verify_key_bytes)
    _write(runtime / "ops/.trusted-codex-worker/qualification-verify.key", verify_key_bytes)
    _write(runtime / "ops/.trusted-codex-worker/qualification.json", b"existing qualification\n")
    _write(
        runtime / "ops/.trusted-codex-worker/planner-qualification-v2.json",
        b"existing planner qualification\n",
    )
    _write(auth, b"test auth fixture only\n")

    monkeypatch.setattr(installer, "INSTALL_BASE", host)
    monkeypatch.setattr(installer, "LAUNCH_AGENT", launch_agent)
    monkeypatch.setattr(installer, "CODEX_AUTH_SOURCE", auth)

    def publish_test_health(_domain: str) -> None:
        payload = plistlib.loads(launch_agent.read_bytes())
        arguments = payload["ProgramArguments"]
        state_root = Path(arguments[arguments.index("--state-root") + 1])
        (state_root / "identity.json").write_text(
            json.dumps({"supervisor_identity_sha256": "test-health-identity"}) + "\n",
            encoding="utf-8",
        )

    monkeypatch.setattr(installer, "_activate_agent", publish_test_health)
    source_before = _snapshot(source)
    runtime_before = _snapshot(runtime)

    result = installer.install(source_root=source, runtime_root=runtime)

    installed = plistlib.loads(launch_agent.read_bytes())
    arguments = installed["ProgramArguments"]

    def argument_value(name: str) -> str:
        return arguments[arguments.index(name) + 1]

    assert result["status"] == "ACTIVE"
    assert arguments[0] == str(runtime / ".venv/bin/python3")
    assert argument_value("--queue-root") == str(runtime / "ops/.trusted-codex-worker/queue")
    assert argument_value("--workspace-root") == str(
        runtime / "ops/.trusted-codex-worker/workspaces"
    )
    assert argument_value("--qualification-path") == str(
        runtime / "ops/.trusted-codex-worker/qualification.json"
    )
    assert argument_value("--planner-qualification-path") == str(
        runtime / "ops/.trusted-codex-worker/planner-qualification-v2.json"
    )
    assert bytes(installer._read_private_key(request_key_path)) == bytes(request_key)
    assert installer._read_public_key(
        runtime / "ops/.trusted-codex-worker/response-verify.key", label="response key"
    ) == bytes(response_key.verify_key)
    assert installer._read_public_key(
        runtime / "ops/.trusted-codex-worker/qualification-verify.key", label="qualification key"
    ) == bytes(response_key.verify_key)
    assert source_before == _snapshot(source)
    assert runtime_before == _snapshot(runtime)

    bundle_root = Path(argument_value("--bundle-root"))
    for index, relative in enumerate(BUNDLE_MEMBERS):
        assert (bundle_root / relative).read_bytes() == f"reviewed-source-{index}\n".encode()
