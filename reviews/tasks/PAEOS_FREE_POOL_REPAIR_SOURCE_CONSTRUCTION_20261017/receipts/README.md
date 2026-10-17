# Sanitized PAEOS task receipt export

This allowlist export records the free-pool source-construction attempt and its single provider-free physical Court observation. It deliberately distinguishes local Bridge spool completion from an independently started worker.

`initialization.json` recorded `worker_dispatches: 0`. `dispatch_started.json` proves that the local PAEOS package dispatch was entered and a request was written. It is not a receiver-start receipt. The builder session was bound to the current Codex thread, which authored the workspace candidate and invoked the completion adapter. The adapter wrote the Bridge spool response; `result.status=COMPLETE` means that response was accepted by ChatBridge, not that a separate worker thread started. No external provider was called.

The Court record is one physical test observation (`exit_code=0`); it is not adjudication, independent review, integration, or qualification. `tokens: 0` is the compatibility transport's meter, not account quota telemetry.

The original capability-bearing package, `kernel.key`, SQLite/WAL files, CAS, runtime state, and all other state files are excluded. The sanitized package receipt includes the original package SHA-256 but omits the capability value. The original prompt content is not exported; its path, size, and SHA-256 are recorded.
