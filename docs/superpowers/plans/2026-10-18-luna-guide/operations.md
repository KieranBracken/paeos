# Luna operating runbook

## Resume without another planning round

On the first Luna turn, confirm the actual selected chat model from available app state; do not infer it from the prompt. Read the main guide, latest notebook and the first eligible card. The human permits using Luna for progress within the remaining allocation; account telemetry and existing task/root ceilings still apply. The Astra exception is for preparing this guide, not indefinite strong-model execution.

Read-only starting commands in the candidate:

```sh
/usr/bin/git -C /Users/bob/.codex/worktrees/p1-bound-source-recovery/paeos status --short --branch
/usr/bin/git -C /Users/bob/.codex/worktrees/p1-bound-source-recovery/paeos rev-parse HEAD
```

Compare HEAD with the saved plan commit and its implementation parent `2ec6ca1a6e8ecb3eff611781e0c59905dbd0c19b`. Later legitimate commits are not automatically an error: reconcile their explicit manifest/disposition, then freeze the new task base. Never reset to this guide's baseline over another owner's work.

First action is B00's scope and admission-fence determination, followed by synthetic B01. Do not rerun180/138 historical tests merely to repeat the last turn, generate a Founder key, call a provider, install the supervisor or wake debt workers as a “preflight.” Execute tests once they discriminate the new change or unresolved concern.

## Concrete task packet

The existing PAEOS task/contract format remains authoritative. Project these fields into it; this list is a completeness checklist, not a competing schema:

| Field | Required value |
|---|---|
| Purpose | One card/subcard and one exact completion claim |
| Source | Repository, commit/tree, selected dirty-file provenance if any, full mutable preimages and dependency hashes |
| Owner | Single integrator, Builder identity, independent reviewer requirement, path lease |
| Authority | Existing human/admission references and permitted effects; reserved boundaries |
| Execution | Real run/task/stage/role/session/workspace, executor/custody identity and logical operation |
| Disclosure | Trusted policy revision, class/provenance, exact route/privacy/free entitlement, closure/tool/frame binding |
| Acceptance | Exact executable/argv/cwd/env/timeout, positive claim, discriminating negative and expected actual outcome |
| Budget | Parent allocation, remaining attempt ceiling, zero blind retry for UNKNOWN, wall/token/cost limits |
| Integration | Candidate capture, applicable review/Court gate, owner, rollback and affected requalification |
| Wake | One observable predicate with owner/source; no “continue when ready” |

Never fill missing identities with random strings to make a schema accept the packet. Fresh IDs identify genuinely new lawful operations; they do not replace reconciliation of abandoned or uncertain effects.

## Verification commands and boundaries

**Python packages:** in the prepared candidate environment, use `uv run pytest` with explicit changed test modules; `uv run ruff check` and `uv run ruff format --check` with exact source/test paths; compile those sources without importing application code; `/usr/bin/git diff --check`. `ops/` is excluded by default Ruff config, so include admitted ops files explicitly/with the tool's exclusion semantics checked. Type-check changed kernel APIs under the existing strict configuration. Preserve command exit/stdout/stderr and interpreter/dependency identity.

**Known safe synthetic harnesses:** `reviews/tasks/PAEOS_PINNED_POLICY_INPUTS_20261018/run_verification.py` and `reviews/tasks/PAEOS_SERVER_MODEL_IDENTITY_20261018/run_verification.py` capture selected tests with fresh scratch/import fences. Their positional label must be new because outputs are create-only. Read their pinned test sets before reuse; adapt under the new task scope when coverage changes. Their diagnostic Python bootstrap is not a depth-one Court verifier and cannot be promoted into Court evidence by relabeling it.

**Full integrated Python suite:** use the existing isolated full-suite runner or a reviewed successor with correctly prepared environment. The last run exited2 at seven collection errors. Report the exact new outcome, duration and bound candidate. Do not hide failures using `--ignore`, `importorskip`, empty stubs, renamed quarantined modules or dirty-main PYTHONPATH. A phase claiming a broken dependency cannot qualify merely because it is called a known failure.

**Orca:** existing backend `pytest.ini` uses `pythonpath=.`; after the P4 fixture repair, run the admitted interpreter with `python -m pytest tests/test_phase4_runtime_ux.py` from its isolated backend root. Add each new module by its explicit admitted path. Existing frontend scripts are `npm run build` and `npm run test:prompt`. No browser script is established yet; P4 creates/pins it and P7 expands it. Use lockfile installs only within admitted network/dependency policy. Inspect startup imports for `.env`, stores and provider activation first.

**Court:** freeze one tracked verifier entry and exact absolute executable, shell-free argv, cwd, environment and candidate binding. Actual kernel-captured observations and independent Court reproduction are required. Deliberate failing command must actually remand at the intended invariant. A wrapper returning0 after printing expected PASS is invalid. Preserve physical observation versus adjudication versus qualification separately.

## Public source recovery

Before each push:

1. Capture the explicit file manifest and SHA-256 for source, tests and sanitized active evidence. Include necessary new dependency files only with their admitted origins. Preserve original findings.
2. Inspect working diff and staged diff. Scan selected content and newly exposed history for keys/tokens/credentials/raw private responses. Scan findings are triaged without printing secret values. Absence of a regex hit does not establish disclosure classification.
3. Use `/usr/bin/git add --` with explicit paths from the manifest. Confirm staged paths match exactly. Commit a message identifying a source/recovery checkpoint, not qualification unless an actual qualification record exists.
4. Inspect ancestry against the remote branch. Push without force. If remote diverged, preserve both and use a new `codex/` recovery branch or a reviewed merge; never overwrite another owner's branch.
5. Read back remote SHA. At the integrated checkpoint fetch into a fresh isolated checkout with hooks/submodules/provider startup disabled and compare every manifest artifact hash. A successful push response alone is insufficient.

Required cadence: captured worker package, review correction, integrated tested result. Do not make a commit per keystroke or republish runtime archives. Other repositories retain their own source ownership and remotes; don't dump a dirty Orca tree into public PAEOS. Capture and classify the exact cross-repository recovery scope before P3.

## Private recovery implementation choice

Use **restic repository version2** for the planned encrypted runtime snapshot, subject to verifying/installing an exact official binary and authorized storage destination. Its documented `--password-file` mechanism can consume the existing high-entropy backup file as a repository password; it is not an age identity or Founder signing seed. Test compatibility with a synthetic file of the same format first. Do not display or inline the real password, transform it into another key format, or overwrite it. [Official repository/password-file documentation](https://restic.readthedocs.io/en/stable/030_preparing_a_new_repo.html).

The exact destination is still an external prerequisite: inspect existing approved private backup configuration first. If no zero-charge destination with sufficient capacity and recoverable access exists, prepare one minimal decision packet naming the proposed destination, capacity, access and sanitized snapshot manifest. Do not buy storage, accept new terms, alter Time Machine/USB backups or upload plaintext. This holds laptop-loss recovery and unattended claims, not provider-free source repairs.

Use restic only on a coherent quiesced export, not live SQLite files independently copied at arbitrary times. One writer serializes backup/check/restore operations. No prune/forget/destructive retention change without explicit retention authority. Test corruption/wrong password/missing objects and fetch/restore into execution-disabled scratch. Record repository/snapshot IDs, encrypted size, store watermarks and restore checks without secret data. Runtime keeps access only in the trusted backup-writer boundary; the USB copy is independently recoverable. Key custody alone is not a backup.

## Coordination without manual nudges

Existing completion protocol: `/Users/bob/.codex/paeos-coordination/completion-loop-20261018/protocol.json`; cache selected by `protocol.cache_path` (epoch3: `coordinator-state-v3.json`). These are noncanonical scheduling aids. Architect owns updates after the recorded 2026-10-19 handoff; the predecessor protocol/cache remain preserved. Do not silently edit another owner’s cache or treat cache statuses as PAEOS dispositions.

1. Coordinator selects the earliest eligible card from canonical dependencies and current budget. It sends the existing owner one bounded packet with source/manifest and exact wake condition.
2. Receiver validates ownership, baseline and scope. A native queued-message receipt proves delivery only. Genuine PAEOS admission/start/result are separate required observations.
3. Worker proceeds through implementation/verification/review within admitted scope. It reports one material completion, remand or blocker to the coordinator under the existing human-authorized callback protocol. No ACK-to-ACK loop and no messages to unrelated chats.
4. Coordinator validates candidate/evidence/disposition before advancing. A missing receiver acknowledgement/start is inspected once through compact task status; it does not trigger another provider attempt.
5. Continue immediately on an actionable completion event. Existing hourly fallback checks only missed/stalled events and authoritative wake conditions. Do not poll unchanged provider quota with model calls.

Routine technical ownership assignments are coordination, not a new authority root. Before presenting a hold, separate an absent implementation from an actual reserved permission. Cite the governing source or direct human restriction; a generated owner-gap note alone cannot establish Founder exclusivity. Finish permitted read-only source tracing and the exact construction/test packet without asking the human to research ownership. An offline source-construction authorization is not a runtime admission, send grant or qualification.

Callback content: card ID; owner; base/candidate SHA; manifest digest; actual run/task/operation IDs or explicitly NONE for source-only work; verification result; review provenance/disposition; Court observation/adjudication/qualification separately; public push/readback; attempt/usage state; `ALLOWED_NOW`, `HELD`, `AUTHORITY_OR_IMPLEMENTATION_GAP`; exact next owner and wake predicate. Raw secrets/provider responses stay private.

Fresh chats are allowed when context is degraded or a new bounded owner is genuinely needed. Before rollover, capture source/evidence, resolve or preserve all uncertain operations, fence predecessor, transfer remaining allocation and scope, get receiver acknowledgement, then archive predecessor. A fresh chat has no fresh authority/budget. Keep current Chat1 exclusive integration ownership until a verified successor handoff.

## Strong-model escalation packet

Luna first performs deterministic reproduction and narrows the question. Escalate only: authority interpretation with conflicting current records; security invariant failure needing a changed trust boundary; new schema/hash/protocol migration outside frozen semantics; repeated failure with distinct tested hypotheses; or complete-scope reviewer requirement beyond available qualified capability.

Packet: exact invariant and evidence, smallest reproducer, base/diff hashes, observed versus expected behavior, two concrete options with effects/risks, recommendation, required scope/authority, and remaining budget. Do not dump whole history or ask “what next?”. A strong architect response is advice; existing admission/review/Court still decide. If strong capacity is unavailable, checkpoint that dependency and continue independent eligible cards; do not ask weaker models to self-ratify it.

## Reserved human actions

Only ask when a real action is ready: private passphrase/key ceremony; exact privileged signer/enrollment/install action if required; a missing off-device destination/access decision; a concrete authority/scope/terms/cost expansion; final Founder ratification after P9. Do not ask again for the rejected separate account or approvals already covering the same bounded effect. Finish all preparatory implementation, tests, concrete packet and review before asking for the final action.

## Compact Luna handoff prompt

> Continue the saved PAEOS Luna guide at `docs/superpowers/plans/2026-10-18-luna-p1-p9-execution-guide.md`. Read the guide and only the next eligible card. Start B00/B01 from the saved candidate; do not restart programme planning. Preserve current owners, original findings, dirty main, consumed/UNKNOWN effects and all phase gates. Use architect as the single coordinator selected by the current protocol and real PAEOS admission/workspaces; no ChatBridge, subscription fallback or paid route. Keep production disclosure denied until the complete reviewed boundary and actual authority permit it. Finish synthetic work before the human-only Founder ceremony. Send material verified callbacks, use explicit sanitized Git checkpoints with remote readback, and continue automatically through eligible cards. Stop only at a concrete missing authority/action, budget/capability limit or final P9 ratification gate; report exact owner and wake condition.
