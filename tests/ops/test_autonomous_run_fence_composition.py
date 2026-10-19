from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from types import SimpleNamespace

import pytest
from kernel.ledger import InMemoryLedgerStore, Ledger
from runtime.autonomy.admission_send_fence import (
    AdmissionNotCurrent,
    AdmissionSendFence,
)
from runtime.integrations import SessionSpec, TrustedTransportFailure
from runtime.scheduler import GlobalBudget

from ops import autonomous_run


class _SyntheticAuthority:
    def verify_policy(self, payload: Mapping[str, object]) -> bool:
        return False

    def verify_admission(self, payload: Mapping[str, object]) -> bool:
        return False

    def authorize_frame(
        self,
        admission: Mapping[str, object],
        policy: Mapping[str, object],
        *,
        frame_digest: str,
        route_digest: str,
    ) -> bool:
        return False


class _DenyBeforeSendFence(AdmissionSendFence):
    def __init__(self) -> None:
        super().__init__(Ledger(InMemoryLedgerStore()), authority=_SyntheticAuthority())
        self.preflight_calls: list[tuple[str, int]] = []

    def preflight(self, admission_ref: str, expected_epoch: int) -> None:
        self.preflight_calls.append((admission_ref, expected_epoch))
        raise AdmissionNotCurrent("synthetic stale admission fixture")


def test_missing_admission_binding_leaves_codex_transport_unavailable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def forbidden_identity_read(*_args: object, **_kwargs: object) -> bytes | None:
        pytest.fail("missing admission binding must be rejected before identity reads")

    monkeypatch.setattr(autonomous_run, "_read_hex_identity", forbidden_identity_read)

    transport = autonomous_run._load_codex_transport(tmp_path)

    assert transport is None


def test_explicit_admission_binding_reaches_transport_and_denies_before_queue_write(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    identity_dir = tmp_path / "supervisor"
    queue_root = identity_dir / "queue"
    workspace_root = tmp_path / "approved-workspaces"
    workspace = workspace_root / "synthetic-mission"
    workspace.mkdir(parents=True)
    request_key_path = identity_dir / "request.key"
    response_key_path = identity_dir / "response.verify"
    fence = _DenyBeforeSendFence()
    identity_reads: list[tuple[Path, bool]] = []

    def synthetic_identity(path: Path, *, private: bool) -> bytes:
        identity_reads.append((path, private))
        return b"\x01" * 32 if private else b"\x02" * 32

    monkeypatch.setattr(autonomous_run, "DEFAULT_CODEX_REQUEST_KEY", request_key_path)
    monkeypatch.setattr(autonomous_run, "DEFAULT_CODEX_RESPONSE_VERIFY_KEY", response_key_path)
    monkeypatch.setattr(autonomous_run, "_read_hex_identity", synthetic_identity)

    transport = autonomous_run._load_codex_transport(
        workspace_root,
        admission_send_fence=fence,
        admission_ref="synthetic-admission-17",
        expected_admission_epoch=17,
    )

    assert transport is not None
    assert identity_reads == [(request_key_path, True), (response_key_path, False)]
    with pytest.raises(TrustedTransportFailure) as raised:
        transport.run(
            SessionSpec(
                workspace=workspace,
                prompt="synthetic prompt",
                allowed_tools=(),
                read_scopes=(),
                timeout_s=1,
                task_id="synthetic-task",
                goal_id="synthetic-goal",
                run_id="synthetic-run",
                stage="BUILD",
            )
        )

    assert raised.value.code == "disclosure_authority_unavailable"
    assert fence.preflight_calls == [("synthetic-admission-17", 17)]
    assert transport.last_request_sha256 is None
    assert not queue_root.exists()


def test_scheduler_composes_only_the_explicit_codex_admission_binding(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    class CompositionReached(Exception):
        pass

    fence = _DenyBeforeSendFence()
    captured: dict[str, object] = {}

    class SyntheticMcpTransport:
        def __init__(self, _state_dir: Path) -> None:
            pass

        def mcp_config(self, *_args: object, **_kwargs: object) -> dict[str, object]:
            return {}

    def capture_codex_transport(_workspace_root: Path, **kwargs: object) -> None:
        captured.update(kwargs)
        raise CompositionReached

    monkeypatch.setattr(autonomous_run, "load_or_create_signing_key", lambda _path: object())
    monkeypatch.setattr(
        autonomous_run,
        "load_authoritative_manifest",
        lambda _path: SimpleNamespace(manifest_sha256="a" * 64),
    )
    monkeypatch.setattr(autonomous_run, "McpWorkerTransport", SyntheticMcpTransport)
    monkeypatch.setattr(autonomous_run, "DEFAULT_CODEX_WORKSPACE_ROOT", tmp_path / "workspaces")
    monkeypatch.setattr(autonomous_run, "_load_codex_transport", capture_codex_transport)

    with pytest.raises(CompositionReached):
        autonomous_run.build_scheduler(
            tmp_path / "state",
            tmp_path / "repository",
            global_budget=GlobalBudget(tokens=1, wallclock_s=1, runs=1),
            runtime_type="codex",
            codex_admission_send_fence=fence,
            codex_admission_ref="synthetic-admission-17",
            codex_expected_admission_epoch=17,
        )

    assert captured == {
        "admission_send_fence": fence,
        "admission_ref": "synthetic-admission-17",
        "expected_admission_epoch": 17,
    }
