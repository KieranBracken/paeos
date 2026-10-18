# Bootstrap and the first real PAEOS task

These are proposed implementation contracts, not existing APIs or activation authority. Root owns this lane. Keep every positive production path disabled until the combined boundary passes the gates below. Each card includes its own verification; the common capture/review/integration procedure is in `operations.md`.

## B00 — Freeze the smallest lawful offline repair

**Inputs:** source checkpoint `2ec6ca1a6e8ecb3eff611781e0c59905dbd0c19b`; latest human instruction to continue signing/disclosure/model-identity fixes; existing offline repair exception; original immutable reviews. **Output:** one bounded source/test contract and an immutable preimage manifest, not a task-admission receipt.

- [ ] Verify candidate HEAD/status, inventory any later edits and compare the recorded49-file manifest. Read the latest notebook and router invariants.
- [ ] Record which current human authorization covers each B01–B03 effect. Offline synthetic implementation is separate from human enrollment, installation and live qualification. Do not carry an older one-use operation into a new package by changing its name.
- [ ] Freeze B01 source/tests below; keep kernel ledger/capability and debt integration forbidden. Pin read-only admission, policy, broker and supervisor dependencies.
- [ ] Before B01 writes, bind the admission/send fence with Chat3 to the actual admission owner. Required adapter semantics are `acquire_send_lease(admission_ref, expected_epoch, logical_job_id, frame_digest)` and `finish_send_lease(lease_id, observed_outcome_ref)`: durable identity, authoritative current admission, exclusive ordering against revocation, bounded lifetime, and unresolved leases preserved after crash. These are proposed internal operations, not existing APIs. Revocation must invalidate unclaimed leases or wait for the defined already-claimed send boundary. The lease must span the router send claim and start of transmission; a worker cannot mint it. Reuse an existing equivalent if present. If absent, prepare one narrow admission-owner implementation contract and exact race test; do not add it to Chat1's kernel scope or silently invent authority. No positive B01 acceptance until this prerequisite is evidenced.
- [ ] Capture the original Security Review hash and append remediation references; never edit the report. Preserve the current seven collection failures separately.
- [ ] Document all enabled egress call sites found with `rg`, including direct forwarding, planner, producer, compatibility and UI helper paths. Each row must be `ENFORCED` or `DISABLED`, with a negative test. An unclassified alternate path blocks positive activation.
- [ ] Freeze synthetic test environment: fresh temporary HOME/state/database/workspaces; no host `.env`, keychain, auth file, USB contents, real database or external network. Interpreter and dependency origins may be read from the pinned environment, not project imports from dirty main.

**Exit:** exact scoped repair package is reviewable. If a required change would amend authority rather than implement existing permission, finish its concrete design/test packet and escalate that amendment only. Do not block independent source tests on a private-key ceremony.

## B01 — Trusted public policy state and durable disclosure attempts

**Modify:** `paeos/model_router/state.py`; add `paeos/model_router/disclosure_authority.py`. **Tests:** add `tests/model_router/test_disclosure_authority.py`, `tests/model_router/test_disclosure_attempts.py`; retain `test_disclosure_policy.py` and `test_disclosure_store.py`. **Read-only:** existing admission/contracts, public policy loader, runtime ledger.

**Design decision:** extend the existing Policy Router database for router-owned disclosure revisions and attempt reservations. This is not a new authority database. Founder signatures supply classification/disclosure authority; existing PAEOS admission supplies execution authority. Router storage enforces consumption/currentness and joins those identities. Do not fix Chat1's kernel ledger in this lane. Current `RouterStateDB` uses `synchronous=NORMAL`; the new reservation transaction needs explicitly tested durable settings, including `FULL` for its connection. Do not assert present storage already offers this property.

**Proposed internal boundary:** `DisclosureAuthority` is constructed only by the reviewed supervisor composition root from protected enrolled configuration and the existing trusted admission verifier. It exposes authorization/reservation and final send-claim operations to trusted transports. Worker requests may supply identifiers to look up, but never a verification key, classification, trusted flag, policy-store path or verifier callback.

**Persisted facts to add through a versioned migration in the existing DB:** enrolled policy ID/key fingerprint/host activation epoch; current revision/digest/revocation; root allocation identity; logical operation plus ordinal; admission, task/run/stage/role, closure, frame and exact route digests; reservation/send/return/refusal/uncertainty timestamps and attributable usage references. Use unique constraints for logical identity and settlement. Preserve previous records; no reset-on-start or new-chat replenishment.

Add a separate `open_enrolled` authority path: it opens only an existing enrolled database/configuration and never invokes the current create-directory/create-database/default-seeding constructor. Explicit trusted enrollment/migration is separate. Missing/replaced DB, WAL inconsistency, missing enrollment metadata or unexpected schema must deny without recreation. Existing health-only state behavior may remain compatible; it cannot default-activate disclosure.

**Transaction contract:**

```text
BEGIN IMMEDIATE
  verify protected enrollment epoch and exact signed policy revision/digest
  verify policy not revoked/expired and actual admission still current
  verify purpose, role/stage, route, approved input/transform closure and exact frame
  reject duplicate/conflicting logical operation, including unresolved predecessor
  check remaining root allocation including outstanding/UNKNOWN reservations
  insert immutable reservation with all binding digests
COMMIT (durable before any socket write)
```

A separate atomic send claim rechecks policy/currentness immediately before the network owner starts transmission. Revocation linearizes against that claim: a later revocation cannot retract bytes already sent. A crash after reservation or send claim remains non-replayable until authoritative reconciliation; even a request believed unsent is not released by elapsed time alone. Admission revocation and disclosure revocation need an enforced shared dispatch fence or a proven existing lease contract; a check followed by an unrelated transaction is insufficient. If that fence cannot be implemented within existing authority, return the exact missing primitive; never treat signed but stale admission as current.

- [ ] Add failing tests using a temporary RouterStateDB and synthetic signed policy/public identity. No default HOME database may be opened.
- [ ] Implement schema migration and bounded no-follow protected configuration loading; reject worker-writable enrollment configuration, symlink ancestors, unknown schema and corrupt/missing state.
- [ ] Implement transaction and query-only reconciliation; protect the DB from worker filesystem access. Only the trusted owner may activate/revoke policy revisions.
- [ ] Exercise two real processes/connections racing the same operation: one reservation; conflicting frame, new UUID with same logical effect, stale revision and repeated settlement all refuse.
- [ ] Kill at pre-commit/post-commit/pre-send/post-send/pre-receipt boundaries. Reopen preserves consumption/uncertainty; rollback before commit cannot leave a claimed send. DB-full/locked/unavailable yields no transmission.
- [ ] Test revocation racing send claim, policy downgrade, restored older snapshot, clock reversal and epoch mismatch. A restored host starts disabled until trusted ownership/currentness reconciliation; local counters alone do not establish currentness after disaster recovery.
- [ ] In restoration tests, retain an independently current authority watermark or require refusal pending reconciliation. Restoring both the database and its local epoch can make two stale values agree; signatures/root ownership/transactions cannot detect arbitrary rollback without a non-restored trusted reference. Do not manufacture a newer fixture counter and call it rollback detection.
- [ ] Run focused tests, lint/format, compile and diff/secret checks. Push a sanitized package; do not install it.

**Exit:** atomic synthetic positive path plus all negative controls. This does not authorize disclosure until B02/B03 prove actual payload and accessible inputs.

## B02 — Actual payload, derived outputs and every egress boundary

**Modify:** `runtime/integrations/trusted_codex_transport.py`, `trusted_codex_planner_transport.py`, `task_scoped_responses_broker.py`, `provider_broker.py`, `ops/trusted_worker_launcher_service.py`; `paeos/model_router/disclosure_policy.py` only for an explicitly versioned derivative format. Add `paeos/model_router/disclosure_frame.py` and its focused tests. Add/extend relevant `tests/runtime/test_*disclosure*.py` and response-auth tests.

**Existing v1 remains exact-artifact-only.** Do not quietly reinterpret `EXACT_ARTIFACTS` as permission for arbitrary future workspace files. A version2 policy is needed for ongoing engineering output. Its signed scope enumerates approved source identities/hashes, allowed deterministic templates, named transformation/tool implementations and dependency digests, inherited output class, purposes/destinations, size/time/attempt limits and exclusions. It grants no new execution authority. Invalid/unknown versions fail closed. Derived output may retain or increase input sensitivity; no automatic downgrade. All inputs, including the user's mission brief and restored conversation history, need trusted provenance.

Version2 must also cover authenticated model-response/history provenance: exact preceding request and route/response receipt, task/run/session binding, inherited classification and approved use. A model-produced label or signature cannot establish authority. Reject another task's response/history and unverifiable restored transcripts. Implement and test this version before the combined B04 review.

**Initial tool envelope:** read approved immutable file; propose bounded patch; trusted parent applies patch only within allowed candidate paths; run exact allowlisted test argv with synthetic state and fixed dependencies. No general shell, arbitrary Python snippet, downloaded package, remote URL/file reference or unmediated computer tool. Model text is data, not a tool authorization. Additional tools require their own reviewed transformation and confinement proof.

**Frame rules:** strict UTF-8/duplicate-key rejection, closed versioned schema, size/depth limits; bind complete instructions/history/input/attachments/tool definitions/results and the actual destination/model/entitlement. Resolve content before authorization, never after. Reject unsupported remote references. Serialize once, hash those bytes and transmit those same bytes. A transport-local bearer/session credential is SECRET even if it only works on loopback: prevent its inclusion in prompts/tool outputs, and keep parent-only secrets inaccessible. Literal redaction is supplementary, never the provenance mechanism.

- [ ] Add tests proving missing/worker-authored/unknown classification causes **zero signatures and zero network calls**.
- [ ] Add an allowed synthetic non-SECRET frame that reaches a fake in-process upstream with exact byte equality, then rejects one-byte mutation after authorization.
- [ ] Test Builder permission used as Planner, foreign task/run/session, stale admission/epoch, wrong purpose/route/model/family, nonfree entitlement, oversized/duplicate/unknown JSON, opaque attachment, changed tool output and unbound restored history.
- [ ] Test approved initial prompt followed by an unauthorized later tool result; the second frame must refuse without sending it.
- [ ] Enforce the same bound reservation at HTTP ingress and `_forward_to_chatgpt`; direct method invocation, injected forwarder and another client cannot bypass it. Parent auth loading happens only after authorization.
- [ ] Integrate the producer's independent signed-response identity without reusing the Codex supervisor private response key. Missing producer verification identity must fail before treating response content as evidence.
- [ ] Keep unsupported provider/UI/legacy paths denied. Preserve valid existing response-auth and model-identity behavior, including per-request pairing and truthful HTTP error versus identity failure.

**Exit:** every enabled network owner enforces the same current authority and exact payload; negative tests exercise actual forwarding seams. No live provider call is needed for this package.

## B03 — Closed worker input and execution environment

**Modify:** `runtime/integrations/worker_confinement.py`, `process_supervisor.py`, `ops/trusted_codex_worker_supervisor.py`, relevant `kernel/sandbox_backend.py` seam if admitted. **Tests:** `tests/runtime/test_worker_confinement_mutations.py`, `tests/kernel/test_sandbox_confinement.py`, new `tests/runtime/test_disclosure_closure.py`.

**New/proposed tool mediation:** `runtime/integrations/mediated_worker_tools.py`, `tests/runtime/test_mediated_worker_tools.py`; trusted parent maps closed requests `read_artifact(artifact_id)`, `propose_patch(base_digest, patch)`, `run_test(test_id)` to the frozen contract. The model cannot supply executable/argv/environment. Verify a real enforceable adapter/hook for the pinned transport; current supervisor use of `--dangerously-bypass-approvals-and-sandbox` plus outer Seatbelt does not establish command mediation. If the CLI cannot disable its unrestricted built-in tools or route them through the hook, it is transport-only until a scoped compatible adapter exists. Do not mistake a prompt telling it to use approved tools for enforcement.

Current broad system-read roots and unrestricted process/IPC allowances do not prove closed inputs. `kernel/sandbox.py` resource limits are not a filesystem/network security boundary. Do not disable confinement when a test or SDK needs more access.

- [ ] Inventory the exact worker executable, libraries, resources, configuration and approved source closure. Capture immutable dependencies; do not grant broad `/Users/bob`, `/Volumes`, `/opt/homebrew`, mutable caches or parent state merely to make startup work.
- [ ] Separate parent-owned broker/auth/policy/attempt state from the worker. Explicitly close inherited file descriptors and build a minimal environment, working directory and credential-free HOME. Deny all egress except the bound broker endpoint and necessary validated IPC.
- [ ] Strip `PAEOS_TASK_BROKER_TOKEN` and all parent/transport credentials from tool-child environments; the present CLI sees its local broker token, so test actual tool/CLI output and frame rejection as well as subprocess environment. Never classify this credential as PUBLIC because it is short lived.
- [ ] Enforce approved tools/argv before subprocess creation. Child processes inherit confinement. No alternate interpreter/helper can enlarge access. Patch application validates relative paths, symlinks, modes and exact preimages.
- [ ] In temporary real subprocesses, prove approved reads/writes and named tests work. Then prove denial for outside-root and sibling files, final/ancestor symlinks and swaps, USB-key sentinel, policy/attempt store, supervisor files, parent auth, inherited secret environment/FD, unapproved executable, argv variation, IPC helper and alternate endpoint.
- [ ] Add a file after closure capture and attempt to disclose it; deny or require fresh approved derivation. Test tool output containing the synthetic local broker credential; it must not enter the outbound frame.
- [ ] Test enforcement unavailable/malformed policy: no worker launch, no weaker fallback. Record executable/OS/sandbox identity, argv, exit/stdout/stderr and sentinel outcome; never use real keys as canaries.

**Exit:** actual worker process can do the bounded task and cannot obtain excluded inputs. If the current Codex transport requires an unrestricted shell or broad home access, disable its editing capability and report the precise incompatibility; a transport-only canary does not resolve it.

## B04 — Bundle, one fresh Security Review, and Founder ceremony

**Bundle scope:** `ops/install_trusted_codex_worker_supervisor.py`, its existing installer tests, new temporary startup/confinement tests, and the exact source/resource closure. Existing bundle has13 files and needs the new disclosure closure; static imports alone are insufficient.

**Signer/enrollment scope before review:** proposed `ops/founder_policy_signer.py`, `ops/install_founder_policy_signer.py`, `tests/ops/test_founder_policy_signer.py`, `tests/ops/test_founder_policy_enrollment.py`, owned by the bootstrap integrator under a frozen synthetic-only package. Protect the complete signer executable/interpreter/dependency closure; refuse non-root owner, writable ancestors, substituted binaries/configuration, symlink leaves, changed policy after display and private-key export fields. Test generation/signing with synthetic material in temporary roots and a real subprocess, including public-only outputs. Human creation/enrollment uses the reviewed installed bytes later; no post-review signer implementation. If implementing the signer requires authority outside the current offline repair, prepare this exact package for the reserved decision instead of spending the one final review on an incomplete bundle.

- [ ] Preserve `install(source_root, runtime_root=...)` compatibility. Build reviewed source against main runtime interpreter/queue/workspace/valid existing keys; never overwrite main's four mismatched untracked bootstrap files.
- [ ] Add real temporary bundle subprocess startup, signed synthetic identity and live supervisor proof; missing-dependency negative. Test no-follow roots/ancestors/leaves, outside-root sentinels and existing request-key preservation. No LaunchAgent, host credential or provider effects in tests.
- [ ] Run combined focused/regression/static checks; record all failures. Full integrated suite once, retaining the current seven collection failures unless actually fixed through admitted closure restoration.
- [ ] Push/read back exact candidate and manifest. Request **one fresh independent read-only Security Review** under the actual review authorization; record what model/family/provenance is and is not available. A plan critique is not that review.
- [ ] If actionable findings return, preserve them unchanged, hold install/canary and report the smallest remediation scope. Do not spend repeated review calls or claim heterogeneous L14 without evidence.

**Signer design to prepare before human steps:** no separate login. A distinct root-owned0700 Founder-key directory on the encrypted USB; a small reviewed deterministic signer and complete root-owned executable/dependency closure; human-invoked administrator action; runtime sees only public identity and signed policy. Never run privileged Python from a user-writable checkout/venv. Never reuse `backup-decryption.key`.

**Threat model:** protects against confined unprivileged PAEOS workers; trusts human, OS and narrowly installed supervisor/signer. It does not claim protection from an arbitrary unsandboxed administrator-capable agent. Private volume stays locked in ordinary operation; human signing occurs with workers quiesced and privileged credential caching cleared afterward. A paused chat alone is not OS isolation. If actual installed confinement cannot exclude elevation or key/config modification, stop before real key creation.

**Human-only ceremony, after tested reviewed package is ready:**

1. Present a short policy summary: exact authority/purposes, source and transformation scope, named destinations/privacy/free entitlement, limits/expiry, revocation and exclusions. Do not ask the human to review raw opaque JSON alone.
2. Human unlocks USB privately and runs the exact reviewed administrator installer/signer. It generates a separate Founder key exclusively in the protected USB directory; no key bytes are printed/exported to agents. Verify root ownership/modes and executable/dependency hashes without reading private content.
3. Export only public key and signed policy; enroll via the reviewed protected path. Human independently checks displayed public fingerprint against the exported identity. PAEOS cannot self-select its trust root.
4. Clear administrator authentication cache; lock/unmount the key volume. Verify routine worker cannot read key/config sentinels or elevate. Reopen/lock recovery test is human guided and credential private.
5. Routine tasks now use the signed bounded policy without repeated signing. A scope/route/expiry/revocation change may require a new human ceremony; do not promise perpetual unattended signing.

Exact administrator commands are produced from the accepted bundle at execution time. Publishing commands pointing at nonexistent or unreviewed signer code here would be unsafe. This is a bounded command-generation task with the above fixed acceptance, not an invitation to redesign key custody.

## B05 — Authorized installation and exactly one transport canary

**Entry:** clean applicable Security Review on exact bytes, real enrollment, complete confinement, exact activation authority and reconciliation of any prior operation. A previous one-use authorization cannot be assumed unused; verify its operation record before consuming it.

- [ ] Check queue empty, no active Builder, installed/source bundle hashes, actual executable/version, host identities reused and main's untracked files unchanged.
- [ ] Install reviewed source against runtime root only. Rollback is safe disabled state if prior code had the privacy defect; never reopen old unrestricted egress.
- [ ] Freeze one fresh qualification task with actual run/task/scope/workspace/stage/role/route/disclosure and logical operation identity. Route is the authorized `gpt-5.6-sol` canary unless the actual package authority specifies otherwise; changing the current chat to Luna does not rewrite this contract.
- [ ] Require receiver start, signed request/response, exact server-model identity, passing positive/negative confinement canaries and exactly one broker call. Capture effect and qualification disposition separately.
- [ ] Timeout, interrupted response, missing identity or lost acknowledgement is `UNKNOWN` or explicit refusal according to observation; do not rerun. Query original operation without a new provider call where possible.

**Exit:** transport qualification only. Editing capability is separate and must be established before a Builder receives a source task.

## B06 — Stage readiness and the free independent route

For the next codec task create exactly one matrix: stage, applicable capability, role, family constraint, input class, tool rights, qualification digest/expiry and exact route. Read canonical lifecycle applicability; do not assume only Builder and L14 need models. Reuse valid evidence; probe only missing capabilities.

Route owner verifies current official terms for the named endpoint/account/model, no-training requirement and permitted limited safety/security logging for INTERNAL, zero-charge entitlement and actual family. PUBLIC availability or a model catalogue entry is not enough. Exclude the retired NVIDIA entry and unavailable subscriptions. No paid fallback or auto-router that hides actual family/terms. Do not test eligibility by sending project content first; use a synthetic probe only after eligibility is established. Persist rate-limit reset/health once; no repeated provider polling.

**Editing qualification:** actual approved read, patch returned/applied within scope, named test executed and evidence captured; prohibited read/write/tool refused. Verify genuine start/response and physical identity. A text echo does not qualify editing.

**Exit:** all mandatory capabilities for the codec are current and the actual task may be admitted. If L14 remains unavailable, do not launch work whose contract requires that missing gate to complete; retain permissible local preparation. Wake Chat1 with D258-A, exact candidate and fresh admission, not the abandoned operation or ChatBridge harness.
