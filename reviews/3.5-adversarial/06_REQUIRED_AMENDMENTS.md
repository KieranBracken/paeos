# 06 — Required Amendments

Each amendment is the smallest fix for a demonstrated defect. **BLOCKING** = must integrate before PAEOS-4 freezes schemas / before genesis; **DEFERRABLE** = may enter through the evolution loop after bootstrap. Ordering is by severity.

| # | Fixes | Amendment | Class | Status |
|---|---|---|---|---|
| A-06 | F7 (lattice contradiction) | **Probationary integration** for `goal.kind=amendment`: `executed → integrated-provisional → verified \| reverted`; integration arms the falsifier; refutation triggers mechanical revert | Architectural | **BLOCKING** |
| A-07 | F8 (livelock), 05-§2a | Evidence binds to the goal's **declared read-set** (justification graph), not trunk state; sibling read-set overlap becomes a decomposition **admission criterion**; Integrator may batch to bound invalidation rate | Architectural | **BLOCKING** |
| A-09 | F10 (forgeable evidence) | Execution-class Evidence is emitted **by the EXEC syscall** with adapter-signed provenance; validator rejects agent-authored execution claims | Architectural | **BLOCKING** |
| A-12 | F13, F16, 05-§2b | **Budget conservation law**: Σ(child budgets) ≤ parent − decomposition cost; root budgets founder-set; Evidence records production cost. (Full scheduling policy deferred to evolution) | Architectural | **BLOCKING** (law) / deferrable (scheduler) |
| A-02 | F2 (ontology collapse) | Incident, Decision, Amendment become **Goal subtypes** (`goal.kind`), preserving required fields; I7/I8 rebind unchanged | Schema | **BLOCKING** (pre-PAEOS-4) |
| A-03 | F3 (untyped work product) | **Artifact** base type (content-addressed + provenance); **Trunk** defined as integrator-owned ref | Schema | **BLOCKING** (pre-PAEOS-4) |
| A-17 | H10 (tenancy) | Policy **namespaces**: `scope ∈ {kernel, workload:<n>}`; promotion to kernel scope requires independent scars in ≥2 tenants | Schema | **BLOCKING** (field) / deferrable (promotion protocol) |
| A-08 | F9 (correlated verification) | **I3′**: non-mechanical verification must be provenance-decorrelated (different model family where adapter declares one; else mechanical augmentation, deficit recorded) | Architectural | **BLOCKING** |
| A-01 | F1 (kernel sentence) | Restate kernel: reconciled objects (Goal, Policy) vs immutable records (Artifact, Evidence) | Definitional | **BLOCKING** (one paragraph) |
| A-05 | F6 (Compiler judgment) | Compiler is deterministic over the **explicit link graph**; link-authoring is a Generate-stance duty; relevance discovery is a routable goal | Contract | **BLOCKING** |
| A-16 | H7 (SPAWN semantics) | SPAWN contract requires **speculation-branch isolation**; sequential emulation isolates via branches; conformance-tested | Contract | **BLOCKING** (in conformance spec) |
| A-18 | I7 unsafe in irreversible regime¹ | **Vicarious scars**: for irreversible-class hazards, imported/anticipated scars (external corpora, other tenants, near-misses) satisfy I7, with stricter falsifiers. Genesis already set the precedent (Sentium catalog) | Architectural | **BLOCKING** |
| A-10 | F11 (conflict rule) | Default-deny: live refuting evidence blocks promotion until superseded or expired | Small | DEFERRABLE (trivial; do at genesis) |
| A-11 | F12 (spec-gaming) | Decomposition audit gains **spec-sufficiency** check ("satisfy the spec while violating intent — if you can, spec fails") | Small | DEFERRABLE |
| A-13 | F14 (oscillation) | Pruning writes **tombstones**; re-admission requires evidence strictly exceeding the original scar | Small | DEFERRABLE |
| A-14 | F15 (quadrant drift) | Classification **is Evidence** — bound and expiring under I2; quadrant-relevant changes force re-route | Small (reuses I2) | DEFERRABLE (cheap; recommend genesis) |
| A-15 | H3 (unaudited root) | **Root-goal ceremony**: adversarial interrogation of every root Goal before decomposition | Small | DEFERRABLE |
| A-04 | F4 (role compression) | Role = **(stance, domain)** in kernel schema; seven names kept as bindings | Schema | DEFERRABLE (recommend pre-PAEOS-4) |
| A-19 | H1, H2, H5, H6 | Genesis-record additions: single-founder assumption; parchment clause (founder-sovereignty limit); NL-as-policy-encoding assumption with falsifier; I12's falsifier recorded | Documentation | **BLOCKING** (honesty items; one page) |

¹ F-numbering note: the I7-irreversible-regime defect was proven during invariant analysis: failure-driven derivation cannot protect against first-occurrence catastrophic failures (data loss, security breach) because the scar requirement demands the catastrophe happen once. The router's own logic (irreversible ⇒ pre-commitment) contradicts I7's learn-by-scar in exactly that quadrant. A-18 resolves it with the corpus's own precedent.

**Blocking set: 12 amendments. None removes a primitive by force; none reworks the skeleton; all reuse existing machinery or add one field/state/law.** The largest (A-07 justification graph) replaces the binding mechanism inside I2 without changing I2's meaning.
