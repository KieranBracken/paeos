# B00 confinement continuation — blocked on supported CLI mediation

**Disposition:** candidate-side offline work is frozen in the existing B00 worktree. The pinned Codex CLI 0.147.0 still omits the mediated `tools` inventory from its Responses request. The supervisor now fails closed before the legacy process launch for that pinned executable. This does not unblock Builder production execution.

The durable detailed verification record is [CHAT4_B00_CONFINEMENT_EVIDENCE_20261021.txt](/Users/bob/PAEOS-Workspaces/codex-supervision/event-deliveries/CHAT4_B00_CONFINEMENT_EVIDENCE_20261021.txt), SHA-256 `8b7fb5cdb65da8dd5089978c4d4a9c7a9870bb017c4d37d6ff05b2fbbaad5366`. The exact candidate patch is [CHAT4_B00_CONFINEMENT_CONTINUATION_20261021.patch](/Users/bob/PAEOS-Workspaces/codex-supervision/event-deliveries/CHAT4_B00_CONFINEMENT_CONTINUATION_20261021.patch), SHA-256 `9e4a257aee968574c91eefd3214b05ad29dc7cf040b01d55062f03bb57f22451`.

The candidate is the preserved worktree `/Users/bob/.codex/worktrees/b00-confinement-v1/paeos`, based on `aefdf625e1a44ba33bc2a611a8e1c894a5f88b1e`, locally checkpointed as detached commit `50a54a59b9e0d27190e9355af5af6fa552de897e`. Its tree is clean. The commit changes only these owner-card paths:

- `ops/trusted_codex_worker_supervisor.py`
- `runtime/integrations/mediated_worker_tools.py`
- `runtime/integrations/process_supervisor.py`
- `runtime/integrations/worker_confinement.py`
- `tests/runtime/test_confined_codex_cli.py`
- `tests/runtime/test_mediated_worker_tools.py`
- `tests/runtime/test_worker_confinement_mutations.py`

The new regression proves `_run_request` refuses the exact pinned Codex executable before canaries, `_codex_argv`, and `run_bounded_process`. The actual CLI probe is still intentionally failing: its version preflight ran under Seatbelt and confirmed 0.147.0; the actual invocation ran under Seatbelt with only a local fake-provider loopback endpoint allowed and returned one request with `tools=None`. The latest local regression suite passed **78 tests, 1 deselected**; Ruff format/lint, compilation of all seven files, committed diff checks, and the scoped secret scan passed. No provider, host-service, key, Chat 1, Court, A-08, PF03, qualification, or production activation action occurred.

**Next eligible task for root/Chat 1:** keep Builder execution fail-closed while finding an existing supported pinned client/transport that exposes exactly the parent-mediated read/patch/test tools. Prove it with a local fake provider that sends actual `function_call` responses, captures each permitted invocation and forbidden calls, and runs under Seatbelt with external egress denied. If Codex 0.147.0 remains unsupported, do not enable its under-development feature or route around the client boundary. After a supported path is evidenced, root can separately review and compose the positive source path. The protected non-same-UID custody service remains unprovisioned and separately gated; this package contains no reviewed administrator install artifact, so it provides no admin command. Chat 1's candidate was not modified directly.

The prior Luna review's launch-path defect is addressed with a default refusal for the configured pinned executable. No independent review of this continuation was run under the allocation; production wiring still requires root's independent review and service evidence. The candidate remains source-only and is not a Court/A-08 result. No remote was pushed: the checkpoint is detached and no authorized remote branch was specified for readback.
