# B00 construction route and first-slice decision

**Decision ID:** `B00_BOOTSTRAP_S1_20261019`

**Status:** `COORDINATION_CHECK_PENDING`

**Type:** one-use, provider-free source bootstrap proposal; not a PAEOS admission, owner appointment, egress permit, or production activation

**Candidate branch:** `codex/p1-bound-source-recovery-20261018` at `c6f7444af4ef8b70b8ed6372361bc7be8e7c78c2`

**Pinned B00 source candidate:** `082a59ce163d15fc0d40141c1c6cc74e7522d063`

This packet narrows the previous owner-scope proposal. The previous packet and all original review findings remain unchanged. This decision is not for naming an owner inside an already delegated remit. It is for the exact new write scope below, unless the Architect verifies an existing delegation that covers it.

## Findings that determine the next gate

### Construction route

PAEOS has a local scheduler entrypoint: `ops/autonomous_run.py` reads a backlog and calls `build_scheduler`; `build_scheduler` constructs a local `AuthorityEnvelope`, `PersistentMissionController`, `RunStateRegistry`, and `SoftLoop`. `SoftLoop.run` registers a signed local run root and starts a root task. For Trace-B it separately requires `BuilderTransportReady` before the Builder can run.

That is evidence of local scheduler and run-root construction, **not** evidence of the external admission contract required here. The entrypoint accepts no independently verified admission receipt or owner-signed task-scope record; it creates the run identity and root envelope from its local arguments/state. The offline scheduler-readiness tests intentionally replace the worker with a function that fails if called. They establish refusal/composition behavior, not an admitted worker start or returned worker evidence. The user has excluded ChatBridge, so no ChatBridge route is proposed.

Conclusion: root/task registration is separable from the missing provider-send fence, so there is no circular dependency merely to construct a local task record. But this local route does not currently prove the required authenticated admission plus physical worker-start/return. A real provider-backed task remains held. This proposal therefore labels its first source change as an **offline bootstrap exception** and forbids calling it a PAEOS task.

### Existing owner scope and handoff

Chat 3's existing task is authenticated ORCA-to-PAEOS mission admission in an isolated candidate. Its task instructions grant narrow source/test work for that admission boundary. They do not establish ownership of provider disclosure or every outbound network path, and no repository policy was found extending them to the B00 egress boundary.

Chat 3 has now handed off its S0 candidate: the candidate is frozen pending independent review, the review request is prepared but not dispatched, and Chat 3 relinquished further candidate construction. No integration, review acceptance, or qualification is claimed. The handoff clears availability; it does not transfer S0 authority to B00.

The Architect's prior coordination role is acknowledged. The latest B00 follow-up says its thread was retired from completion dispatch. The Architect is checking whether any standing delegation covers the exact first slice. Until that check is returned, neither an executable delegated assignment nor a need for new Founder authority is asserted.

### Exact first slice

The B00 inventory identifies `ops/run_task02_codex.sh` as a manually callable, unguarded direct Codex route. Its current content runs `codex exec --dangerously-bypass-approvals-and-sandbox` and redirects a repository prompt into that process. The source hash matches the pinned inventory. No specific denial test currently covers this script.

The smallest useful first change is **retirement of that one out-of-band entrypoint**, replacing its body with a fixed fail-closed response and nonzero exit before prompt access or process launch. Add one synthetic test that runs the real script with a fake `codex` executable in a temporary `PATH`, verifies the fake executable is never invoked, checks the stable refusal, and verifies the script contains no prompt-open or Codex-dispatch command. The prompt file stays read-only. This closes only the `direct-codex-task-script` inventory path; it does not complete B00 or authorize any other route.

### Relationship to DEBT-0258

This one-file retirement **does not unblock DEBT-0258**. It closes an independent manual bypass and should be tracked as parallel P1 security work. Chat 1 remains the sole D0258 integrator.

The later B00 repair that can unblock a live D0258 Builder task is the canonical, owner-approved admission/currentness and disclosure check at the actual Codex outbound-send boundary, bound to the complete outbound frame and accessible-input closure, followed by a stage-qualified Builder route. The current Codex transport denies before prompt inspection/signing when trusted disclosure authority is unavailable. The retirement slice does not change that behavior, supply the missing currentness/revocation state, or qualify a worker. Only after those independent prerequisites are proven may the coordinator hand Chat 1 a fresh D0258 task contract and admission.

## Exact one-use bootstrap scope, if no standing delegation covers it

**Proposed technical owner:** Chat 3, for this slice only, after the S0 handoff already recorded above.

**Coordinator:** the completion overseer for this checkpoint. This does not reactivate the retired Architect dispatch thread or make the coordinator a source owner.

**Mutable source/test files:**

- `ops/run_task02_codex.sh`
- `tests/ops/test_run_task02_codex_denial.py` (new)

**Checkpoint-only records after verification:**

- `reviews/tasks/PAEOS_LUNA_B00_SCOPE_20261018/BOOTSTRAP_SLICE_01_REPORT.md` (new)
- `reviews/tasks/PAEOS_LUNA_B00_SCOPE_20261018/BOOTSTRAP_SLICE_01_CHECKPOINT_MANIFEST.json` (new; its own hash excluded)
- append-only entries in `PAEOS_HALLUCINATION_CHECKER_NOTEBOOK.md` and `MessyChangesNeedsReview.md`

`ops/backlogs/prompt-concept-os-task02.txt` and all B00 source/review records are read-only. The candidate starts from the branch SHA stated above in an isolated workspace. Do not alter the pinned source candidate, original review, or disposition.

**Permitted effects:** synthetic test execution, shell syntax validation, focused lint/format/compile checks, diff and secret scans, and an explicit sanitized recovery commit/push with remote-SHA readback. Record `PAEOS_TASK_ID: NONE` and `PAEOS_ADMISSION: NONE`; this is the bounded exception, not governed PAEOS execution.

**Forbidden effects:** any provider/process launch other than the fake test executable; network access; real prompt or user data in tests; key/credential/runtime-state access; PAEOS admission/start claims; egress enablement; edits to the disclosure authority, currentness store, send fence, Builder transport, Chat 1 files, or other unguarded routes; installation, qualification, Court action, debt integration, or P3.

## Acceptance and stop conditions

1. Baseline and exact two-file mutable manifest are frozen before edits.
2. The synthetic test proves the script returns the fixed refusal and never invokes the fake Codex process. `bash -n` passes. Focused test, applicable formatting/lint, compilation, diff checks, and secret scan pass.
3. Capture the candidate hashes and exact test outputs. Commit and push only the explicit manifest; verify the remote SHA. This is a recovery checkpoint, not a release or B00/P1 qualification.
4. Request one fresh independent read-only review of the exact pushed diff only through a verified free, privacy-eligible different-family route. No paid fallback. If no such route is available, record review as held; do not claim acceptance or proceed to any positive egress.
5. Keep the original inventory frozen. A separate progress record may say that this one path has a denial candidate; do not rewrite the original finding or report the other four unguarded paths as resolved.

After this slice, the next B00 task is a source-bound map of the existing admission/mission ledger and actual send owner. The map must distinguish a storage substrate from an authority root. `kernel/ledger.py` describes its append-only hash-chained ledger as PAEOS's sole authority, and `PersistentMissionController`/the mission graph persist task events there. This is a credible existing subsystem to investigate; the earlier finding that no send-fence API was evidenced does not establish that no suitable subsystem exists.

The current SQLite backend is durable and each row insert is atomic, but `Ledger.append` composes the next sequence from a read of the current head and then inserts; the SQLite backend uses autocommit plus a process-local lock and does not expose a transaction that spans currentness/revocation validation, the send claim, and the network owner's first socket write. It therefore is not already a proven cross-process send fence. The next owner map must determine whether this existing ledger can be extended with the required conditional transaction and whether it is the actual owner of admissions. Do not create a parallel authority database or trust root. If the existing store cannot meet the needed ordering, return the exact missing storage/authority primitive for a separate decision rather than silently adding a second ledger.

## Decision requested

The Architect must first report whether standing delegation covers **this exact provider-egress denial slice**. If it does, the Architect should make the one-item assignment under that delegation after confirming the S0 handoff; no Founder approval is needed merely to appoint an owner within remit. If it does not, the minimum reserved decision is:

> Authorize Chat 3, after its recorded S0 handoff, for one offline provider-free bootstrap change limited to `ops/run_task02_codex.sh` and `tests/ops/test_run_task02_codex_denial.py`, with the report/checkpoint records listed above. The change may only retire the direct Codex task-script route. It must use synthetic tests, stay in the isolated candidate, make no PAEOS admission or worker-start claim, and stop after the pushed checkpoint and one eligible read-only review attempt. This does not appoint a permanent B00 owner, authorize the full send-fence scope, unblock D0258, enable egress, or change the separate quota instruction.

The user's 20% reserve override for this week is a separate existing instruction. This packet neither extends its time window nor creates a spending ceiling or any paid-route authorization.

## Current gates

**ALLOWED_NOW:** preserve the source-bound route analysis; receive the Architect's delegation check; retain Chat 3's frozen S0 handoff.

**HELD:** the two-file write until the Architect confirms applicable standing authority or the user approves the exact one-use exception; all positive egress, B00 send-fence implementation, D0258 activation, dependent debt work, installation, qualification, Court action, and P3.

**AUTHORITY_OR_IMPLEMENTATION_GAP:** no externally evidenced task admission/start route for this candidate; no established owner for B00 provider-egress authority/currentness/revocation; no proven atomic send claim. Exact wake: the Architect's source-backed delegation result, then—if needed—the user's decision above. No source/test code has changed under this packet.
