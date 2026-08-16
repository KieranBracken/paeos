# Worker Package: G-ROLES — Role Bodies + Genesis Protocols

## Purpose
Produce the four genesis role policies and four genesis protocol policies as schema-valid
`Policy` objects for genesis commit G5. Content is assembled from K4 §5/§7 — the mutation
matrix and protocol cells are already decided; this task renders them as loadable policy
bodies.

## Forcing kernel clause
K4 §5 (roles, mutation matrix) · K4 §7 (router/protocols) · K4 §2.7 (policy schema) · PAEOS-3 SVK-6/7.

## Dependencies
F-SCHEMA (policy shape). SC-06 (TriggerExpr), SC-11 (9→4 mapping).

## Owned files
```
genesis/roles/role-builder.json        # (GENERATE, WORK),      loading: at-spawn
genesis/roles/role-adversary.json      # (FALSIFY, WORK)
genesis/roles/role-judge.json          # (SELECT, WORK)
genesis/roles/role-classifier.json     # (SELECT, GOALSTRUCT)
genesis/protocols/proto-direct.json    # loading: routed
genesis/protocols/proto-checked.json
genesis/protocols/proto-adversarial.json
genesis/protocols/proto-escalate.json
```
All other roles are demand-paged post-genesis (PAEOS-3 §4) — creating them now is a
review-reject (no rule before its demand).

## File contents that must already exist
F-SCHEMA merged · K4 §5.3 mutation matrix · SPEC-CLARIFICATIONS.md.

## Interfaces
Role body sections (all four roles, same template): `stance_obligation` (one paragraph,
derived from the stance definition K4 §5.1) · `may_write` / `must_not_write` (transcribe
the §5.3 row VERBATIM) · `output_contract` (ProposedWrites composition for this stance) ·
`halt_conditions` (budget exhaustion; new-ambiguity HALT rule).

## Protocol cell mapping (BINDING — SC-11, 9 cells → 4 protocols)
```
(v=mechanical,  r=reversible)   → proto-direct      : 1 Builder; EXEC evidence; integrate
(v=mechanical,  r=guarded)      → proto-checked     : 1 Builder; EXEC evidence; +1 (F,WORK) pass
(v=mechanical,  r=irreversible) → proto-checked
(v=adversarial, r=reversible)   → proto-adversarial : 1 Builder + 1 Adversary; Judge if candidates>1
(v=adversarial, r=guarded)      → proto-adversarial
(v=adversarial, r=irreversible) → proto-escalate if no covering policy, else proto-adversarial + decision-gate
(v=external,    r=reversible)   → proto-adversarial + external evidence requirement
(v=external,    r=guarded)      → proto-escalate
(v=external,    r=irreversible) → proto-escalate    : spawn Goal(kind=decision) (K4 §7.2)
```
Protocol body fields: `cells: [(v,r)…]` · `roles: [(stance,domain)…]` · `fanout: 1`
(naive genesis default; N>1 arrives via evolution) · `evidence_reqs` template per
K4 §2.5 EvidenceReq (decorrelation: `mechanical` for proto-direct/checked,
`provenance-decorrelated` for proto-adversarial per K3) · `escalation: bool`.

## Invariants
Naive by construction: no protocol may contain refinement logic (retry strategies,
heuristics, quality bars) — refinement enters only via post-genesis amendment (PAEOS-3
§SVK-7). Mutation lists verbatim from §5.3. `scope: kernel` on all eight; scars: all
eight cite `scar:paeos-3.5/F4` (roles) / `scar:sentium/founder-bottleneck` (protocols)
per G-CONST/G-CORPUS tables; falsifier per policy: "this cell's ceremony level produces
zero defect catches / pure friction over window W".

## Acceptance tests
- Schema-valid vs F-SCHEMA · §5.3 rows verbatim (mechanical diff) · mapping table
  exhaustive: all 9 cells covered, each exactly once · fanout=1 everywhere ·
  compile-readiness: bodies contain no unresolved placeholders.

## Conformance tests validated downstream
C6 (reference goal runs under proto-direct with role-builder) · F-REFGOAL consumes these verbatim.

## Commit boundaries
2 commits: `genesis: role policies` · `genesis: protocol policies`.

## Expected outputs
8 files.

## Forbidden modifications
Extra roles/protocols · fanout>1 · any refinement content · rewording §5.3 rows · touching spec/fixtures.

## Review checklist
- [ ] Exactly 8 files; demand-paging respected
- [ ] Mutation matrix verbatim (diff against K4 §5.3)
- [ ] 9-cell mapping exhaustive and exclusive
- [ ] Naivety preserved (reject any cleverness)
- [ ] Scars/falsifiers per tables; loading fields correct
