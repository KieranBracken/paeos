"""Provider-neutral, fail-closed supervisor adapter contracts."""

from runtime.supervisors.admission import (
    MAX_PROFILE_TTL_SECONDS,
    SupervisorAdmissionDecision,
    SupervisorAdmissionProfile,
    decide_supervisor_admission,
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

__all__ = [
    "MAX_PROFILE_TTL_SECONDS",
    "AdapterResult",
    "SupervisorAdapter",
    "SupervisorAdmissionDecision",
    "SupervisorAdmissionProfile",
    "SupervisorRequest",
    "SupervisorResponse",
    "SupervisorTier",
    "TransportObservation",
    "decide_supervisor_admission",
    "decode_request",
    "decode_response",
    "encode_request",
    "encode_response",
    "validate_response",
]
