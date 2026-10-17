# Terminated DEBT-0249 successor: coordination timeout

Verified 2026-10-15T17:05:58.905531+00:00. Run `r-29471672`, goal `g-28779efed40e`; original run root `/private/tmp/paeos-debt0249-run-82a4185550e948b4a677d68202977a11` and peer state root are preserved unchanged. No late worker completion was submitted.

## Actual result

Runtime Sealed: 0 | Remanded: 1 | Remediated: 0. Court Sealed: 0 | Remanded: 0 | Remediated: 0. Builder and Court were not reached. The runtime subprocess exited 2 with `IDEATE worker failed: FAILED`. Its recorded PID is no longer present.

The read-only SQLite connection used `mode=ro&immutable=1`; no WAL or SHM was present. `PRAGMA integrity_check` returned `ok`. All nine dense rows independently recomputed using the preserved ledger algorithm, including PRODUCTION domain, and all predecessor links matched. Head `f225e078befbca95f22294c8905a4e2da311577df17f18b105de73d9cd07a730` agrees with the subprocess stdout. Source imports and provider calls were unnecessary.

| Stage | Task | Ledger result | UTC timestamp |
|---|---|---|---|
| L03 RE_DERIVE | t-26ab63ea8e74 | COMPLETE, seq 4 | 16:56:12.255583 |
| L04 IDEATE | t-c77ed9cdb294 | FAILED, seq 5 | 17:01:12.451699 |

Two exact prompt files and one terminal response exist. L04 has no response; both bound workspaces are absent. Three CAS blobs have matching content-address filenames: L03 artifact, L03 response, and failure-result bytes. The last contains `BRIDGE_RESPONSE_TIMEOUT: no correlated response before timeout for r-29471672--t-c77ed9cdb294--ideate`. The L03 artifact remains `2bcad5d11b9063310e3df292c53088dde8252db2d5d5e3106c9fced7a4844c8a`; its response remains `780d6350bf4ca3197213a7748caa2af9977867b001f711c8ddeb9ccc5d64a8af`.

The runtime recorded the actual `chat-bridge-compatibility` model label and zero adapter tokens. Those fields do not establish physical model identity, total provider usage, or qualification. The initial `L11_WEAKNESS_FINDER_ADVISORY_SCAN` event is not completion of L11. The generic retrospective summary says “court remanded”, but no Court execution occurred; the actual failure is the L04 worker timeout.

## Cause and evidence limits

The assigning parent relayed the worker's exact statement: it spent too long reading an embedded package, including an oversized truncated read and subsequent narrower reads, then delayed writing while composing. The worker reported no artifact, response, draft, implementation, tests, or provider calls, and all tool calls completed with none pending. Full wording is preserved in `WORKER_COORDINATION_STATEMENT.json` and explicitly identified as coordination testimony.

The parent separately reported interruption at 17:00:41 UTC and a takeover attempt after the deadline that asserted the workspace was absent before any write. Current physical checks independently confirm absent workspaces and absent L04 response. They cannot reconstruct every action in a deleted workspace or independently prove the historical absence of pending tools. The timing and recorded failure support the coordination timeout; no substantive IDEATE result exists to assess.

## Separate preflight failure

PREFLIGHT1 exited 1 at launcher import: nonexistent `assert_lifecycle_contract_is_current` could not import from `runtime.ceremony`. The preserved launcher places that import before importing or invoking `ops.autonomous_run.main`. Its contemporaneous analysis records no state/ledger creation. The corrected actual launcher uses `assert_canonical_lifecycle_bound`. PREFLIGHT1 is not a second runtime remand or Court outcome. Its generic receipt status string is preserved without treating it as runtime-entry proof.

## Preservation and boundaries

`run/` contains the exact nonsecret receipts, intents, subprocess logs, launchers, intake, source manifest and generated friction note. `state/` contains the copied ledger, exact bridge exchange files, CAS and evaluation artifact. `LEDGER_READBACK.json`, `VERIFICATION.json` and `SOURCE_VERIFICATION.json` provide the independent readback. All 903 manifest-listed source files match their recorded hashes. Original archived files were rehashed unchanged after copying.

No signing key was read, hashed or copied. `seal.key`, MCP configuration and scars database were excluded; the latter two are unnecessary for the requested proof. No source, provider, runtime state, old bridge response, production policy, qualification, frozen candidate, or active successor was changed. This archive preserves failure evidence and provides no authority to replay the old stage or bypass later gates.
