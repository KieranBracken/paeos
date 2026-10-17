IDEATE planning artifact prepared for goal g-d0cd25d2331e, run r-1bc742d8, task t-fd84f3ea130a, role PLANNER, session planner.

Artifact: ideate/candidate-architectures.md
SHA-256: 8f0de17d5c5ea0feccbc6424ac048521d7e00a9268687d408be8160834d5a481

Full artifact follows. This reports bounded architecture comparison only, without implementation, approval, test-result, qualification or lifecycle-advancement claims.

# Candidate architectures for the bounded DEBT-0249 successor

Goal g-d0cd25d2331e; run r-1bc742d8; task t-fd84f3ea130a; stage IDEATE; role PLANNER; session planner.

This comparison is planning output. No implementation, test result, approval, qualification or lifecycle advancement is asserted.

## Grounding and decision criteria

The current scoped source is spec/debt0249-successor-task.md, SHA-256 b09d02e111a74d2ac15291ed8739fbc60ecc7821907b919b6b0dd3291ac48a70. All four embedded source hashes were rechecked. The materialized first-principles artifact, context/artifact-51ba0650e7b7.txt, matches SHA-256 51ba0650e7b7e543102d16b60ebd27d97f2fdc967657e3cea69905a9768fb947. Its requirements are preserved here.

Compare designs by unavoidable enforcement, authentic evidence binding, scope compatibility, backward compatibility, and discriminating verification. A convenient helper or a locally signed declaration is insufficient. The snapshots establish missing promotion checks and incomplete Council CAS comparison; they do not establish an available trusted production-stream producer.

## Candidate A: direct validation at the existing promotion boundary

Extend the existing evaluator and promotion adapter within kernel/promotion.py and runtime/autonomy/promotion.py. The evaluator inspects the exact candidate bytes and invokes runtime/ast_linter.py checks before the adapter can prepare or execute a ref update. A runtime-owned stream and its execution/candidate binding must reach this boundary through an existing lawful producer. Missing or inconsistent evidence yields an explicit denial.

This has the smallest enforcement surface: direct callers cannot bypass the checks by skipping a new optional wrapper. Candidate scanning should share the byte snapshot used for candidate hashing, classify tests using repository-relative paths, and deny read/parse failures. The detector's current substring exemption must not let a temporary directory or production filename masquerade as test scope.

Tradeoff: evaluating a complete stream costs more than checking a receipt, and the current signature does not expose the required runtime evidence. The downstream design must identify its real source. Passing arbitrary rows or a caller-set trusted flag is not a solution. Candidate A is viable only if the allowed adapter can obtain already-owned evidence without changing a protected producer. The existing Trace-A-only automatic-promotion restriction remains intact despite this repair task using a fuller ceremony.

## Candidate B: exact-content evidence bundle with mandatory revalidation

Use the existing CAS to reference a bundle containing the candidate digest and exact production evidence. The promotion adapter obtains the reference from the runtime, and the evaluator resolves it, recomputes content hashes and runs mandatory validation. Reuse existing storage and trust roots; introduce no independent authority store.

This makes replay and review easier and avoids repeatedly transporting large streams. It also exposes two costs: bundle schema/version compatibility and the need to bind the reference to a genuine run. CAS existence authenticates bytes, not their origin. A bundle assembled by the caller, or a receipt saying checks passed, cannot replace verification against an established runtime anchor. The seeded material does not demonstrate such an anchor. Candidate B therefore remains conditional and is less attractive than A unless existing production interfaces already provide the necessary content-addressed binding.

## Candidate C: wrapper-only or package-time validation

A new wrapper or audit-package script could run both helpers before calling the unchanged evaluator. It is easy to build and useful as diagnostic tooling, but direct evaluate_promotion or promote calls would still bypass it. A report can also become stale after candidate mutation. Reject this as the enforcement design. Retain package tooling only to reproduce observations and enumerate exact artifacts; it cannot grant promotion eligibility.

## Council design choices

A shared canonical serializer in runtime/critique.py is the preferred local candidate. Recording and verification use the same complete dissent representation and whole-record representation. Verification resolves CAS bytes, rejects malformed/non-object payloads and compares all required fields: voter identity, stance, argument, risks, alternatives, relevant model identity, and consistency between votes and dissenting_opinions. Whole-record binding additionally covers vote/proposal identity, topic, consensus state and the empirical-evidence prohibition.

Preserve the existing self-hash convention: serialize vote_cas_hash as the empty string, compute/store that payload, then attach the digest to the returned record. Verification normalizes the same field before comparison. Never require a digest to contain itself.

An alternative is independent field-by-field checks in both recording and verification. It minimizes serializer changes but duplicates the rule and invites omissions; the current bug is precisely an incomplete field comparison. Prefer a shared representation plus independent tests for every field. Historical payloads lacking fields need an explicit compatibility disposition. Do not silently invent missing values, rewrite historical objects or treat old records as newly qualified.

## Comparison outcome and next evidence

Advance A and B to research, with A provisionally favored for fewer trust and schema changes. Before selection, locate the actual producer and determine how immutable candidate/run identity binds its stream. If that requires protected orchestrator, Court, sandbox, router or evidence changes, record the precise dependency and remand before Builder expansion. A disconnected denial helper is not completion of DEF-0249-14-05.

For each viable design, require authentic RED at the real boundary, valid positive controls, and one-variable negatives for candidate mocks, test-path confusion, absent/TEST/tampered/reordered streams and individual Council-field changes. Verify denial causes no promotion effect. Local correctness fixtures are not external execution or L14 provenance evidence.

Keep implementation within the nine exact paths in the scoped specification and planning within declared stage directories. Tooling must support disposable outputs without touching the v14 package root or claiming qualification. Preserve all qualified baselines, P3-P9_BLOCKED and SENTIUM_FROZEN. AuthorityEnvelope, find-delete, physical transcript provenance and catalog-identity residuals remain outside this slice. No historical attempt is resumed or consumed operation reused.
