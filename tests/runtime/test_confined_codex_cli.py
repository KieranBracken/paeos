from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from runtime.integrations.mediated_worker_tools import WorkerToolScope


def test_confined_codex_argv_disables_shell_and_binds_only_parent_tools(tmp_path: Path) -> None:
    from ops.trusted_codex_worker_supervisor import build_confined_codex_argv

    workspace = tmp_path / "workspace"
    workspace.mkdir()
    scope = WorkerToolScope(
        workspace=workspace,
        artifacts={"readme": "README.md"},
        patch_targets={"readme": "README.md"},
        tests={"unit": (sys.executable, "-m", "pytest", "-q")},
    )
    argv = build_confined_codex_argv(
        Path("/opt/homebrew/Caskroom/codex/0.147.0/bin/codex"),
        prompt="Read the approved artifact, make the bounded patch, then run the named test.",
        workspace=workspace,
        broker_base_url="http://127.0.0.1:43123/v1",
        scope=scope,
        python_executable=Path(sys.executable),
    )
    rendered = "\n".join(argv)

    assert "--disable" in argv and "shell_tool" in argv
    assert "--sandbox" in argv and argv[argv.index("--sandbox") + 1] == "read-only"
    assert "--dangerously-bypass-approvals-and-sandbox" not in argv
    # The parent supplies an empty isolated CODEX_HOME; no user config or approval file is inherited.
    assert "--ignore-user-config" not in argv and "--ignore-rules" in argv
    assert "plugins" in argv and "apps" in argv
    assert "mcp_servers.paeos_mediated" in rendered
    assert "mcp_servers.paeos_mediated.required=true" in argv
    assert not any(arg.startswith("mcp_servers.paeos_mediated.enabled_tools=") for arg in argv)
    assert 'mcp_servers.paeos_mediated.default_tools_approval_mode="auto"' in argv
    assert "PAEOS_TASK_SCOPE_B64" in rendered
    assert "analytics.enabled=false" in argv
    assert 'otel.metrics_exporter="none"' in argv
    assert "ephemeral-task-token" not in rendered
    assert "receipt_key" not in rendered and 'sandbox="' not in rendered


def test_confined_cli_arguments_reject_non_loopback_provider_and_scope_mismatch(
    tmp_path: Path,
) -> None:
    import pytest
    from ops.trusted_codex_worker_supervisor import build_confined_codex_argv
    from runtime.integrations.mediated_worker_tools import MediatedWorkerError

    workspace = tmp_path / "workspace"
    workspace.mkdir()
    other = tmp_path / "other"
    other.mkdir()
    scope = WorkerToolScope(workspace=workspace, artifacts={}, patch_targets={}, tests={})

    with pytest.raises(MediatedWorkerError):
        build_confined_codex_argv(
            Path("/opt/homebrew/Caskroom/codex/0.147.0/bin/codex"),
            prompt="do bounded work",
            workspace=other,
            broker_base_url="http://127.0.0.1:43123/v1",
            scope=scope,
            python_executable=Path(sys.executable),
        )
    with pytest.raises(MediatedWorkerError):
        build_confined_codex_argv(
            Path("/opt/homebrew/Caskroom/codex/0.147.0/bin/codex"),
            prompt="do bounded work",
            workspace=workspace,
            broker_base_url="https://provider.invalid/v1",
            scope=scope,
            python_executable=Path(sys.executable),
        )


def test_supervisor_fails_closed_before_legacy_bypass_launch_when_mcp_is_unsupported(
    tmp_path: Path, monkeypatch
) -> None:
    import pytest
    from nacl.signing import SigningKey

    from ops import trusted_codex_worker_supervisor as supervisor_module

    codex_home = tmp_path / "codex-home"
    codex_home.mkdir()
    auth_path = codex_home / "auth.json"
    auth_path.write_text("{}\n", encoding="utf-8")
    auth_path.chmod(0o600)
    request_key = SigningKey.generate().verify_key
    request_key_path = tmp_path / "request-verify-key.hex"
    request_key_path.write_text(request_key.encode().hex(), encoding="ascii")
    service = supervisor_module.TrustedCodexWorkerSupervisor(
        queue_root=tmp_path / "queue",
        state_root=tmp_path / "state",
        workspace_root=tmp_path / "workspaces",
        codex_home=codex_home,
        request_verify_key_path=request_key_path,
        response_signing_key=SigningKey.generate(),
    )
    workspace = service.workspace_root / "ws-synthetic"
    workspace.mkdir(parents=True)

    class LocalBroker:
        task_token = "synthetic-only"
        base_url = "http://127.0.0.1:43123/v1"
        loopback_port = 43123

        def __init__(self, **_kwargs) -> None:
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_args) -> None:
            return None

    service._policy = lambda *_args, **_kwargs: (
        object(),
        {"PATH": os.defpath},
        supervisor_module._fixed_codex_executable(),
    )
    canary_calls: list[bool] = []
    service._run_canaries = lambda *_args: canary_calls.append(True)
    monkeypatch.setattr(supervisor_module, "ParentOwnedResponsesBroker", LocalBroker)

    def unexpected_legacy_launch(*_args, **_kwargs):
        raise AssertionError("unsupported mediated-tool inventory reached the legacy launcher")

    monkeypatch.setattr(supervisor_module, "_codex_argv", unexpected_legacy_launch)
    monkeypatch.setattr(supervisor_module, "run_bounded_process", unexpected_legacy_launch)

    with pytest.raises(supervisor_module.SupervisorFailure, match="supported mediated MCP"):
        service._run_request(
            {
                "workspace_id": workspace.name,
                "task_id": "t-synthetic",
                "goal_id": "g-synthetic",
                "run_id": "r-synthetic",
                "stage": "IMPLEMENT",
                "prompt": "synthetic blocked request",
            },
            "synthetic-request",
        )

    assert not canary_calls
    lifecycle = tmp_path / "state" / "synthetic-request" / "lifecycle.json"
    assert lifecycle.is_file()
    assert '"error_code":"capability_failure"' in lifecycle.read_text(encoding="utf-8")


def test_real_pinned_cli_exposes_only_mediated_tools_to_local_fake_provider(tmp_path: Path) -> None:
    """Exercise the pinned CLI with loopback only and no user auth/configuration."""
    import json
    import threading
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

    import pytest
    from ops.trusted_codex_worker_supervisor import build_confined_codex_argv
    from runtime.integrations.worker_confinement import policy_for_worker

    codex = Path("/opt/homebrew/bin/codex")
    if not codex.exists():
        pytest.fail("pinned Codex CLI is not installed; actual CLI inventory was not tested")

    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "README.md").write_text("approved artifact\n", encoding="utf-8")
    worker_home = workspace / ".worker-home"
    worker_codex_home = worker_home / ".codex"
    worker_temp = workspace / ".worker-tmp"
    worker_home.mkdir()
    worker_codex_home.mkdir()
    worker_temp.mkdir()
    env = {
        "HOME": str(worker_home),
        "CODEX_HOME": str(worker_codex_home),
        "PATH": os.defpath,
        "LANG": "C",
        "LC_ALL": "C",
        "TMPDIR": str(worker_temp),
        "PAEOS_TASK_BROKER_TOKEN": "local-fake-provider-token",
    }
    version_policy = policy_for_worker(
        workspace=workspace,
        read_roots=(workspace, Path(sys.base_prefix).resolve()),
        write_roots=(workspace,),
        runtime_home=Path(env["CODEX_HOME"]),
        temp_root=Path(env["TMPDIR"]),
    )
    version_argv = version_policy.wrap_argv((str(codex.resolve(strict=True)), "--version"))
    version_result = subprocess.run(
        version_argv,
        cwd=workspace,
        env=env,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert version_result.returncode == 0, version_result.stderr[-2000:]
    version = version_result.stdout.strip()
    if version != "codex-cli 0.147.0":
        pytest.fail(f"unexpected Codex CLI version for pinned test: {version}")

    python_executable = (Path(sys.base_prefix).resolve() / "bin" / "python3.13").resolve(
        strict=True
    )
    scope = WorkerToolScope(
        workspace=workspace,
        artifacts={"readme": "README.md"},
        patch_targets={"readme": "README.md"},
        tests={"unit": (str(python_executable), "-c", "print('TEST_OK')")},
    )
    observed: dict[str, object] = {
        "tools": None,
        "calls": [],
        "request_count": 0,
        "request_keys": None,
        "tool_choice": None,
    }

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            length = int(self.headers.get("Content-Length", "0"))
            request = json.loads(self.rfile.read(length))
            tools = request.get("tools")
            observed["tools"] = tools
            observed["request_keys"] = sorted(request)
            observed["tool_choice"] = request.get("tool_choice")
            observed["request_count"] = int(observed["request_count"]) + 1
            response = {
                "id": "resp_test",
                "object": "response",
                "created_at": 0,
                "status": "completed",
                "model": "gpt-5.6-sol",
                "output": [
                    {
                        "id": "msg_test",
                        "type": "message",
                        "role": "assistant",
                        "status": "completed",
                        "content": [
                            {
                                "type": "output_text",
                                "text": "bounded local test complete",
                                "annotations": [],
                            }
                        ],
                    }
                ],
                "usage": {"input_tokens": 1, "output_tokens": 1, "total_tokens": 2},
            }
            payload = (
                "event: response.completed\n"
                "data: " + json.dumps({"type": "response.completed", "response": response}) + "\n\n"
                "data: [DONE]\n\n"
            ).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, *_args: object) -> None:
            return

    class LocalServer(ThreadingHTTPServer):
        daemon_threads = True

    server = LocalServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        argv = build_confined_codex_argv(
            codex.resolve(),
            prompt="Use the read_artifact tool for artifact_id readme, then return a short response.",
            workspace=workspace,
            broker_base_url=f"http://127.0.0.1:{server.server_port}/v1",
            scope=scope,
            python_executable=python_executable,
        )
        policy = policy_for_worker(
            workspace=workspace,
            read_roots=(
                workspace,
                Path(__file__).resolve().parents[2]
                / "runtime/integrations/mediated_worker_tools.py",
                Path(sys.base_prefix).resolve(),
            ),
            write_roots=(workspace,),
            runtime_home=Path(env["CODEX_HOME"]),
            temp_root=Path(env["TMPDIR"]),
            loopback_port=server.server_port,
            read_probe_paths=(Path("/etc/codex/requirements.toml"),),
        )
        launch_argv = policy.wrap_argv(tuple(argv))
        assert launch_argv[:3] == (
            "/usr/bin/sandbox-exec",
            "-p",
            policy.seatbelt_profile,
        )
        proc = subprocess.run(
            launch_argv,
            cwd=workspace,
            env=env,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
        assert proc.returncode == 0, proc.stderr[-4000:] + "\n" + proc.stdout[-4000:]
        names = [item.get("name") for item in observed["tools"] or []]
        assert names == [
            "mcp__paeos_mediated__read_artifact",
            "mcp__paeos_mediated__propose_patch",
            "mcp__paeos_mediated__run_test",
        ], (
            f"tools={observed['tools']!r}; request_keys={observed['request_keys']!r}; "
            f"tool_choice={observed['tool_choice']!r}; request_count={observed['request_count']!r}; "
            f"mcp_logs={[line for line in proc.stderr.splitlines() if 'paeos_mediated' in line or 'tools/list' in line or 'dynamic_tool_count' in line]!r}; "
            f"stderr={proc.stderr[-2000:]!r}; stdout={proc.stdout[-4000:]!r}"
        )
        assert "shell" not in names and "exec_command" not in names
        assert "bounded local test complete" in proc.stdout
        assert not (workspace / "escaped").exists()
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_process_supervisor_executes_the_canonical_path_it_records(tmp_path: Path) -> None:
    from runtime.integrations.process_supervisor import run_bounded_process

    workspace = tmp_path / "workspace"
    workspace.mkdir()
    alias = tmp_path / "python-alias"
    alias.symlink_to(sys.executable)
    observation = run_bounded_process(
        (str(alias), "-c", "print('PROCESS_OK')"),
        cwd=workspace,
        environment={"PATH": os.defpath},
        start_timeout_s=5,
        execution_timeout_s=10,
        state_path=tmp_path / "process-state.json",
    )
    assert observation.argv[0] == str(Path(sys.executable).resolve())
    assert observation.executable == observation.argv[0]
    assert observation.stdout == b"PROCESS_OK\n"
    assert observation.exit_code == 0
