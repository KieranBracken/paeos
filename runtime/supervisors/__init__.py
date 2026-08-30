"""Provider-neutral, fail-closed supervisor adapter contracts."""

from runtime.supervisors.admission import (
    MAX_PROFILE_TTL_SECONDS,
    SupervisorAdmissionDecision,
    SupervisorAdmissionProfile,
    decide_supervisor_admission,
)
from runtime.supervisors.antigravity import AntigravitySupervisorAdapter
from runtime.supervisors.checkpoint import (
    SCHEMA_VERSION as CHECKPOINT_SCHEMA_VERSION,
)
from runtime.supervisors.checkpoint import (
    SupervisorCheckpoint,
    SupervisorCoordinator,
    SupervisorRotationError,
    repository_digest,
    verify_checkpoint,
)
from runtime.supervisors.codex import CodexSupervisorAdapter
from runtime.supervisors.headless import (
    HeadlessInvocation,
    HeadlessResult,
    HeadlessRunner,
    HeadlessSupervisorAdapter,
    SupervisorAdapterError,
)
from runtime.supervisors.protocol import (
    AdapterResult,
    SupervisorAdapter,
    SupervisorRequest,
    SupervisorResponse,
    SupervisorTier,
    TransportObservation,
    decode_request,
    decode_response,
    encode_request,
    encode_response,
    validate_response,
)
from runtime.supervisors.registry import SupervisorAdapterDescriptor, SupervisorAdapterRegistry

__all__ = [
    "CHECKPOINT_SCHEMA_VERSION",
    "MAX_PROFILE_TTL_SECONDS",
    "AdapterResult",
    "AntigravitySupervisorAdapter",
    "CodexSupervisorAdapter",
    "HeadlessInvocation",
    "HeadlessResult",
    "HeadlessRunner",
    "HeadlessSupervisorAdapter",
    "SupervisorAdapter",
    "SupervisorAdapterDescriptor",
    "SupervisorAdapterError",
    "SupervisorAdapterRegistry",
    "SupervisorAdmissionDecision",
    "SupervisorAdmissionProfile",
    "SupervisorCheckpoint",
    "SupervisorCoordinator",
    "SupervisorRequest",
    "SupervisorResponse",
    "SupervisorRotationError",
    "SupervisorTier",
    "TransportObservation",
    "decide_supervisor_admission",
    "decode_request",
    "decode_response",
    "encode_request",
    "encode_response",
    "repository_digest",
    "validate_response",
    "verify_checkpoint",
]
