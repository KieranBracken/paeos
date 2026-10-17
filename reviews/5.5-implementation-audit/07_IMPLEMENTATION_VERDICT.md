# 07 — Implementation Verdict

## VERDICT: GO — CONDITIONAL ON THE PATCH SET

Implementation can succeed and become mechanical, but **not from the corpus as frozen**.
The audit found 8 BLOCKING issues, 8 HIGH, 7 MEDIUM, 4 LOW (01_*), plus corrections to
PAEOS-4.5, PAEOS-5, and Wave 0 recorded below. Three findings touch frozen kernel
surfaces and require the K4 §14.5 amendment ceremony — the honest headline:

> **The kernel as frozen cannot be implemented without amending itself three times.**
> (B-01 status authority, B-02 provenance stamping, B-06 byte units — plus the EXEC
> signature change in 04.) Everything else is clarification-grade.

This is the expected result, not a failure: PAEOS-4's closing clause anticipated exactly
this ("any ambiguity discovered during implementation is a defect in this document"), and
the constitution's own amendment path is the remedy. The validation logic of this session
held: the spec was completable *because* trying to implement it exposed where it wasn't.

## Mandatory pre-Wave-1 patch set
1. **Kernel amendments (ceremony required):** B-01, B-02, B-06, EXEC-takes-Check (04).
2. **SC register extensions SC-13..SC-24:** B-03 meta-schema + atomic G1/G2 · B-04/05
   storage model (05_* is the text) · B-05 render grammar · B-07 Check schema · B-08
   selector DSL · H-01..H-08 pins · 03's four pins (store-root, lease, two-phase budget
   lease, fsync) · 06's pins (sandbox write-mask, A7 fixtures, key rotation).
3. **Threat-model preamble** stating residuals A10/A11/A15 (06).

## Corrections to prior documents (rule: no loyalty to consistency)
- **PAEOS-4.5 was wrong three times:** R §2 layout (superseded by 05_*), R §3 graph
  (store↛schema, router↛store — 02_*), R §12 genesis ordering (G1<G2 impossible — B-03).
- **PAEOS-5 backlog is missing four nodes:** `F-RENDER` (render-grammar goldens, Wave 1,
  fable) · `T-FAULT` (C5 kill-injection harness, Wave 3, sonnet) · `F-VAL` scope +A7/SIG
  fixture pairs · `F-SCHEMA` scope +6 schemas (H-04). Backlog edges: F-RENDER→I-COMP,
  T-FAULT→I-SYS-SPAWN acceptance.
- **Wave 0 packages:** F-SCHEMA package under-scoped (H-04 — must be reissued before
  assignment); F-SPI needs the `workdir` parameter (04); G-ROOT reminder for
  language/licensing constraints (L-04). G-CONST, G-CORPUS, G-ROLES survive unmodified.

## Investigation 9 — testing gaps (beyond backlog fixes above)
JCS differential fuzzer vs independent impl (L0) · compile() double-run determinism gate
in CI · validator-bypass architectural test (no WRITE path skips validation — lint the
call graph) · liveness convergence fuzzer (random ref sequences) · render goldens. All
sonnet-class once specified; fold into conformance/ ownership.

## Investigation 12 — performance
Two mandatory-index rulings (else O(n²) or worse): incremental liveness reverse index
(recompute-per-commit over all evidence is O(E) per write — index makes it O(touched)),
and the head map (READ by id otherwise scans objects/). Dependents index (H-08) is
O(E) to rebuild, amortized fine. compile() closure bounded by DL cap (already a genesis
parameter). Conservation check O(children) — fine. Git ref manifests shard at ~10⁴
objects (M-01). No true O(n²) remains after the two rulings.

## Investigation 13 — distributed future
Objects and git make replication trivial; the blockers are exactly two assumptions:
the global single-writer lease (H-01) and linear per-object version chains
(head + prev). Neither is constitutional — both are implementation pins. Consequence:
**federation by workload partition is achievable without kernel change** (tenancy
namespaces A-17 partition goals; each partition keeps single-writer); multi-master
writes to the *same* workload would require a ref-merge semantics amendment. Record as
a deliberate, documented deferral — the kernel does not preclude distribution.

## Investigation 14 — independent implementation test
Pre-patch: an independent team diverges at 11 identified points (storage mapping, render
text, token units, selector DSL, retry/timeout policies, timestamp source, meta-schema,
lease semantics, worktree model, EXEC environment, validator check order — the last was
already pinned). Post-patch: every divergence point has a pinned resolution with golden
or property tests; remaining freedom is genuinely semantic-free (language, process
layout). Conclusion: compatible-kernel goal is achievable **only after** the patch set —
which is the strongest justification for mandating it.

## Investigation 15 — re-derived implementation order
Independent re-derivation confirms the P0–P9 spine with three changes: (1) the storage
model (05_*) and meta-schema are now *part of P0* — they precede even I-CONST, since
fixtures embed hashes and paths; (2) F-RENDER joins Wave 1 before I-COMP; (3) I-STORE
parallelizes with F-SCHEMA (02_* store↛schema correction), slightly widening Wave 1.
Everything else stands. PAEOS-5's order was right in shape, incomplete in content.

## What this audit proves about the method
Every blocker found was a *contract gap*, not an architectural error: no primitive,
invariant, role, or loop needed redesign — they needed missing sentences. The
constitution's own instruments (SC register, incident conversion at G-RUN, §14.5
ceremony) absorb all of it. That is the difference between a specification that is
incomplete and one that is wrong, and it is why the verdict is GO rather than HALT.

**Gate:** Wave 1 MUST NOT dispatch until: the three kernel amendments are drafted and
founder-resolved, SC-13..SC-24 are appended, and the F-SCHEMA/F-SPI packages are
reissued. Estimated ceremony cost: one session. After that, implementation is —
finally, and now demonstrably — a deterministic engineering exercise.
