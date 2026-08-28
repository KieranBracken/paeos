"""Cline desktop-approval broker for worker admission probes.

Implements file-IPC approval/denial for Cline 3.0.56's desktop tool-approval
protocol. The broker binds to one session, delegates policy to the pure
evaluate_tool_request function, and never duplicates admission logic.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any, Protocol

from runtime.worker_admission import (
    ProbeContract,
    ToolDecisionRecord,
    evaluate_tool_request,
)

_IDENTIFIER_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}\Z")


def _valid_identifier(value: object) -> bool:
    """Return whether an untrusted IPC identifier is one safe path component."""
    return isinstance(value, str) and _IDENTIFIER_RE.fullmatch(value) is not None


class ProcessHandle(Protocol):
    """Minimal process interface for the broker — no subprocess import needed."""

    pid: int

    def poll(self) -> int | None: ...
    def terminate(self) -> None: ...
    def wait(self, timeout: float | None = None) -> int: ...
    def kill(self) -> None: ...


class DesktopApprovalBroker:
    """Cline desktop tool-approval broker.

    Reads request files from the approval directory, evaluates them against
    the probe contract, and writes decision files. Every decision is
    journaled. The broker never executes tools itself.
    """

    def __init__(
        self,
        *,
        contract: ProbeContract,
        approval_dir: Path,
        quarantine_dir: Path,
        journal_path: Path,
        poll_seconds: float = 0.05,
        max_wait_seconds: float = 300.0,
    ) -> None:
        self._contract = contract
        self._approval_dir = approval_dir
        self._quarantine_dir = quarantine_dir
        self._journal_path = journal_path
        self._poll_seconds = poll_seconds
        self._max_wait_seconds = max_wait_seconds
        self._bound_session_id: str | None = None
        self._prior_decisions: list[ToolDecisionRecord] = []
        self.circuit_breaker_fired: bool = False

    def process_request(
        self,
        path: Path,
        process: ProcessHandle | None = None,
    ) -> ToolDecisionRecord:
        """Process a single Cline tool-approval request file.

        Returns a ToolDecisionRecord. On denial, writes the denial decision,
        fires circuit breaker if needed, and terminates the process.
        """
        raw_bytes = path.read_bytes()
        request_hash = hashlib.sha256(raw_bytes).hexdigest()

        # Parse request JSON
        try:
            request_data = json.loads(raw_bytes)
            if not isinstance(request_data, dict):
                raise ValueError("request is not a dict")
        except (json.JSONDecodeError, ValueError):
            # Malformed JSON → quarantine
            self._quarantine(path, raw_bytes)
            decision = ToolDecisionRecord(
                tool_name="<malformed>",
                approved=False,
                reason_code="MALFORMED_JSON",
            )
            self._journal_and_write_decision(
                path, request_data={}, request_hash=request_hash,
                decision=decision, tool_call_id="unknown",
                session_id="unknown",
            )
            self._halt_process(process)
            return decision

        session_id = request_data.get("sessionId", "unknown")
        tool_call_id = request_data.get("toolCallId", "unknown")

        if not _valid_identifier(session_id) or not _valid_identifier(tool_call_id):
            decision = ToolDecisionRecord(
                tool_name=str(request_data.get("toolName", "<unknown>")),
                approved=False,
                reason_code="INVALID_IDENTIFIER",
            )
            safe_tool_call = f"invalid-{request_hash[:16]}"
            self._journal_and_write_decision(
                path,
                request_data,
                request_hash,
                decision,
                safe_tool_call,
                "invalid",
            )
            self._halt_process(process)
            return decision

        assert isinstance(session_id, str)
        assert isinstance(tool_call_id, str)

        # Session binding: first well-formed request locks the session ID
        if self._bound_session_id is None:
            self._bound_session_id = session_id
        elif session_id != self._bound_session_id:
            decision = ToolDecisionRecord(
                tool_name=request_data.get("toolName", "<unknown>"),
                approved=False,
                reason_code="SESSION_MISMATCH",
            )
            self.circuit_breaker_fired = True
            self._journal_and_write_decision(
                path, request_data, request_hash, decision,
                tool_call_id, session_id,
            )
            if process is not None:
                self._terminate_process(process)
            return decision

        # Check for existing decision file (protocol violation)
        decision_path = self._decision_path(session_id, tool_call_id)
        if decision_path.exists():
            decision = ToolDecisionRecord(
                tool_name=request_data.get("toolName", "<unknown>"),
                approved=False,
                reason_code="DECISION_ALREADY_EXISTS",
            )
            # Do NOT overwrite the existing decision file
            self._journal_entry(
                request_hash=request_hash,
                decision=decision,
                decision_hash="<existing>",
                tool_call_id=tool_call_id,
                session_id=session_id,
            )
            self._halt_process(process)
            return decision

        # Delegate to pure policy evaluator
        decision = evaluate_tool_request(
            self._contract,
            request_data,
            tuple(self._prior_decisions),
        )

        # Write decision and journal
        try:
            self._journal_and_write_decision(
                path, request_data, request_hash, decision,
                tool_call_id, session_id,
            )
        except FileExistsError:
            decision = ToolDecisionRecord(
                tool_name=request_data.get("toolName", "<unknown>"),
                approved=False,
                reason_code="DECISION_ALREADY_EXISTS",
            )
            existing_path = self._decision_path(session_id, tool_call_id)
            existing_hash = hashlib.sha256(existing_path.read_bytes()).hexdigest()
            self._journal_entry(
                request_hash=request_hash,
                decision=decision,
                decision_hash=existing_hash,
                tool_call_id=tool_call_id,
                session_id=session_id,
            )
            self._halt_process(process)
            return decision

        # Track decisions for ordering
        self._prior_decisions.append(decision)

        # On denial: fire circuit breaker and terminate
        if not decision.approved:
            self._halt_process(process)

        return decision

    def serve(
        self,
        process: ProcessHandle,
    ) -> tuple[ToolDecisionRecord, ...]:
        """Serve approval requests while the process is alive.

        Returns after the process exits and all discovered requests
        have terminal journal entries.
        """
        decisions: list[ToolDecisionRecord] = []
        seen_requests: set[str] = set()
        deadline = time.monotonic() + self._max_wait_seconds

        while process.poll() is None and not self.circuit_breaker_fired:
            if time.monotonic() >= deadline:
                self._halt_process(process)
                break
            self._approval_dir.mkdir(parents=True, exist_ok=True)
            for req_file in sorted(self._approval_dir.glob("*.request.*.json")):
                if str(req_file) not in seen_requests:
                    seen_requests.add(str(req_file))
                    decision = self.process_request(req_file, process=process)
                    decisions.append(decision)
            time.sleep(self._poll_seconds)

        # Final sweep after process exits
        if self._approval_dir.exists():
            for req_file in sorted(self._approval_dir.glob("*.request.*.json")):
                if str(req_file) not in seen_requests:
                    seen_requests.add(str(req_file))
                    decision = self.process_request(req_file, process=process)
                    decisions.append(decision)

        return tuple(decisions)

    # -------------------------------------------------------------------
    # Private helpers
    # -------------------------------------------------------------------

    def _decision_path(self, session_id: str, tool_call_id: str) -> Path:
        return self._approval_dir / f"{session_id}.decision.{tool_call_id}.json"

    def _quarantine(self, source: Path, raw_bytes: bytes) -> None:
        """Copy malformed request bytes to quarantine directory."""
        self._quarantine_dir.mkdir(parents=True, mode=0o700, exist_ok=True)
        dest = self._quarantine_dir / source.name
        dest.write_bytes(raw_bytes)
        os.chmod(dest, 0o600)

    def _write_decision_file(
        self,
        session_id: str,
        tool_call_id: str,
        decision: ToolDecisionRecord,
    ) -> str:
        """Write decision file atomically. Returns hash of written bytes."""
        self._approval_dir.mkdir(parents=True, mode=0o700, exist_ok=True)
        final_path = self._decision_path(session_id, tool_call_id)

        if decision.approved:
            decision_data: dict[str, Any] = {"approved": True}
        else:
            decision_data = {
                "approved": False,
                "reason": f"PAEOS_{decision.reason_code}",
            }

        decision_bytes = json.dumps(decision_data).encode()
        decision_hash = hashlib.sha256(decision_bytes).hexdigest()

        # Atomic no-replace publish: temp file, fsync, hard-link, unlink temp.
        # os.link fails with FileExistsError if another broker won the race.
        fd, tmp_path = tempfile.mkstemp(
            dir=str(self._approval_dir),
            prefix=".decision_",
            suffix=".tmp",
        )
        try:
            os.write(fd, decision_bytes)
            os.fsync(fd)
            os.fchmod(fd, 0o600)
        finally:
            os.close(fd)

        try:
            os.link(tmp_path, final_path)
        finally:
            os.unlink(tmp_path)

        return decision_hash

    def _journal_entry(
        self,
        *,
        request_hash: str,
        decision: ToolDecisionRecord,
        decision_hash: str,
        tool_call_id: str,
        session_id: str,
    ) -> None:
        """Append a single JSONL journal entry."""
        self._journal_path.parent.mkdir(parents=True, mode=0o700, exist_ok=True)
        entry = {
            "timestamp": time.time(),
            "request_hash": request_hash,
            "decision_hash": decision_hash,
            "approved": decision.approved,
            "reason_code": decision.reason_code,
            "tool_name": decision.tool_name,
            "tool_call_id": tool_call_id,
            "session_id": session_id,
        }
        with self._journal_path.open("a") as f:
            f.write(json.dumps(entry) + "\n")
        os.chmod(self._journal_path, 0o600)

    def _journal_and_write_decision(
        self,
        path: Path,
        request_data: dict[str, Any],
        request_hash: str,
        decision: ToolDecisionRecord,
        tool_call_id: str,
        session_id: str,
    ) -> None:
        """Write decision file and journal entry together."""
        decision_hash = self._write_decision_file(
            session_id, tool_call_id, decision,
        )
        self._journal_entry(
            request_hash=request_hash,
            decision=decision,
            decision_hash=decision_hash,
            tool_call_id=tool_call_id,
            session_id=session_id,
        )

    def _terminate_process(self, process: ProcessHandle) -> None:
        """Terminate the exact child process. Kill if terminate doesn't work."""
        process.terminate()
        try:
            process.wait(timeout=2.0)
        except (subprocess.TimeoutExpired, TimeoutError, OSError):
            process.kill()

    def _halt_process(self, process: ProcessHandle | None) -> None:
        """Trip the broker breaker and terminate only the bound child, if present."""
        self.circuit_breaker_fired = True
        if process is not None:
            self._terminate_process(process)
