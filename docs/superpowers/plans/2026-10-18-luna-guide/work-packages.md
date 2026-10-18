# Debt and phase implementation cards

Every card inherits the main guide's constraints and operating procedure. Source paths are relative to the stated repository. Names marked **new/proposed** are planned files/interfaces, not claims of existing software. Before each phase, bind the listed paths to its qualified predecessor tree; later edits may change line numbers. Missing required source becomes an explicit source-origin task, never permission to import dirty main.

## D258-A — First real task: contract codec

**Owner:** current Chat1. **Entry:** B06, fresh PAEOS admission, immutable candidate. **Mutable files:** `runtime/implementation_contract.py`, `tests/runtime/test_implementation_contract.py`. No kernel keys/ledger/token/supersession changes.

Existing types are `AcceptanceCommand` and `FrozenImplementationContract`. Add exactly:

```python
def canonical_implementation_contract_bytes(contract: FrozenImplementationContract) -> bytes: ...
def implementation_contract_from_canonical_json(raw: bytes) -> FrozenImplementationContract: ...
```

These signatures are the proposed support API. Canonical envelope fields are `contract_id`, `contract_hash`, `goal_id`, `run_id`, `ceremony_trace`, `base_commit`, `allowed_paths`, `required_artifacts`, `acceptance_commands`, `rollback_argv`, `data_class`, `context_manifest_hash`, `derivation_register_hash`. Commands contain `command_id`, `argv`, `cwd`, `timeout_seconds`, `expected_exit_codes`. Do not import the larger archived schema.

Freeze encoding as UTF-8 JSON, sorted object keys, compact separators, `ensure_ascii=True`, no trailing newline; tuple fields encode as arrays. Preserve array ordering for round-trip. Existing semantic hash independently sorts allowed paths/artifacts and excludes contract ID/hash; **envelope SHA is not `contract_hash`**. Decoder requires canonical bytes, exact field sets at every level, real integer types rather than booleans, nonempty correct strings, valid relative paths and recomputed existing semantic hash. Validate before returning an object. Do not silently strengthen unrelated legacy validators without consumer tests/scope.

- [ ] Preserve existing hash vectors; add deterministic envelope and exact round-trip tests.
- [ ] Add duplicate/unknown/missing-key, malformed command/array, boolean-int, bad hash/path and noncanonical whitespace/key-order negatives. Test array ordering versus sorted semantic hash explicitly.
- [ ] Run focused module tests in the admitted candidate; verify import origins, capture returned patch and physical task/run/start/result evidence.
- [ ] Independent reviewer reproduces against captured bytes, then Chat1 integrates through the applicable disposition. Record this as one completed support API, not D0258 qualification.

Named new tests should express `test_codec_round_trip_preserves_command_order`, `test_codec_rejects_duplicate_nested_key`, `test_codec_rejects_bool_timeout`, `test_codec_preserves_existing_semantic_hash`. Each malformed input must fail before a usable contract is returned.

## D258-B — Atomic ledger and public-only verifier (two reviewed slices)

**Owner:** Chat1; separate contracts for each slice. **Entry:** codec integrated; exact caller signatures frozen from consumer requirements.

**Ledger mutable files:** `kernel/ledger.py`, `kernel/ledger_sqlite.py`, `tests/kernel/test_ledger.py`, `tests/kernel/test_ledger_sqlite.py`. Add public `Ledger.append_once_if_new` backed by one actual storage transaction. Preserve row/hash/domain semantics. Stable transaction ID, exact expected head, authenticated consumption and duplicate refusal are required; no fallback to `append` or private-store access. Decide exact parameters against current `LedgerRow`/append consumer before writes; a five-minute call-site inventory must produce the typed signature in the task contract. This is API binding, not a new architecture round.

- [ ] Real two-process SQLite race accepts exactly one row; stale head, changed-payload replay and duplicate consumption refuse.
- [ ] Close/reopen preserves consumption; commit-success/response-loss is still consumed; pre-commit rollback has no effect. Broken chain and writer contention reject truthfully.
- [ ] Implement only the minimal migration/transaction needed; do not copy the archived38KB ledger into the current smaller baseline.

**Verifier mutable files:** `kernel/capability.py`, `tests/kernel/test_capability.py`, relevant `test_capability_properties.py`. Add `CapabilityVerifier` constructed with public verification material only. Reuse verification semantics, no private key loading/generation, minting or ledger mutation.

- [ ] Existing synthetic broker token verifies; foreign key, altered signature/payload, wrong role/goal/run/session/operation/mission digest/ledger sequence/domain/expiry refuse.
- [ ] Separate current-token authorization from verification of historically consumed obligations. An expired token does not erase a valid pending supersession recorded at its historical sequence/time.
- [ ] Existing broker verification regressions pass; public-only construction has no file writes/key generation. Independent review of each exact slice precedes integration.

## D258-C — Supersession, pending denial and actual consumers

**Preserved reference:** `reviews/tasks/PAEOS_DEBT0258_SOURCE_CONSTRUCTION_20261015_db28d1ca/`; module SHA `47a0ad002c18487f5acc6290959bf5d41e9f2617aedd08995c6ddc78a8092144`, tests SHA `fc5ac02fff3bd75f8acd8aa2266ff8c68ffe44696774d1d72a0519a2afc71e7c`. Historical57 tests/four controls/one observation do not authorize integration.

**First scope:** new `runtime/scope_supersession.py` plus `tests/runtime/test_scope_supersession.py`, using the reviewed support APIs. Reconcile reference bytes to current schemas; fresh review covers the resulting combined tree.

- [ ] Bind canonical request, signed authority, immutable policy/CAS references, exact predecessor and successor prestate. Scope is an authorized strict superset; acceptance obligations cannot disappear. Each allowed path has hash or ABSENT.
- [ ] Detect cycles/dangling claim edges and include transitive impacted claims. Consume once atomically; output only `PENDING_REQUALIFICATION_AND_ACTIVATION`, never activation.
- [ ] Fresh successor task implements read-only pending observation using the abandoned task's `scope.reviewed.json` acceptance. Validate ledger chain/head, transition `scope-supersession:<tx>`, domain, canonical bytes, historical token and retained obligations. No mutation from observation.
- [ ] No consumed record means `NO_CONSUMED_SUPERSESSION_OBSERVED`, not ACTIVE. Pending record denies predecessor and unactivated successor after expiry and reopen.

**Next separate consumer scope:** audit call sites in `runtime/orchestrator/__init__.py`, `runtime/candidate_materialization.py`, `runtime/court/completeness_firewall.py`, `kernel/evidence.py`, `kernel/promotion.py`, `kernel/seal.py`. Freeze the actually reachable consumers before writes.

- [ ] Carry observed head/currentness through admission, evidence, review, Court and seal. Race a supersession between check and use; reject stale preconditions before effects.
- [ ] Mutated CAS, forged/ambiguous grant, stale head, duplicate consumption and lost-response replay all refuse. A caller's matching hashes/prose are not authority.

## D258-D — Executor custody and D0258 qualification

**Owner:** Chat4 supplies custody slice; Chat1 integrates. **Entry:** D258-C and exact executor/admission interfaces. New module location is chosen under `runtime/integrations/` adjacent to the actual executor; freeze that one path and tests before dispatch. Do not pretend an `ExecutionCustody` implementation already exists.

Required public semantics: `describe` reports actual executor capabilities; `start_once` durably accepts one logical job and exact request digest under fenced authority; `query` returns authoritative accepted/running/result/unknown state after lost acknowledgement or restart; `cancel` distinguishes request, acknowledgement and effects already completed. The caller cannot supply observed start/result or mark itself qualified.

- [ ] Freeze typed request/result schema from existing mission/admission identities and CAS references; no parallel mission root.
- [ ] Kill caller/executor before and after acceptance, process start, result persistence and acknowledgement. Reconcile same logical job. Lost ACK never authorizes duplicate start.
- [ ] Verify output/candidate provenance, cancellation races, stale fence and conflicting request digest. A `BUILDER_STARTED=true` flag fails the negative control.
- [ ] Obtain independent audit, physical Court adjudication and affected baseline requalification. Record exact D0258 qualification receipt; only then wake D0260.

## D249-A — Council candidate and fresh review

**Owner:** D0249. **Entry:** currently eligible exact lease/admission and B06 review capability; disjoint from Chat1 files. Reference `reviews/tasks/PAEOS_DEBT0249_COUNCIL_SOURCE_CONSTRUCTION_20261015_a8ea317d/`.

Mutable `runtime/critique.py`, `tests/runtime/test_debt0249_remand14.py`; regression `tests/runtime/test_l09_critique.py`. Captured source SHA `3dafd096208d5a62144791a9504dddb189d2615eebbf47b3107463a7a9c9908e`; tests SHA `54efec89f89bb85bea7d17eca0bb4b9a236468bf80d64c8bb923cb34cddaf013`.

- [ ] Reproduce valid mixed dissent/reject, reordered view and CAS reopen controls; reject altered approval/stance/risk, missing/extra keys, boolean risk, swapped/nonexistent hash and duplicate dissent.
- [ ] Obtain a fresh eligible different-family review of exact bytes; resolve findings within scoped admission. The October17 zero-attempt retired-model receipt is not a review.
- [ ] Integrate only through owner/disposition; historical51 tests do not seal Council or D0249.

## D249-B — Required hardening slices and16-domain accounting

**Inputs:** `reviews/architecture/DEBT_0249_PROGRAMME_CONTRACT.md`, its acceptance manifest/gap matrix/soft-guarantee register and current debt ledger. **Output:** one row per ELH-01…16, explicit ELH-14-WF sub-obligations, each with authority, current phase, source owner, predicate, positive/negative test, evidence and disposition.

Prioritize ELH-01/06 provenance; ELH-02/03/04/09/10 authority/separation/promotion/currentness/synthetic segregation; ELH-08/11 restart/convergence jointly with D0117; ELH-12/14/15/16 routing/semantic/applicable architecture/Council. Locate exact mutable files from each predicate and existing tests, then give each slice one bounded contract. Reuse `tests/runtime/test_completeness_firewall.py`, `tests/kernel/test_promotion_policy.py`, confinement mutation tests and relevant router tests.

ELH-07/SG-018 calibration remains held until its exact owner/lease is admitted. Shared files integrate serially. Preserve lawful later/post-P9 dispositions; neither omit an obligation nor convert every maturity improvement into pre-P3 work. If contract prose conflicts with later ratified phasing, record the exact authority resolving it. Unresolved authority conflict holds that slice.

## D260 — Primitive sufficiency before Builder authority

**Owner:** D0260. **Entry:** D0258 qualification. Existing seams: L02 `runtime/triage.py`, L03 `runtime/agents/`, L09/L10 `runtime/critique.py` and existing adversary, L11 `paeos/semantic/freeze_guard.py`/implementation contract, L12 orchestrator. No new central architecture-analysis service.

- [ ] Freeze applicability, assumptions, authority boundaries, uncertainty states, invariants and required primitives into existing immutable contract/CAS/ledger artifacts.
- [ ] RED: a normal applicable proposal relies on a started flag to recover lost acknowledgement/restart/concurrent retry. It must be refused before Builder authority, naming missing durable `start_once`/query capability.
- [ ] Positive: separately evidenced sufficient custody passes this test while all other gates still apply. Simple genuinely eligible Trace-A work retains lawful economical handling.
- [ ] Missing/contradictory/stale/advisory-only analysis refuses; Builder assertion cannot discharge its own deficit. Physical admission test proves no token/worker effect on refusal.
- [ ] Independent verification and qualification, then wake D0117 only when its other predicates are met.

## ISO — Bounded D0261 goal isolation

**Owner:** existing concurrency/controller owner coordinated by Manager; exclusive file lease, not a new debt integrator. **Scope:** `ops/autonomous_run.py`, actual MDG/controller selector and focused isolation tests. Reference `docs/PAEOS_MULTI_GOAL_CONCURRENCY_CONTRACT.md`.

- [ ] RED MC-01/02: active child in goalA must not redirect goalB into A, including sequential restart and reversed graph order. `max_concurrency=1` does not fix this.
- [ ] Restrict reconstruction/selection to authenticated incoming goal/root lineage; conflicting or missing identity refuses. No hardcoded task names or selecting the first active leaf globally.
- [ ] Review/integrate this necessary D0117 dependency. Keep general concurrent goals disabled. Full C2/C3/MC-03…12 qualification belongs before P7 concurrency activation.

## D117 — Real remediation composition, then physical proof

**Owner:** D0117. **Entry:** D0258, D0260, ISO and named D0249 prerequisite slices qualified; no requirement for D0249 final qualification yet.

First review/reconcile preserved successor `PAEOS_DEBT0117_SOURCE_CONSTRUCTION_20261015_b8889bd7`: `runtime/autonomy/resume_engine.py` SHA `cd3edfbd4d9cbd96f30e46cb8ffa567c20cc8801db52b6242d4f2998088dfda7`, new `tests/runtime/autonomy/test_resume_checkpoint_admission.py` SHA `5d332af1352f9018a42811cb77a413446bbef57fa153ff28549694612eab82d5`. Historical38+13 tests are not physical autonomy proof.

- [ ] Replace production's hardcoded `task-A/C/E` graph unwind/`SEALED` return with actual admitted child execution, captured result, independent verification and real qualification. Use existing controller/authority/MDG/lifecycle/custody; no second controller.
- [ ] Consume real checkpoint admission on resume. Preserve expired lease facts for reclamation, durable retry/churn history and authenticated existing-parent/root identity. Parent continuation requires fresh original-blocker recheck, not child success alone.
- [ ] Restore exact required test origins (including pre-P2 scenario tests absent in recovery) only through an admitted manifest. The old D0117 protocol's ChatBridge/owner/launch instructions are historical, not executable instructions.
- [ ] Run one parent→child→grandchild mission through production entrypoint, genuine invariant failure/remand, governed repair, controller SIGKILL and automatic production restart. No chat prompt, graph fixture, direct qualification call or fabricated verdict may finish it.
- [ ] Verify original blocker rechecks, exactly one logical continuation effect per child/parent, durable job/lease/lineage reconstruction and real final seal references.
- [ ] Separate reserved-authority case must stop at the intended authority predicate, not an incidental import/TypeError. Record empirical remands/remediation and adjudication separately.

## P0 — Final pre-P3 and affected-baseline gate

Manager joins D0258, D0260, D0117, D0249 final16-domain accounting and all remaining canonical pre-P3 prerequisites. Resolve the D0249 combined qualification after D0117 contributes its evidence. Link exact current P1/PRE-P2/P2 qualification artifacts and affected-claim requalification; don't rely on historical final-status prose. Reconcile open debt IDs and lawful deferrals, scope/currentness, free-route readiness and fresh root allocation. One missing required seal holds P3; independent eligible repair continues.

Explicit preserved-baseline checklist: P1 heterogeneous audit and CF-01…06 enforcement at L11/L13/L16; PRE-P2 delegated repair/reserved STOP/learning and checkpoint/resume claims; P2 five-tuple identity/state/authority manifest, historical SAKG/Concept repository dispositions, LOF logical-versus-physical corpus disposition and SDCG nonblocking disposition. Validate each exact receipt/manifest and dependency impact. Missing or invalidated evidence opens only the affected bounded repair/requalification; do not repeat an already qualified archive or migrate a store because old prose requests it.

## P3 — Operational Orca boundary

**Repositories:** PAEOS plus `/Users/bob/GitHub/orca-strator`. Inspected Orca HEAD `bc587840a608480526c3fdb4d154d0febb7785b5` is dirty; capture selected dirty bytes and full dependency closure before any isolated candidate. Commit alone is not its complete state.

**P3-A identity and classifier.** Anchors: PAEOS `contracts/envelopes.py`, `contracts/task_classifier.py`, `contracts/orca_mission_adapter.py`, `runtime/autonomy/orca_lineage.py`; Orca `backend/app/task_classifier.py`, `schemas.py`, `models.py`, `routers/tasks.py`.

- [ ] Preserve original intent/brief/plan version and digest, producer identity, mission/logical-job/correlation/causation, scope/admission/disclosure and accepted PAEOS run identity.
- [ ] Classify engineering versus domain cognition without conferring authority. Reject disguised engineering and caller-authored provider/retry/skip-stage authority.

**P3-B durable delivery.** Actual PAEOS transport is `runtime/transport/orca_paeos_transport.py` (absent from recovery until admitted restoration). Replace hash-only sender trust, `force_enabled=True` defaults and “moved to inbound_processed means accepted.” Use producer-owned outbox, consumer inbox and actual admission transaction; acknowledge only durable acceptance. Do not mutate task state on GET or accept posted SEALED as qualification. Bind status/result to authoritative producer.

- [ ] Same logical job plus same payload recovers one acceptance; same ID/different digest refuses. Crash between accept and ACK returns the recorded job after restart.
- [ ] Running isolated Orca and PAEOS submit/accept/run/return one harmless mission. Capture actual wire/spool traffic and both canonical stores joined by identity.
- [ ] Tampering, stale authority, malformed scope, disabled adapter, bad classifier and unauthorized routing fields reject before effects. Demonstrate disable/rollback with pending-message preservation.
- [ ] Extend existing `tests/contracts/test_orca_mission_adapter.py`, `tests/runtime/test_orca_paeos_transport.py`, `tests/contracts/test_orca_mission_control_adapter.py`. Repair `ops/verify_orca_paeos_boundary_court.py`: constant phrase artifact hashes and a temp-file queue alone cannot qualify P3.

**P3-C mission freeze.** Freeze exact public-note files/identities/hashes/rights, offline HTML output root, citation manifest, deterministic integrity checker, contradiction report, unchanged input corpus and tool/network/time/cost limits. Hostile HTML renders safely, outside-root symlinks refuse, changed sources are detectable, every frozen note is accounted for. No publication. Preserve programme/corpus/mission-spec lineage through P8. Phase demonstrations are distinct genuinely admitted executions with their own logical-job IDs and phase purpose; never resubmit a consumed P3 job as P8. If a real mission is intentionally suspended across phases instead, its existing checkpoint and lawful continuation predicate must be recorded and reconciled, not replaced by a fresh ID.

**Exit:** actual two-process proof, negative controls, independent audit and Court on exact cross-repository candidate; prerequisite phase gate opens P4.

## P4 — Exact plans and truthful usable runtime

**P4-A approved-plan execution.** Orca `backend/app/council_planner.py`, `orchestrator.py`, `schemas.py`, `models.py`, `frontend/src/main.tsx`. Persist exact proposed/approved plan version/digest and execute those stages; stale approval after material edits refuses. Preserve settled answers; prompt enhancement cannot invent authority.

**P4-B truthful states and failures.** `backend/app/main.py`, `runtime_events.py`, `agents/registry.py`, `agents/stub_adapter.py`, orchestrator and frontend. Distinguish submitted/admitted/running/blocked/failed/stale/unknown. No success-shaped stub on governed paths. DB/provider unavailable and lost events remain visible; freshness comes from actual source/cursor.

Home spend/capacity and `/stats` must derive from authoritative observations with unit, source/time and availability. Missing metering is UNKNOWN, never invented zero. Remove hardcoded financial/capacity figures. Cockpit ticker must display persisted correlated events, never generated fallback rows. Test a synthetic ledger change through API to browser, missing/stale measurement, event persistence/reopen, duplicate suppression and disconnected state; no fabricated row may appear during outage.

**P4-C Idea OS cutover.** Existing `idea_os_database.py`, PAEOS `contracts/idea_os_lifecycle_adapter.py`; dedicated `backend/app/services/idea_os_store.py` is proposed, absent. Keep workflow/settings/runtime tables with their owners. Freeze dataset/table boundaries, integrity manifest, dual-read parity, canonical pointer switch, pointer rollback and unauthorized transition negatives. Historical665/14 counts are not universal acceptance. No destructive migration without ratified rollback drill.

**P4-D browser and STOP.** Existing `ErrorBoundary.tsx`, `IdeaOsDashboard.tsx`, `styles.css`, `main.tsx`. Add a minimal pinned Playwright harness (currently absent) now, expand at P7. Prove topbar/HALT usability at supported widths, independent tab crash/retry, mission intake/approval and actual STOP request/ACK/in-flight disposition/restart. STOP requested is not STOP confirmed.

- [ ] First remove real-host database reads from routine `backend/tests/test_phase4_runtime_ux.py` and historical hardcoded counts in `tests/contracts/test_phase4_cutover.py`; use synthetic temporary stores.
- [ ] Startup must not discover host `.env` or construct real stores. Configure isolated app before importing `backend/app/main.py`; providers disabled unless admitted for the physical mission.
- [ ] Browser action→wire request→durable state→visible result shares mission/plan/run identity. Exercise stale approval, DB/provider outage, disconnect/reconnect, STOP and rollback.
- [ ] Rewrite `ops/verify_orca_runtime_ux_court.py` source-text/host-count checks into candidate-bound browser/wire/state observations. CSS grep is not UI proof.

**Exit:** all four packages plus representative browser/real transport proof, heterogeneous audit and Court. Do not defer plan execution, failures or browser evidence to P6/P7.

## P5 — All substrate capabilities

Reference the captured September7 P5 design with current privacy/admission corrections. Its proposed implementation files are absent at inspection, so creating them is real work, not “enable existing service.” Preserve all six claim IDs including quarantine/authority containment.

**P5-A SAKG.** Existing `sakg/extract.py`, `store.py`, `ingest.py`, `outcome_observer.py`, `mcp_server.py`; proposed `sakg/continuous.py` implements `ExtractionRunner.run_once(ExtractionProbe)` and controlled watch. Bind source manifest/digest, durable checkpoint only after accepted append, empirical inserted/replayed counts. External read-only graph query returns namespace/snapshot/provenance and deterministic bounded results. Test unchanged no-op, changed extraction, crash between commit/checkpoint, idempotent retry, malformed-source no checkpoint, committed query visibility and namespace/write denial.

**P5-B Concept persistence.** Reuse existing `concept/store.py` WAL/read pool/transaction/outbox and `concept/ids.py` Crockford128 rules. Proposed `concept/canonical.py` is a small production path/config boundary if required, not another database framework. Independent process reopen preserves IDs/content; test conflict, rollback, namespace, read-only query, outbox and WAL recovery. Prove actual production path uses durable storage.

**P5-C grounded distillation.** Proposed `concept/distillation.py`, `contracts/research-distillation-v1.schema.json`. Bind every claim/theme/contradiction to approved note IDs/hashes/provenance. Explicit OPEN/RESOLVED/UNRESOLVED states; missing/conflicting resolution stays unresolved. Test altered/missing/revoked source, malformed states and conflicting resolutions. A note saying “true” is not verification of truth.

**P5-D synthesis.** Orca `backend/app/company/synthesis_engine.py`; proposed `synthesis_parser.py`. Validate the whole bounded closed-schema response before accepted mutation: supported single JSON object, exact known note IDs/hashes, unique IDs, valid nested contradiction state. Reject duplicate keys, prose/multiple-object ambiguity, unknown fields, bad hashes and oversized content; never print raw private malformed response.

SQLite commit plus filesystem replace is not a cross-store atomic transaction. Stage immutable content, commit a durable accepted-state/outbox reference, materialize projection idempotently; crash recovery resolves each boundary. Only then report artifact complete. Test process death before/after staging, commit and projection, not merely exception rollback.

**P5-E KAE/LOF.** Existing `kae/citation_pipeline.py`, `contracts/kae_lof_federation_adapter.py`; proposed `kae/acquisition.py` supplies durable local acquire/inspect/get_bytes/revoke through existing CAS/state ownership. Require trusted source root and usage rights; descriptor-relative no-follow reads, dedup/conflict, CAS integrity, durable revocation and downstream deny/quarantine. No implicit network fetch or external model disclosure. Test restart, corruption, revocation, conflict, symlink ancestors/leaves, outside sentinel and crash during object/ledger handoff.

**P5-F integrated quarantine.** Exercise the five capabilities through actual production entrypoints in the frozen envelope, including malformed/revoked data denial and immutable provenance joins. New `ops/verify_substrate_capability_court.py` must capture actual observations, not expected labels. Six existing design claims all have explicit dispositions. Heterogeneous audit and Court precede P6.

## P6 — Durable runtime, recovery and budget

P6 hardens already functional P3–P5 behavior; transactional guarantees necessary for earlier claims cannot wait here.

**P6-A transaction/event stream.** Existing state/event/outbox owners and Orca `runtime_events.py`/orchestrator: one committed effect with durable outbox; fresh read transaction/cursor per SSE cycle; unambiguous sequence or `(timestamp,id)`, not timestamp alone. Background jobs own their database/session lifetime, not a closed request session. Kill before/after commit/dispatch/ACK/projection/cancel; test equal timestamps, out-of-order/replay, DB locked/full/unavailable. Never return authoritative success after failed commit.

**P6-B recovery exporter.** `runtime/supervisors/checkpoint.py` currently leaves governance/transaction/reconciliation content incomplete. Populate actual referenced artifacts/authoritative store boundaries, unresolved operations, debt, leases and ownership. Fence new admission briefly; consistent DB snapshots plus immutable CAS reference closure; verify cross-store references before release. Use bounded quiescence if online coherence cannot be proven. Missing objects fail or explicit quarantine; never invent empty “complete” fields.

**P6-C encrypted recovery.** Use the restic version2/password-file decision in `operations.md`; preserve the existing backup file and test a synthetic same-format password before enrollment. It is not a Founder seed or age/OpenPGP identity. Prove synthetic restore before real snapshot. Measure staging space/encrypted size/upload time; one writer, deduplicate immutable objects, coalesce unchanged snapshots. Private backup destination and independently recoverable key access must be verified; USB key on same laptop is not off-device runtime backup. Restore with all execution/timers/LaunchAgents/provider dispatch disabled. After snapshot watermark any potentially dispatched operation remains uncertain until original-executor reconciliation. Local fence increment cannot fence another live host.

**P6-D root budget.** `runtime/scheduler.py`/existing governor must reserve before admission, charge children/reviews/retries/successors to same root, retain UNKNOWN reservations, settle attributable usage once, reconstruct after restart and reject new-chat resets. Token/time/attempt/money/account quota are separate dimensions; unknown usage is not zero. Join bootstrap router attempt records to root accounting without creating competing authority. Test concurrent reserve, kill/restart, duplicated settlement, missing metering and exhausted parent spawning child.

**P6-E engineering hygiene.** Compatible migrations/configuration/startup/secret/error/dead-path fixes; split `frontend/src/main.tsx` and `backend/app/orchestrator.py` along already tested interfaces only. A broad rewrite is not required. Derived performance budgets and rollback are frozen before migration; production migration remains separately governed.

**Exit:** physical kills and recovery drill, actual off-device encrypted fetch/disabled restore, durable-budget proof, applicable audit/Court and no unresolved required P6 debts. These are mandatory before claiming unattended laptop-loss resilience.

## P7 — Broader physical verification

- [ ] Expand existing P3/P4 harnesses across browser navigation/errors/approvals/STOP/reconnect, cross-system identity/provenance, actual multiprocess transport and namespace isolation.
- [ ] Qualify D0261 C2/C3 before general parallel-goal activation: canonical readiness, compatible atomic admissions, ordinary/repair/nested/retry paths, alias/shared-resource races, dependency-triggered refill, UNKNOWN reconciliation, fairness/root accounting; MC-03…12.
- [ ] Full Trace-B L01–L19 with authentic heterogeneous review, genuine failed-invariant remand and governed remediation. Test observer/verifier failures separately from candidate failures.
- [ ] Confinement corpus covers files/environment/descriptors/subprocess/IPC plus adapted tools and restored history. Revalidate after SDK/OS/tool changes.
- [ ] Freeze workload/corpus/machine/versions and product requirements before SLO thresholds. Measure repeatable resource/time envelope; never choose thresholds after observing a convenient pass.
- [ ] Complete omitted verification classes from original phase manifest, candidate-bound audit and Court. Fixtures-only traces cannot satisfy physical classes.

## P8 — Public-note catalogue Founder journey

Use the frozen P3 programme/corpus/mission-spec lineage under a fresh genuinely admitted P8 execution, or the explicitly preserved continuation of an actually suspended job. A terminal P3 demonstration is not replayed. Running Orca accepts ordinary language, settles consequential choices, preserves brief/plan approval, admits PAEOS work and returns a usable result through real transport.

- [ ] Deliver offline searchable HTML, source/citation manifest, deterministic integrity command and evidence-citing contradiction report. Enumerate every frozen note; inputs unchanged; no publication or network requirement to use result.
- [ ] Verify hostile note rendering, outside-root symlink denial, source-change detection, deterministic integrity and unresolved-versus-established claims.
- [ ] Encounter one authentic engineering gap; detect, admit repair, independently verify/review and resume. Label intentionally injected faults separately; no scripted verdict presented as autonomy.
- [ ] Demonstrate genuine remand, controller interruption/restart and STOP with same logical job and no duplicate effect, through the user-visible journey.
- [ ] Separately prove a real reserved decision defined in the frozen contract, such as a material corpus/scope extension: no effect without human approval; wrong or stale plan-version approval refuses; correct approval plus the required fresh current admission/supersession disposition resumes the same logical job exactly once. STOP and initial brief confirmation do not substitute for this decision gate. Ordinary in-scope repairs remain autonomous.
- [ ] Record required and avoidable Founder interventions, elapsed time and attributable cost. Routine prompt forwarding or terminal intervention fails the accepted outcome; legitimate reserved decisions remain required.
- [ ] Authorized learning uses actual bounded evidence, not inferred user preference or unapproved source ingestion. Complete audit and Court before P9.
- [ ] Physically query SAKG after the journey and after restart: newly committed outcome/learning node joins source, run, candidate and evidence identities. Replay is idempotent. Fabricated/unbound outcome cannot be promoted or counted as verified learning. This is the explicit P8.3 proof, not a prose reflection.

## P9 — Whole-estate audit and final stop

- [ ] Freeze all repository/tree manifests, obligation IDs, source/currentness/ownership map, phase evidence joins, open debt/remands/lawful deferrals, regression disposition, recovery drill and Founder journey.
- [ ] Compare against every original DAG obligation and October12 crosswalk. SDCG remains its ratified nonblocking adjacent research; historical SAKG/Concept repositories remain reference homes. No Sentium/Career work enters scope.
- [ ] Independent heterogeneous whole-estate audit covers completeness/reachability, security/authority, source/documentation drift, failure/restart/stop, usefulness, evidence validity and firewall omission detection. Physically capture reviewer provenance and candidate/report binding; no self-attested family.
- [ ] Resolve ordinary remands through admitted scope/budget; preserve findings and requalify affected claims. Final Court reproduces candidate-bound observations with discriminating negative controls.
- [ ] Produce final evidence inventory and exact status `PRE_SENTIUM_ECOSYSTEM_COMPLETE_PENDING_FOUNDER_RATIFICATION`. Stop. No automatic Founder ratification, external publication, Career or Sentium activation.
