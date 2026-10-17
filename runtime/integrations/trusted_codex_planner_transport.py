"""Fixed, task-scoped Codex transport for the qualified GPT-5.6 Luna planner route."""

from __future__ import annotations

import time

from runtime.integrations import SessionSpec
from runtime.integrations.trusted_codex_transport import (
    HostCodexWorkerTransport,
    TrustedCodexTransportError,
)
from runtime.planner_transport import PLANNER_STAGES

__all__ = ["PLANNER_CAPABILITY_SCHEMA", "HostCodexPlannerTransport"]

PLANNER_CAPABILITY_SCHEMA = "paeos.trusted-codex-planner-launch/1"
PLANNER_MODEL_ID = "gpt-5.6-luna"
CAPABILITY_TTL_SECONDS = 90.0


class HostCodexPlannerTransport(HostCodexWorkerTransport):
    """A Luna-only planner client; it cannot submit an IMPLEMENT capability."""

    model_id = PLANNER_MODEL_ID

    def _request_payload(self, spec: SessionSpec) -> dict[str, object]:
        if spec.stage not in PLANNER_STAGES:
            raise TrustedCodexTransportError("planner stage is not eligible for the Luna route")
        if not self._workspace_is_approved(spec.workspace):
            raise TrustedCodexTransportError("session workspace is outside the fixed supervisor root")
        if not all(
            isinstance(value, str) and value
            for value in (spec.task_id, spec.goal_id, spec.run_id, spec.stage)
        ):
            raise TrustedCodexTransportError("session identity is incomplete")
        if "\x00" in spec.prompt or not spec.prompt.strip():
            raise TrustedCodexTransportError("session prompt is malformed")
        if len(spec.prompt.encode("utf-8")) > 64 * 1024:
            raise TrustedCodexTransportError("session prompt exceeds bounded size")
        issued = time.time()
        return {
            "schema": PLANNER_CAPABILITY_SCHEMA,
            "request_id": self._new_request_id(),
            "task_id": spec.task_id,
            "goal_id": spec.goal_id,
            "run_id": spec.run_id,
            "stage": spec.stage,
            "workspace_id": spec.workspace.name,
            "prompt": spec.prompt,
            "issued_at": issued,
            "expires_at": issued + CAPABILITY_TTL_SECONDS,
            "provider_id": self.provider_id,
            "model_id": self.model_id,
            "family": self.model_family,
            "fallback_used": False,
            "manual_chat_bridge": False,
        }

    @staticmethod
    def _new_request_id() -> str:
        import uuid

        return uuid.uuid4().hex
