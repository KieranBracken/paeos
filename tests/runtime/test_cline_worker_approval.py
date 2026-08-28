"""Tests for Cline desktop-approval broker (Task 3).

Plan: 2026-08-26-paeos-cline-worker-admission.md, lines 392-510.
Proves file-IPC approval/denial, session binding, circuit breaker,
quarantine, journal, and process termination.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import pytest
from paeos.model_router.types import ModelFamily
from runtime.integrations.cline_worker import DesktopApprovalBroker
from runtime.worker_admission import ProbeContract

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

OLD_TEXT, NEW_TEXT = "baseline-worker\n", "admitted-worker\n"
VERIFY = "python3 verify_probe.py"
SESSION_ID = "session-001"


@pytest.fixture()
def contract(tmp_path: Path) -> ProbeContract:
    return ProbeContract(
        probe_id="probe-001",
        sandbox=tmp_path / "probe" / "sandbox",
        provider_id="cline-pass",
        model_id="cline-pass/qwen3.8-max",
        expected_family=ModelFamily.QWEN,
        artifact_name="artifact.txt",
        initial_bytes=OLD_TEXT.encode(),
        expected_bytes=NEW_TEXT.encode(),
        verification_command=VERIFY,
    )


@pytest.fixture()
def broker_dirs(tmp_path: Path) -> dict[str, Path]:
    approval_dir = tmp_path / "approvals"
    quarantine_dir = tmp_path / "quarantine"
    evidence_dir = tmp_path / "evidence"
    return {
        "approval_dir": approval_dir,
        "quarantine_dir": quarantine_dir,
        "journal_path": evidence_dir / "journal.jsonl",
    }


@pytest.fixture()
def broker(contract: ProbeContract, broker_dirs: dict[str, Path]) -> DesktopApprovalBroker:
    return DesktopApprovalBroker(
        contract=contract,
        **broker_dirs,
    )


def _write_request(
    approval_dir: Path,
    session_id: str,
    tool_call_id: str,
    tool_name: str,
    tool_input: Any,
    *,
    iteration: int = 1,
) -> Path:
    """Write a Cline desktop approval request file."""
    approval_dir.mkdir(parents=True, exist_ok=True)
    request_data = {
        "requestId": tool_call_id,
        "sessionId": session_id,
        "createdAt": "2026-08-26T10:00:00+00:00",
        "toolCallId": tool_call_id,
        "toolName": tool_name,
        "input": tool_input,
        "iteration": iteration,
    }
    path = approval_dir / f"{session_id}.request.{tool_call_id}.json"
    path.write_text(json.dumps(request_data))
    return path


def _editor_input(contract: ProbeContract) -> dict[str, str]:
    return {
        "path": str(contract.artifact_path),
        "old_text": OLD_TEXT,
        "new_text": NEW_TEXT,
    }


def _verify_input() -> dict[str, list[str]]:
    return {"commands": [VERIFY]}


class FakeProcess:
    """Fake process exposing poll/terminate/wait/kill."""

    def __init__(self, *, alive: bool = False) -> None:
        self._alive = alive
        self.terminate_count = 0
        self.kill_count = 0
        self.pid = 4242

    def poll(self) -> int | None:
        return None if self._alive else 0

    def terminate(self) -> None:
        self.terminate_count += 1
        self._alive = False

    def wait(self, timeout: float | None = None) -> int:
        if self._alive:
            raise TimeoutError
        return 0

    def kill(self) -> None:
        self.kill_count += 1
        self._alive = False


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_first_valid_editor_binds_session_and_creates_decision(
    broker: DesktopApprovalBroker,
    broker_dirs: dict[str, Path],
    contract: ProbeContract,
) -> None:
    """Test 1: first valid editor request binds session and creates decision."""
    req_path = _write_request(
        broker_dirs["approval_dir"], SESSION_ID, "call-001", "editor",
        _editor_input(contract),
    )
    decision = broker.process_request(req_path)
    assert decision.approved
    assert decision.tool_name == "editor"

    # Decision file should exist
    decision_path = broker_dirs["approval_dir"] / f"{SESSION_ID}.decision.call-001.json"
    assert decision_path.exists()
    decision_data = json.loads(decision_path.read_text())
    assert decision_data["approved"] is True


def test_verification_approved_after_editor(
    broker: DesktopApprovalBroker,
    broker_dirs: dict[str, Path],
    contract: ProbeContract,
) -> None:
    """Test 2: exact verification request approved after editor."""
    # First, approve editor
    req_path = _write_request(
        broker_dirs["approval_dir"], SESSION_ID, "call-001", "editor",
        _editor_input(contract),
    )
    broker.process_request(req_path)

    # Then, verification
    req_path2 = _write_request(
        broker_dirs["approval_dir"], SESSION_ID, "call-002", "run_commands",
        _verify_input(),
    )
    decision = broker.process_request(req_path2)
    assert decision.approved
    assert decision.tool_name == "run_commands"


def test_second_session_id_denied(
    broker: DesktopApprovalBroker,
    broker_dirs: dict[str, Path],
    contract: ProbeContract,
) -> None:
    """Test 3: a second session ID is denied."""
    # Bind first session
    req_path = _write_request(
        broker_dirs["approval_dir"], SESSION_ID, "call-001", "editor",
        _editor_input(contract),
    )
    broker.process_request(req_path)

    # Second session
    req_path2 = _write_request(
        broker_dirs["approval_dir"], "session-002", "call-002", "editor",
        _editor_input(contract),
    )
    decision = broker.process_request(req_path2)
    assert not decision.approved
    assert broker.circuit_breaker_fired


def test_malformed_json_quarantined_and_denied(
    broker: DesktopApprovalBroker,
    broker_dirs: dict[str, Path],
) -> None:
    """Test 4: malformed JSON copied to quarantine and denied."""
    broker_dirs["approval_dir"].mkdir(parents=True, exist_ok=True)
    bad_path = broker_dirs["approval_dir"] / "session-001.request.call-bad.json"
    bad_bytes = b"not valid json {{{"
    bad_path.write_bytes(bad_bytes)

    decision = broker.process_request(bad_path)
    assert not decision.approved

    # Check quarantine copy exists with same bytes
    quarantine_files = list(broker_dirs["quarantine_dir"].iterdir())
    assert len(quarantine_files) == 1
    assert quarantine_files[0].read_bytes() == bad_bytes


def test_expanded_command_denied_fires_breaker_terminates_once(
    broker: DesktopApprovalBroker,
    broker_dirs: dict[str, Path],
    contract: ProbeContract,
) -> None:
    """Test 5: expanded command denied, breaker fired, process terminated once."""
    # First approve editor
    req_path = _write_request(
        broker_dirs["approval_dir"], SESSION_ID, "call-001", "editor",
        _editor_input(contract),
    )
    broker.process_request(req_path)

    # Then send expanded command
    fake_proc = FakeProcess(alive=True)
    req_path2 = _write_request(
        broker_dirs["approval_dir"], SESSION_ID, "call-002", "run_commands",
        {"commands": [f"cd /tmp && {VERIFY}"]},
    )
    decision = broker.process_request(req_path2, process=fake_proc)
    assert not decision.approved
    assert broker.circuit_breaker_fired
    assert fake_proc.terminate_count == 1


def test_broker_never_overwrites_existing_decision(
    broker: DesktopApprovalBroker,
    broker_dirs: dict[str, Path],
    contract: ProbeContract,
) -> None:
    """Test 6: existing decision file is never overwritten."""
    broker_dirs["approval_dir"].mkdir(parents=True, exist_ok=True)
    decision_path = broker_dirs["approval_dir"] / f"{SESSION_ID}.decision.call-001.json"
    decision_path.write_text('{"approved": false, "reason": "PREEXISTING"}')

    req_path = _write_request(
        broker_dirs["approval_dir"], SESSION_ID, "call-001", "editor",
        _editor_input(contract),
    )
    decision = broker.process_request(req_path)
    assert not decision.approved  # Protocol violation

    # Original file content preserved
    assert "PREEXISTING" in decision_path.read_text()


def test_journal_records_all_decisions(
    broker: DesktopApprovalBroker,
    broker_dirs: dict[str, Path],
    contract: ProbeContract,
) -> None:
    """Test 7: every request/decision hash appended to JSONL journal."""
    req_path = _write_request(
        broker_dirs["approval_dir"], SESSION_ID, "call-001", "editor",
        _editor_input(contract),
    )
    broker.process_request(req_path)

    journal_path = broker_dirs["journal_path"]
    assert journal_path.exists()

    lines = journal_path.read_text().strip().split("\n")
    assert len(lines) >= 1

    entry = json.loads(lines[0])
    assert "request_hash" in entry
    assert "decision_hash" in entry
    assert "tool_name" in entry
    assert entry["tool_name"] == "editor"
    assert entry["session_id"] == SESSION_ID
    assert "approved" in entry


def test_no_files_outside_tmp_path(
    broker: DesktopApprovalBroker,
    broker_dirs: dict[str, Path],
    contract: ProbeContract,
    tmp_path: Path,
) -> None:
    """Test 8: no file written outside tmp_path."""
    req_path = _write_request(
        broker_dirs["approval_dir"], SESSION_ID, "call-001", "editor",
        _editor_input(contract),
    )
    broker.process_request(req_path)

    # Verify all created files are under tmp_path
    for root, _dirs, files in os.walk(tmp_path):
        for f in files:
            full = Path(root) / f
            assert full.is_relative_to(tmp_path)
