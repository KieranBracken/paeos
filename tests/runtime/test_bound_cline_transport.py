"""RED tests for the bound Cline transport contract."""

from __future__ import annotations

from pathlib import Path

import pytest
from paeos.model_router.types import ModelFamily
from runtime.integrations.bound_cline_transport import (
    BoundWorkerConfig,
    TransportProtocolError,
    _validate_binding,
    _validate_paths,
)
from runtime.integrations.bridge_protocol import Disposition, RequestEnvelope


def _request(tmp_path: Path, *, workspace: Path | None = None) -> RequestEnvelope:
    sandbox = workspace or (tmp_path / "sandbox")
    sandbox.mkdir(parents=True, exist_ok=True)
    return RequestEnvelope(
        schema_version="paeos-bridge-v2",
        request_id="request-1",
        transaction_key="a" * 64,
        created_at="2026-08-31T00:00:00Z",
        expires_at="2026-08-31T01:00:00Z",
        goal_id="goal-1",
        run_id="run-1",
        stage_id="L12",
        role="BUILDER",
        workspace_root=str(sandbox),
        worker_transport_id="headless:bound-cline",
        worker_session_id="session-1",
        worker_pid=1,
        worker_tty=None,
        worker_model_provider="cline-pass",
        worker_model_id="z-ai/glm-5.3-flash",
        worker_model_family=ModelFamily.GLM.value,
        semantic_hash="b" * 64,
        evidence_manifest_hash="c" * 64,
        payload_hash="d" * 64,
        allowed_dispositions=(Disposition.CONTINUE, Disposition.REMAND),
    )


def _config(tmp_path: Path, *, branch_name: str = "codex/recovery") -> BoundWorkerConfig:
    state_root = tmp_path / "state"
    worktree = tmp_path / "worktree"
    package = tmp_path / "package"
    state_root.mkdir()
    worktree.mkdir()
    package.mkdir()
    files = {}
    for name in ("node", "host.mjs", "sdk.mjs", "core.mjs", "qualification.json"):
        path = package / name
        path.write_text("synthetic", encoding="utf-8")
        files[name] = path
    return BoundWorkerConfig(
        state_root=state_root,
        recovery_worktree=worktree,
        branch_name=branch_name,
        candidate_head="e" * 40,
        node_executable=files["node"],
        host_module=files["host.mjs"],
        sdk_entrypoint=files["sdk.mjs"],
        core_entrypoint=files["core.mjs"],
        qualification_record=files["qualification.json"],
        provider_id="cline-pass",
        model_id="z-ai/glm-5.3-flash",
        model_family=ModelFamily.GLM,
        session_id="session-1",
    )


def test_valid_request_and_config_pass_binding(tmp_path: Path) -> None:
    config = _config(tmp_path)
    request = _request(tmp_path, workspace=config.recovery_worktree / "sandbox")
    _validate_binding(request, config)


def test_main_branch_is_rejected_before_process_launch(tmp_path: Path) -> None:
    config = _config(tmp_path, branch_name="main")
    request = _request(tmp_path, workspace=config.recovery_worktree / "sandbox")
    with pytest.raises(TransportProtocolError, match="main/trunk"):
        _validate_binding(request, config)


def test_workspace_outside_recovery_worktree_is_rejected(tmp_path: Path) -> None:
    config = _config(tmp_path)
    request = _request(tmp_path, workspace=tmp_path / "outside")
    with pytest.raises(TransportProtocolError, match="worktree"):
        _validate_binding(request, config)


def test_symlinked_host_and_prompt_are_rejected(tmp_path: Path) -> None:
    config = _config(tmp_path)
    link = config.host_module.with_name("host-link.mjs")
    link.symlink_to(config.host_module)
    prompt = config.recovery_worktree / "prompt.md"
    prompt.write_text("prompt", encoding="utf-8")
    request = _request(tmp_path, workspace=config.recovery_worktree / "sandbox")
    with pytest.raises(TransportProtocolError, match="symlink"):
        _validate_paths(request, config, prompt_path=prompt, host_path=link)
