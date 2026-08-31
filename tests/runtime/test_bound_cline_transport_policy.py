"""RED tests for the immutable bound-worker policy sidecar."""

from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from pathlib import Path

import pytest
from runtime.integrations.bound_cline_transport import (
    BoundWorkerConfig,
    TransportProtocolError,
    _load_policy,
    _validate_policy,
)

from tests.runtime.test_bound_cline_transport import _config, _request


def _policy_payload(request_payload_hash: str = "d" * 64) -> dict[str, object]:
    return {
        "artifact_path": "artifact.txt",
        "allowed_tools": ["editor", "run_commands"],
        "request_payload_hash": request_payload_hash,
        "verification_command": "python verify_probe.py",
        "write_scopes": ["artifact.txt"],
    }


def _write_policy(config: BoundWorkerConfig, payload: dict[str, object]) -> BoundWorkerConfig:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8") + b"\n"
    config.policy_path.write_bytes(raw)
    return replace(config, policy_sha256=hashlib.sha256(raw).hexdigest())


def test_valid_policy_is_loaded_and_bound_to_request(tmp_path: Path) -> None:
    config = _config(tmp_path)
    config = _write_policy(config, _policy_payload())
    policy = _load_policy(config.policy_path)
    _validate_policy(
        policy,
        _request(tmp_path, workspace=config.recovery_worktree / "sandbox"),
        config,
    )
    assert policy.allowed_tools == ("editor", "run_commands")


def test_policy_payload_hash_mismatch_is_rejected(tmp_path: Path) -> None:
    config = _config(tmp_path)
    config = _write_policy(config, _policy_payload("0" * 64))
    policy = _load_policy(config.policy_path)
    request = _request(tmp_path, workspace=config.recovery_worktree / "sandbox")
    with pytest.raises(TransportProtocolError, match="payload hash"):
        _validate_policy(policy, request, config)


def test_policy_rejects_unknown_tool(tmp_path: Path) -> None:
    config = _config(tmp_path)
    config = _write_policy(
        config,
        {
            **_policy_payload(),
            "allowed_tools": ["editor", "read_files"],
        },
    )
    with pytest.raises(TransportProtocolError, match="tool"):
        _load_policy(config.policy_path)


def test_policy_rejects_shell_expansion(tmp_path: Path) -> None:
    config = _config(tmp_path)
    config = _write_policy(
        config,
        {**_policy_payload(), "verification_command": "cd /tmp && python verify_probe.py"},
    )
    with pytest.raises(TransportProtocolError, match="command"):
        _load_policy(config.policy_path)
