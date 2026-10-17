# Builder transport bootstrap recovery checkpoint

Date: 2026-10-17
Branch: `codex/builder-qualification-bootstrap-20261017`
Base recovery commit: `2dc2544ee2f46d2a240c4bff16ee1950a476e92e`

## Scope

This checkpoint implements the user-authorized one-time repair for the expired Trusted Codex Builder qualification path. It supports a fresh shared UUID across qualification task, goal, and run identity; a supervisor-persisted one-use identity claim; a single provider request after an idle-queue and signed-supervisor restart check; and preserved private workspace, attempt state, signed request, and signed response evidence. If the response is ambiguous, the attempt remains `UNKNOWN` and has no retry path. Historical active lifecycle records permit restart only when their exact process receipt is valid and the recorded PID is absent; malformed, missing, live, or uncheckable process evidence blocks restart.

The supervisor qualification writer requires the one-use identity claim, every required canary to pass, the exact lifecycle, and exactly one broker request. No private key is created and no token is minted by the wrapper.

## Verification

The focused verification receipt records 43 passing tests across the trusted transport, Builder readiness, and trusted-client suites. Ruff lint and formatting checks passed for all 13 source/test files in this package. Bytecode compilation passed. The scan found zero matches for private-key PEMs, common GitHub/OpenAI/Anthropic/Google credentials, or AWS access keys across the 17 staged payload files. Exact commands, outputs, and per-file hashes are in `focused-verification.json` and `secret-scan.json`; `MANIFEST.json` binds this report, receipts, source files, and required notebook entries.

`tests/runtime/test_builder_transport_gate.py` is intentionally excluded from this checkpoint: in the sanitized recovery tree its collection fails because `runtime.autonomy.authority` is not present. That failure is unrelated to the bootstrap path and is not represented as a passing test.

## Current disposition

This is a source recovery checkpoint, not a release, qualification, Court adjudication, or P3 readiness claim. The candidate has not been installed on the host. No provider request or new PAEOS task admission/receiver start has occurred; the current signed Builder qualification remains expired. Independent review choice is pending. After review, host installation is gated on a fresh check that the signed request queue is empty and no worker process is active. The authorized live qualification is exactly one gpt-5.6-sol request; an ambiguous result must remain preserved and must not be retried.

ALLOWED_NOW: Publish this captured, tested candidate as a recovery checkpoint. Owner: bootstrap integrator in this task.

HELD: Host install, one-time physical Builder qualification, and fresh Chat 1 D0258 task admission. Wake after the selected independent review completes and immediate host queue/process preflight passes.

AUTHORITY_OR_IMPLEMENTATION_GAP: The safe bootstrap implementation exists in this candidate branch, but the host still uses the previous bundle and has an expired signed qualification. Chat 1 remains the sole D0258 integrator; no new PAEOS admission or receiver-start evidence exists. Court observation, Court adjudication, and qualification remain separate.
