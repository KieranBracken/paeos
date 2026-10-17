# Concept OS CEO-1 Integration Spike

## Demonstrated path

Task 08 exercises the candidate-only ecosystem boundary. A WAL-backed `ConceptStore` is seeded
with Concepts and typed edges; `propose_analogies` creates a reified Analogy with an explicit known
break; `propose_recombinations` creates a two-source candidate Hypothesis with ordered
contribution edges; and both deterministic Search Orchestra arms (`traversal/v1` and
`seeded-random-walk/v1`) run with fixed seeds and budgets. The search result supplies graph and
algorithm snapshot metadata plus `why` paths. The Hypothesis is then read through the
`concept_hypothesis_get` read-only MCP tool, before `build_candidate_envelope` exports the exact
proposition, scope, assumptions, observations, falsifier, local Concept/Analogy references,
opaque SAKG reference, generator trace, and replay manifest. `emit_candidate` appends exactly one
`EMITTED` outbox observation; repeated emission is a byte-identical no-op.

The envelope ID is content-derived with `outbox_uri` and is a fixed 26-character Crockford Base32
`concept://demo/outbox/...` URI. Score vectors are explicitly serialized with `evidentiary: false`
and never contain `confidence`. Status is fixed to `candidate_proposal`, authority is exploratory,
and trust is `untrusted_candidate`.

## CEO-D1 through CEO-D10

| Decision | Evidence |
|---|---|
| CEO-D1 | Reads the durable Concept Graph; no second graph is maintained. |
| CEO-D2 | Uses only the existing pure SQLite WAL store and typed outbox API; no SQL is added. |
| CEO-D3 | Envelope and event identities use canonical content-derived outbox URIs. |
| CEO-D4 | Only append-only `EMITTED` observations are written; nodes are never changed. |
| CEO-D5 | Transformation references are provenance and are never loaded or invoked. |
| CEO-D6 | Existing reified analogy/recombination nodes and binary edges remain the representation. |
| CEO-D7 | The end-to-end test uses two deterministic Search Orchestra arms and complete replay data. |
| CEO-D8 | Scores are non-evidentiary vectors; no confidence/admission score is introduced. |
| CEO-D9 | The bridge stops at a pull-based PAEOS-mediated outbox and has no external authority imports or call sites. |
| CEO-D10 | MDL, wake/sleep, living concepts, and learned allocation remain deferred. |

## Fail-closed and poison containment

Missing scope, assumptions, observations, local provenance, SAKG references, or falsifiers are
rejected. `MissingFalsifierError` and `TruthBearingStatusForbiddenError` are typed boundary
errors. A high-novelty poisoned candidate remains a candidate proposal and cannot mutate the
stored Hypothesis lifecycle. A tampered truth-bearing status is rejected before an outbox row is
created.

## Boundary checks

The constitutional tests parse the bridge AST and reject imports from `runtime.integrations`,
`sakg.store`, and `sentium`; verify the public surface contains construction/emission only; and
verify there are no execution, broker, publication, or lifecycle-disposition call sites. The
focused Task 08 suites pass 13 tests in the retry sandbox. Ruff, Pyright, and
`runtime.ast_linter.check_ast()` are clean there. These are Builder evidence and do not constitute
a Court seal or truth disposition.
