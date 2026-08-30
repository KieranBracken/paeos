"""Provider-neutral, fail-closed supervisor adapter contracts."""

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
    "AdapterResult",
    "SupervisorAdapter",
    "SupervisorRequest",
    "SupervisorResponse",
    "SupervisorTier",
    "TransportObservation",
    "decode_request",
    "decode_response",
    "encode_request",
    "encode_response",
    "validate_response",
]
