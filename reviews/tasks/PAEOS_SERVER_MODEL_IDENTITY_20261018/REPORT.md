# Provider-reported model identity

Base: `8bc28d6feded86672d96816f845e178f99538a74`. Scope is the broker, supervisor and3test files listed in SCOPE.json; existing disclosure denials remain.

The broker retains selected HTTP `openai-model` metadata and parses bounded SSE `response.headers` declarations using the pinned Codex0.147.0 source contract. It never treats `response.model`, tool output, top-level WebSocket metadata or the configured request label as observed identity. Missing/conflicting/malformed declarations, incomplete/error streams and non2xx statuses cannot qualify. Repeated matching declarations are accepted.

Receipt schema advances to /3. Each immutable request/response pair carries observed_model_id, model_identity_contract and model_identity_error; reverse-order concurrent completions remain correctly paired. HTTP transport outcome remains distinct from identity verification. Supervisor completion now requires a matching verified identity and2xx status on every receipt; its signed observation takes model_id from that validated aggregate. Unsupported responses retain truthful transport evidence without claiming identity.

Baseline47failed/91passed; final138passed in23.22s. Tests use synthetic responses and loopback only; external network and host-home data are excluded by the runner. Seven-file lint/format/compilation and source diff checks pass. The final integrated full suite in the adjacent policy package exits2 with7collection errors: four missing contracts.adapters modules and three runtime.transport imports. No full-suite acceptance is claimed.

The upstream contract is now source-bound. This is provider-reported identity received over the configured TLS route, not cryptographic backend-weight attestation, a reproducible binary build or an observed live provider run. Installed package metadata matched0.147.0 during research; the unsigned source tag does not prove binary provenance. Activation must revalidate its exact executable/bundle dependency. No provider call, host key operation, install, qualification, PAEOS admission, Court action, debt integration or formal review occurred.

ALLOWED_NOW: capture/push this tested candidate; review remaining disclosure integration within budget.
HELD: positive egress, installation, final aggregate Security Review, stage qualification, Chat1 admission and dependent debts/P3.
AUTHORITY_OR_IMPLEMENTATION_GAP: model parsing and receipt enforcement are implemented; physical identity qualification is not. Operational signing/disclosure enrollment/currentness/frame/closure/attempt enforcement remains. Chat1 retains exclusive D0258 integration.
