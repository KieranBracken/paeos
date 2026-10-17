RE_DERIVE planning artifact prepared for goal g-d0cd25d2331e, run r-1bc742d8, task t-2078788d3bd1, role PLANNER, session planner.

Artifact: derive/first-principles.md
SHA-256: 51ba0650e7b7e543102d16b60ebd27d97f2fdc967657e3cea69905a9768fb947

The full artifact follows so its reasoning remains available after workspace capture. This response reports planning work only; it contains no test result, Court disposition, qualification, provider observation or lifecycle-advancement claim.

# First-principles derivation: bounded DEBT-0249 successor

Goal: g-d0cd25d2331e. Run: r-1bc742d8. Task: t-2078788d3bd1. Stage: RE_DERIVE. Role: PLANNER. Session: planner.

This artifact derives requirements from the emitted task and seeded source. It is planning work, not an implementation, test result, Court disposition, qualification, sealed-context observation, or authority to promote.

## Evidence and premises

The scoped context is spec/debt0249-successor-task.md, SHA-256 b09d02e111a74d2ac15291ed8739fbc60ecc7821907b919b6b0dd3291ac48a70. Its four embedded Python snapshots parse as Python and independently reproduce their declared SHA-256 values:

- kernel/promotion.py: 9abb08edd216d1798e09d5342d02afb94073a7248f4005854dfcf9d76a14e580
- runtime/ast_linter.py: fc167518cd747cd621cdc02bd9671aee675b9cc5c2baa7f68566590d1c383e8f
- runtime/critique.py: 1184886d6fa145324143a0d95f819de5c36f3a69fb4e54e0f57d6258df0c994f
- runtime/autonomy/promotion.py: 6a07a6ff9ad62e667b3750bc0dcb7344b26e8a781e3a920acffe7db933aa18d6

These pins identify the supplied snapshots; they do not establish the future Builder preimage or any external provider execution. Relevant seeded constraints are constitution/README.md (constitutional files immutable), constitution/canaries/CANARY-0002.json (evidence must discriminate the actual artifact from its negation), spec/PAEOS-7.6-runtime-interface-contracts.md sections 4, 6, 7 and 11 (authority, goal, evidence and validation; content addressing; artifact/environment binding), and spec/PAEOS-8.1-runtime-clarifications.md G-1 (operational stage metadata does not replace kernel state or authority).

The task is a new standalone successor. Historical missions, consumed attempts and qualification states are inputs to preserve, not operations to resume. The task asks for two specific repaired invariants and reproducible local tooling. It does not authorize a new candidate freeze or a qualification claim.

## The problem that must be solved

A helper that can reject bad input is ineffective when the operation that matters never invokes it. An address in CAS proves which bytes were stored; it does not prove those bytes describe the currently presented vote. Both defects are missing binding checks at a consequential boundary.

For DEF-0249-14-05, the supplied evaluate_promotion function hashes candidate files and examines prerequisite records but never invokes detect_mock_usage or verify_production_event_stream. PromotionController.promote invokes evaluate_promotion before its Git operations, making that real call chain the boundary to examine. The source contains an existing Trace-A-only automatic-promotion restriction. This successor's own ceremony classification does not authorize changing that restriction.

For DEF-0249-14-06, record_council_deliberation accepts a supplied dissent hash after checking only CAS existence. The verifier compares only voter_id and argument. Stance, risks and alternatives can diverge without that comparison detecting them. A decoded JSON value that is not an object escapes the comparison. The verifier never validates vote_cas_hash. The dissenting_opinions serialization omits risks and alternatives even though individual votes carry them.

## Necessary invariants

1. Promotion checks must inspect the exact non-test Python candidate bytes corresponding to the proposed candidate, and reject forbidden mocks, unreadable files or unparseable source. Test classification must be derived from repository-relative scope; a temporary ancestor directory or a production filename containing test_ cannot silently exempt production code. No scan of a different checkout or stale snapshot may stand in for the candidate.
2. Production-stream verification must be unavoidable in the actual promotion evaluation path and receive runtime-owned evidence for the relevant execution. Missing evidence must deny promotion. A PRODUCTION label, locally manufactured hash chain or success-shaped string alone is not proof of an authentic production execution. Existing chain, sequence, domain and lifecycle ordering checks must remain effective.
3. The event-stream evidence must support the current candidate/run claim. The next design must establish the available binding API rather than assume an iterable of rows establishes provenance. Success-looking stage names must not turn a failure event or unrelated execution into a successful prerequisite. The supplied helper accepts broad stage prefixes; this is a specific discrimination question to resolve from genuine runtime event contracts without editing protected emitters.
4. Every dissent must be represented consistently in votes, dissenting_opinions and CAS. The complete dissent payload must agree on voter identity, stance, argument, risks and alternatives; identity-bearing model-family data must not be silently discarded. Reject absent, malformed, wrong-shaped and inconsistent objects, including pre-supplied hashes whose contents belong to another dissent.
5. vote_cas_hash must resolve and bind the complete council record: vote/proposal identity, topic, votes, dissent, consensus state and the prohibition on substituting consensus for empirical evidence. Define canonical serialization once. The existing writer hashes a record with an empty vote_cas_hash and attaches the digest afterward; verification must honor a defined non-self-referential representation rather than attempt an impossible hash fixed point.
6. Valid records and valid promotion prerequisites need positive controls. A change that rejects everything fails the task. Existing bootstrap, protected-ref, capability, rollback, single-use and reconciliation guards remain active; this slice cannot weaken them to obtain a positive test.
7. Evidence must discriminate the new invariant in the real production functions. A negative already rejected for an unrelated missing bootstrap or malformed hash does not prove the repaired check. Record the exact intended denial and a minimally changed valid control. Local test records demonstrate verifier behavior only; they do not become real L14 identity or provenance evidence.

## Bounded verification obligations for later stages

Before implementation, observe RED at the actual evaluator/controller for a mock-bearing non-test candidate and missing or invalid production stream, while isolating other prerequisites. After the change, observe GREEN for clean input and rejection of one-variable corruptions: mock introduction, path-based test misclassification, missing event, reordered event, TEST domain, sequence gap and changed row bytes. Include a failure-event and unrelated-run case if the existing runtime contract provides the relevant identity and outcome fields. Check that a denied controller call produces no ref change or promotion-preparation/receipt effect. Do not replace the evaluator or Git runner with a successful stub to claim this result.

For Council binding, first demonstrate the current acceptance gap, then exercise unchanged valid round-trip, individual changes to stance/risks/alternatives, another dissent's CAS hash, non-object JSON, missing object, mismatched votes versus dissent entries, changed record identity/topic/consensus and changed or missing whole-record hash. Verify old legitimate serialization compatibility explicitly; unsupported historical records must have a clear disposition rather than being silently re-certified.

The later trusted verifier must capture actual commands, exit status and output for the targeted suites. This planner has executed no test or production operation and supplies no claimed RED/GREEN results. Mutation and negative controls must execute the changed code, as required by CANARY-0002.

## Scope and unresolved interface questions

The implementation allowlist is exactly kernel/promotion.py, runtime/ast_linter.py, runtime/critique.py, runtime/autonomy/promotion.py, scripts/build_debt0249_audit_package.py, scripts/requalify_subsystems_semantic.py, tests/runtime/test_executable_law_canaries.py, tests/runtime/test_debt0249_remand14.py and tests/runtime/autonomy/test_promotion_controller.py. Planning artifacts remain in the declared stage directories. This stage writes only derive/first-principles.md and the prescribed response.

Before Builder execution, the runtime must reconcile actual preimages and immutable scope overlap. The seeded material does not include the full protected manifest, package-builder source or semantic-tool source, so this planner does not claim an independent whole-manifest or tooling audit from these snapshots. Later stages must inspect those files within their own bound package. Tool outputs must use permitted disposable destinations and cannot overwrite the historical v14 package or emit a qualification claim. A tooling change that requires extra output paths needs scope resolution before use.

The design must answer how runtime-owned production rows and candidate/run binding reach the evaluator through the allowed promotion adapter. If that requires a protected orchestrator, Court, evidence, sandbox or router change, report the exact missing interface and stop that implementation path before Builder expansion. Do not fabricate observations or reinterpret synthetic test data as the missing producer. The same rule applies if old Council serialization cannot represent the required complete payload without an explicit compatibility policy.

Preserve P1_QUALIFIED, PRE_P2_AUTONOMY_QUALIFIED, P2_QUALIFIED and DEBT_0250_QUALIFIED; P3-P9 remain blocked and SENTIUM_FROZEN remains in force. AuthorityEnvelope enforcement, find-delete derivation, physical provenance/transcript enforcement and catalog-verified identity remain separate immutable residuals. This derivation neither repairs nor discharges them.
