# PAEOS-4.5 — Reference Implementation Derivation (v1.0)

Normative input: PAEOS-4 kernel spec v1.0-frozen (all § references below are PAEOS-4 clauses unless prefixed).
Rule of this document: **no element exists without a forcing clause.** Anything a reader cannot trace to a clause is a defect in this document (files as `Goal(kind=incident)` per PAEOS-4 closing clause).
Language-neutral: only contracts, boundaries, and order are derived.

**Global derivation obligations inherited by every module:**
- Traceability: every kernel clause MUST map to ≥1 conformance test, and every module to ≥1 clause ⟵ A6 (unenforced rules decay) + PAEOS-0 M3 (falsifiability). The matrix in §11.4 is itself a deliverable.
- Statelessness: no module may hold state not reconstructible from the store ⟵ D1 (crash-only). All indexes are caches.
- Purity: every function named "pure" in PAEOS-4 (compile §6.1, route §7.1, liveness §2.6, validation checks §4) MUST be implemented side-effect-free and fixture-testable ⟵ §6.1 byte-identical requirement.

---

## §1 Forced module inventory

Format per module: **forcing clause · why it exists · owned responsibilities · why not elsewhere · dependencies · validating tests · earliest bootstrap stage** (stages per PAEOS-3 S0–S5).

### 1.1 `constants`
- **Clause:** PAEOS-4 pinned constants (SHA-256, JCS/RFC 8785, ULID).
- **Why:** §6.1 and C1 demand byte-identical serialization across implementations; hashing/ID/serialization must be a single point of truth.
- **Owns:** canonical serialization, hash computation, ID generation. Nothing else — it is the compatibility floor.
- **Not elsewhere:** duplicating serialization in any module reintroduces divergence C1 exists to kill.
- **Deps:** none (graph root). **Tests:** C1, L0 golden bytes. **Stage:** S0.

### 1.2 `schema`
- **Clause:** §§2.2–2.7 (object schemas), §9.5 (schemas are kernel Policy artifacts pinned by hash).
- **Why:** typed store; untyped artifacts make every K-invariant unenforceable ⟵ F3.
- **Owns:** schema definitions as code AND their emission as store artifacts (dual form forced by §9.5: the *artifact* is authoritative, the code must be generated from or checked against it — one direction MUST be mechanical or they drift, A6).
- **Not elsewhere:** validator consumes schemas but must not define them (validation logic changes independently of object shape; §14.3 freezes shape harder than checks).
- **Deps:** constants. **Tests:** C1 round-trip; L0 fixture set (every object type, every kind, every REQUIRED/optional combination). **Stage:** S0.

### 1.3 `store`
- **Clause:** §2.1 (Objects + Refs, content-addressed, append-only), §11 READ/WRITE guarantees (atomic batch, monotonic snapshot), H4 (git is one adapter-level realization).
- **Why:** the single durable substrate ⟵ A2, K4.
- **Owns:** object put/get by hash, ref transactions (atomic batch = one commit), snapshots, reserved ref namespaces (`trunk/`, `head/`, `branch/spec/`), rebuildable reverse indexes (read-set index for liveness; id→head index).
- **Not elsewhere:** atomicity (§11 WRITE "no partial state") is only implementable at the ref-transaction layer; validator/liveness are *consumers* of snapshots, never co-owners of commit mechanics.
- **Deps:** constants. Backend: git in the reference implementation (satisfies all three §2.1 properties; per H4 the backend is swappable — the store interface, not git, is the contract).
- **Tests:** L0 (append-only: overwrite attempts fail; snapshot monotonicity), C5 (mid-write kill leaves store unchanged). **Stage:** S0.

### 1.4 `validator`
- **Clause:** §11 WRITE validation list (schema, mutation matrix §5.3, K1/K6/K10/K11, X1–X6); enforcement points named per-invariant in §4.
- **Why:** A6 — every invariant's "E:" line names the validator; without it the constitution is prose.
- **Owns:** the ordered check pipeline; one named pure predicate per check (`K1`,…,`K11`, `X1`…`X6`, `MUT` matrix, `SCH` schema, `D2` guard); check registry enumerable for the traceability matrix; error taxonomy of §11 (SCHEMA_VIOLATION, FORBIDDEN_CLASS, INVARIANT_VIOLATION(id), …).
- **Not elsewhere:** checks must run *inside* the WRITE transaction boundary (otherwise a window of invalid state exists, violating K4's audit value); but the check *logic* must not live in `store` because store is shape-agnostic (H4 backend swap must not carry invariant code).
- **Deps:** schema, store (read-only snapshot), budget. **Tests:** L1 — one positive + one negative test per registered check, enumerated mechanically from the registry (registry-driven coverage is what makes "every invariant has a test" checkable); C2, C8. **Stage:** S0 (first executable check ⟵ PAEOS-3 SVK item 3).

### 1.5 `liveness`
- **Clause:** §2.6 liveness function, K2 (read-set binding, transitive basis expiry), T1/T2 (regression, post-integration incident spawn).
- **Why:** evidence expiry is the kernel's load-bearing mechanism (F8 fix); it must fire mechanically on every ref update, not when remembered.
- **Owns:** `live(e)` computation; reverse read-set index maintenance (cache, rebuildable ⟵ D1); regression target computation (`max state whose entry conditions hold`); emission of regression/incident events to the reactor.
- **Not elsewhere:** cannot live in validator (validator judges proposed writes; liveness reacts to committed ref updates — different trigger, different transaction phase). Cannot live in adapters (kernel semantics, K9).
- **Deps:** store, schema. **Tests:** C3 (expiry cascade incl. transitive basis edges), L2 property tests (random ref update sequences: computed status always = max-valid). **Stage:** S1 (first needed when first evidence exists).

### 1.6 `reactor`
- **Clause:** §3.3 automatic transitions T1–T5 ("MUST auto-spawn", "MECHANICAL revert").
- **Why:** four transitions are specified as automatic; something must execute them with no agent in the loop (they are kernel behavior, not role behavior — no stance in §5.3 is permitted to perform them).
- **Owns:** subscription to store ref-transactions; executing T1 regression writes, T2/T5 incident auto-spawn, T3 mechanical policy revert, T4 amendment auto-finalization. Each reaction is itself a WRITE batch through the validator (reactor has no bypass — it is a client, not a superuser; forced by K4/K1 having no exception clause).
- **Not elsewhere:** liveness computes, reactor acts — split forced because computation is pure (§ purity obligation) and action mutates; merging them makes liveness untestable as a pure function.
- **Deps:** liveness, validator, store, syscalls(WRITE). **Tests:** C3 (T1), C7 (T3/T4), L2 (T5 exhaustion: blocked flag + incident). **Stage:** S2 (first automatic transition demand).

### 1.7 `budget`
- **Clause:** §10 (vector arithmetic, conservation K11, debit points §10.3, exhaustion §10.4).
- **Why:** F13 — conservation must be checked at three distinct points (child WRITE, EXEC debit, SPAWN lease); shared arithmetic prevents three divergent implementations.
- **Owns:** Budget vector ops; conservation predicate (used by validator's K11 check); lease/debit records.
- **Not elsewhere:** embedding in validator alone misses the syscall-time debits (§10.3 "at call time"); embedding in syscalls alone misses WRITE-time conservation. One library, two call sites.
- **Deps:** schema. **Tests:** C8, L2 property (no interleaving of debits violates conservation). **Stage:** S0 (root goal carries a budget from its first WRITE).

### 1.8 `compiler`
- **Clause:** §6 entire (resolution order, trigger evaluation, closure, deterministic truncation, manifest, caching).
- **Why:** K5 — sole legitimate source of agent context.
- **Owns:** the six-stage pure pipeline `resolve → close → order → truncate → render → manifest`; trigger predicate evaluation (§2.7 TriggerExpr); scope-conflict detection (§6.2 COMPILE_FAILURE + auto-incident); context cache keyed by `context_hash`.
- **Not elsewhere:** §6.1 byte-identical manifests across implementations ⟹ the pipeline is a conformance surface in itself; adapters receive `Context` and may only *lower* it (§12.1 "zero semantic addition") — any adapter-side selection logic would be a K5 violation.
- **Deps:** store, schema. **Tests:** L0 golden manifests (fixture store → expected manifest bytes, per stage); C6 (in vivo); truncation-record completeness property. **Stage:** S1 (precedes first agent ⟵ PAEOS-3 SVK item 5).

### 1.9 `router`
- **Clause:** §7.1 step 2 (`route()` pure function), §7.2 escalation spawns.
- **Why:** the ceremony decision must be reproducible from the DispatchRecord (§7.1 "MUST be reproducible").
- **Owns:** protocol cell lookup from classification evidence; DispatchRecord construction; child-budget stamping (via `budget`); escalation determination. Does NOT own classification (agent work, (S,GOALSTRUCT), §7.1 step 1) — the split is the clause.
- **Not elsewhere:** merging classify+route into code would delete the A-14 expiry mechanics (classification must be Evidence to expire); merging into reconciler couples policy selection to scheduling, which §15 explicitly excludes from kernel.
- **Deps:** store, schema, budget. **Tests:** L0 (every (v,r) cell → expected protocol fixture), L1 escalation triggers, C6. **Stage:** S2 (born when goal classes multiply ⟵ PAEOS-3 §4; first agent-built organ).

### 1.10 `syscalls`
- **Clause:** §11 entire; §14.2 (runtime ABI stability).
- **Why:** the narrow waist needs exactly one implementation of its semantics per kernel, with adapters plugging in beneath (K9).
- **Owns:** READ (snapshot discipline), WRITE (validate→commit→trigger liveness, error taxonomy), EXEC (sandbox delegation → signed evidence emission — the *only* author of execution-class Evidence ⟵ A-09), SPAWN (compile → branch isolation → adapter instantiation → ProposedWrites collection). Owns the Adapter SPI definition (§10 of this doc).
- **Not elsewhere:** if adapters implemented syscall *semantics* (not just backends), each runtime would re-derive validation/signing/isolation — precisely the divergence C2/C4 exist to catch.
- **Deps:** store, validator, liveness, compiler, budget, adapter-SPI. **Tests:** L3 contract suite (every error condition of §11 constructible), C2, C4, C5. **Stage:** S0 (READ/WRITE), S1 (EXEC/SPAWN).

### 1.11 `adapters/null`
- **Clause:** §12.5 (normative minimal implementation; MUST always remain conformant; disaster floor).
- **Owns:** model invocation via bare API, sandbox via OS subprocess limits, sequential SPAWN with branch isolation via `branch/spec/*` refs, signing key, capability vector declaring no concurrency/single model family (⟹ K3 mechanical-augmentation mode per §12.3).
- **Not elsewhere:** it is the portability proof (K9) — it must share zero code with the reference adapter beyond the SPI, or the proof is circular. **Hard boundary: null and reference adapters may share the kernel library and the SPI, nothing else.**
- **Deps:** adapter-SPI only. **Tests:** full C1–C8 (it is the second conformance runtime ⟵ §13.3). **Stage:** S3.

### 1.12 `adapters/claude-code` (reference)
- **Clause:** §12.6.
- **Owns:** SPI implementation exploiting native subagents (SPAWN acceleration), hooks (validator invocation on tool boundaries), context lowering to native instruction format with declared hashed preamble (§12.1).
- **Deps:** adapter-SPI. **Tests:** full C1–C8 + capability-vector accuracy. **Stage:** S1 (it is the genesis host runtime).

### 1.13 `conformance`
- **Clause:** §12.4 C1–C8; A6; PAEOS-0 M4 (portability CI).
- **Owns:** the five-layer hierarchy (§11 below), the traceability matrix, the reference goal (C6 fixture), the bootstrap-stage exit tests.
- **Not elsewhere:** fixtures are frozen artifacts of the spec — changing one is a spec amendment (§14.5 self-application), so they cannot live inside the modules they test.
- **Deps:** everything (test-only). **Stage:** S0 (C1 is the first exit evidence).

### 1.14 `genesis`
- **Clause:** §13 (record schema, trust roots, parameters, assumptions), PAEOS-3 S0 (recorded founding acts; installer scripts rejected — this module only *performs recorded WRITE batches*, it holds no state and no post-S0 role).
- **Owns:** emitting the S0 commit sequence (§12 below) from founder-supplied inputs.
- **Deps:** syscalls. **Tests:** L1 (genesis record schema; constitution passes its own admission rules — PAEOS-3 S0 exit). **Stage:** S0, then never again (single-shot by design; per PAEOS-3, re-running genesis on a non-empty store MUST fail).

### 1.15 `reconciler`
- **Clause:** forced by the reconciliation model itself (PAEOS-1 §0 via §3: unreconciled goals must be found and dispatched; PAEOS-3 S1 requires an executor for "first legitimate agent spawns"). Scheduling *policy* is explicitly excluded from kernel (§15) — therefore the reconciler ships with the naive genesis policy only (FIFO over dispatchable goals, conservation-constrained) and the policy is a `protocol`-kind parameter, not code ownership.
- **Owns:** the loop: find goals whose next transition has an unmet actor demand → ensure classification exists → route → SPAWN under lease → commit/discard ProposedWrites. Demand-paged role instantiation (PAEOS-3 §4) is this module reading protocol requirements — roles are Policy artifacts, not code.
- **Not elsewhere:** in syscalls it would smuggle policy into the frozen ABI; in adapters it would fork per-runtime behavior (K9).
- **Deps:** syscalls, router. **Tests:** C6 end-to-end; L2 (starvation: a dispatchable goal is eventually dispatched under naive policy). **Stage:** S1.

### 1.16 `cli` (founder ABI surface)
- **Clause:** §14.1 — the sanctioned founder write surface must exist as an operable interface; PAEOS-2 five verbs.
- **Owns:** exactly five commands mapping to the five verbs: `author` (root goal), `resolve` (decision), `inject` (external evidence), `curate` (taste artifact), `audit` (read-only reports: conservation walk, decision queue, intervention rate). Nothing else — a sixth verb would be an unsanctioned ABI extension (§14.1 "ONLY").
- **Deps:** syscalls. **Tests:** L3 (each verb produces exactly its §14.1 object class; `audit` performs zero writes). **Stage:** S0 (`author` needed for root goal), S2 (rest).

---

## §2 Repository structure

One repository = one store: forced, not chosen. §13.3 requires kernel artifacts to traverse the lifecycle *inside the governed store*; H4 lets git be simultaneously the store backend and the VCS; two repos would put the kernel's own code outside its governance, violating self-hosting from commit zero (PAEOS-3 §2).

```
paeos/
  spec/                     # PAEOS-0..4.5 — constitutional basis, hashed into genesis record (§13.1)
  kernel/                   # §1.1–1.10, 1.15: constants, schema, store, validator, liveness,
                            #   reactor, budget, compiler, router, syscalls, reconciler
  adapters/
    spi/                    # §10 — the boundary artifact (own package: shared by 1.11/1.12, owned by neither)
    null/                   # §1.11
    claude-code/            # §1.12
  conformance/
    fixtures/               # frozen golden objects/manifests (spec-owned, §1.13)
    l0..l5/                 # §11 hierarchy
  genesis/                  # §1.14 inputs: scar corpus import, parameters, trust roots
  cli/                      # §1.16
  store/                    # object namespace (objects by hash, JCS files); refs via git
```

## §3 Module dependency graph (acyclic; arrows = "depends on")

```
constants ← schema ← {store*, budget}
store ← constants
{validator, liveness, compiler, router} ← {schema, store}     # mutually independent, pure
validator ← budget
reactor ← {liveness, validator}
syscalls ← {store, validator, liveness, compiler, budget, adapter-spi}
reactor ← syscalls(WRITE)
{adapters/null, adapters/claude-code} ← adapter-spi            # and nothing else shared
{reconciler, cli, genesis} ← syscalls ; reconciler ← router
conformance ← all (test-only)
```
*store depends on constants only; schema listed for fixture typing of reserved refs.
Cycle check: reactor→syscalls→validator, and validator never calls reactor (judge vs act split, §1.6). No cycles.

## §4 Package ownership boundaries

| Package | Change authority | Forced by |
|---|---|---|
| `kernel/*` public surfaces (schemas, lattice, invariants, syscalls) | major-version amendment, full Trace-B + decision ceremony | §14.5 |
| `kernel/*` internals | ordinary amendment goals | §9.4 |
| `conformance/fixtures` | spec amendment (fixtures ARE the spec's executable form) | §1.13, A6 |
| `adapters/*` | workload-scoped goals; conformance is the gate | §12.4 |
| `adapters/spi` | same ceremony as syscalls (it is the other face of §14.2) | §14.2 |
| `genesis/` | write-once; post-S0 changes forbidden | §1.14 |
| scheduling policy, protocols, skills | Policy artifacts in the store, never code | §15 exclusions |

## §5 Runtime architecture

```
Processes (all stateless, all killable ⟵ D1):
  reconciler daemon  — the only long-running process; holds no state (loop re-derives from store)
  agent processes    — ephemeral, one per SPAWN, isolated on branch/spec/* (A-16)
  reactor            — event-driven on ref transactions (may be in-process with reconciler;
                       MUST NOT be in-process with agents — agents cannot hold kernel powers, §5.3)
  validator          — in-transaction library, not a process (must be inside WRITE, §1.4)
  cli                — founder-invoked, short-lived
Conformance C5 defines the process model's acceptance: kill anything, anytime, store converges.
```

## §6 Store architecture

Objects: JCS files keyed by hash under `store/`; WRITE batch = one git commit (atomicity §11); snapshot = commit id (monotonicity §11 READ). Refs: git refs under the three reserved namespaces (§2.1). Indexes (reverse read-set, id→head): derived caches, rebuild-from-scratch command mandatory and conformance-tested (D1 — a cache that can't be rebuilt is invisible state).

## §7 Validator architecture

Registry-driven pipeline: `[(check_id, clause, predicate)]`, executed in fixed order (SCH → MUT → X* → K*), fail-fast, error = `INVARIANT_VIOLATION(check_id)`. The registry is exported so §11.4's traceability matrix is *computed*, not maintained — a check without tests or a clause without a check fails CI mechanically (A6 applied to the implementation itself).

## §8 Compiler architecture

Six pure stages (§1.8), each independently golden-tested: `resolve` (§6.2 order) → `close` (links to DL, skill `requires` closure, acyclicity check) → `order` (slot, priority, id — total order §6.4) → `truncate` (reverse-resolution drop, never constitution/role, record all drops) → `render` (deterministic template) → `manifest` (+ context_hash). Cache is a pure memo on context_hash — eviction cannot affect correctness (D1).

## §9 Router & reconciler split

`route()` = pure lookup (§1.9); `reconciler` = the driver applying it (§1.15). The split is forced by §7.1's reproducibility clause: given a DispatchRecord, `route()` must be re-derivable offline; a router entangled with the live loop can't be.

## §10 Adapter SPI (the §12 contract as an interface)

```
invoke_model(rendered, params) → output           # SPAWN backend
sandbox_exec(cmd, input_refs, limits) → result    # EXEC backend (§12.1 sandbox_class)
sign(bytes) → signature                           # A-09; key registered in genesis record
capabilities() → CapabilityVector                 # §12.1; consumed by K3 mode selection (§12.3)
lower(Context) → native_form                      # §12.1 zero-semantic-addition; preamble hashed
```
Everything else in §12 (isolation, degradation, prohibitions) is enforced by the kernel-side syscall layer and verified by C1–C8 — adapters implement five functions, nothing more. That the SPI is this small is the K9 waist, restated at implementation level.

## §11 Conformance hierarchy

```
L0 unit        — pure functions vs golden fixtures (constants, schema, compiler stages, route cells)
L1 invariant   — validator registry: ≥1 positive + ≥1 negative per check (computed coverage)
L2 property    — randomized: lattice legality, liveness convergence, budget conservation,
                 reconciler non-starvation
L3 contract    — syscall error taxonomy; cli verb↔object-class mapping
L4 adapter     — C1–C8 per adapter (§12.4), identical suite for null and reference
L5 bootstrap   — S0–S4 exit criteria as executable tests (PAEOS-3 stage evidence),
                 culminating in the §13.3 self-hosting criterion as the final test
```
**§11.4 Traceability matrix:** generated artifact `clause × {module, tests}`; CI fails on any unmapped kernel clause. This is the implementation-level form of "no rule without enforcement" (A6).

## §12 Genesis commit sequence (S0, each = one recorded WRITE batch ⟵ PAEOS-3 §2)

```
G1: GenesisRecord (spec hashes, scar corpus refs, trust roots, parameters, assumptions)  §13.1
G2: schema Policy artifacts (objects thereafter pin them)                                 §9.5
G3: validator registered; first Evidence = validator run over G1–G2 (first check)  PAEOS-3 SVK-3
G4: Constitution policies K1–K11 (+D1/D2 as derived), each with scar + falsifier          K6
G5: role policies (Builder first; rest demand-paged), 4 genesis protocols, compiler
    registered as kernel function                                                  PAEOS-3 SVK-6,7
G6: root Goal "PAEOS is self-hosting" + founder-set Budget (the appetite)          §10.2, PAEOS-3 SVK-8
G7: founder-ABI refs (decision queue namespace, taste namespace)                   §14.1
Order is the PAEOS-3 §3 SVK order; G-numbers are its commit-level refinement.
```

## §13 Implementation order & parallelization

Serial spine (each step gated by its conformance evidence — the implementation plan is itself evidence-state-shaped, not calendar-shaped):

```
P0: constants + schema + store            → C1 passes
P1: budget + validator                     → C8; L1 registry green
P2: syscalls READ/WRITE                    → C2 (EXEC signing stubbed as null-adapter key)
P3: liveness + reactor                     → C3
P4: compiler                               → L0 golden manifests
P5: EXEC (sandbox + signing)               → C2 complete
P6: SPAWN + branch isolation + null adapter core → C4, C5
P7: router + reconciler + genesis module   → G1–G7 executable; C6 on null adapter
P8: amendment apply/revert (reactor T3/T4) → C7
P9: claude-code adapter                    → C1–C8 on reference; L5 through S3
```

**Parallel tracks** (independence forced by the dependency graph, §3): after P0 freezes fixtures, `validator`, `liveness`, `compiler`, `router`, `budget` are mutually independent pure modules over (schema, store-read) — five tracks, one per Builder, decorrelated by disjoint read-sets exactly as A-07/PAEOS-2 §6 prescribe for any decomposition. `conformance/fixtures` for L0–L4 derive from the spec alone and parallelize from day zero (contract-first). `adapters/null` and `adapters/claude-code` parallelize after the SPI freezes (P6/P9 overlap). The reconciler and cli are thin and serial-late.
This decomposition IS the child-goal set of G6's root goal — the implementation plan and the bootstrap goal tree are the same object, by construction.

## §14 Smallest executable vertical slice

Target: **C1** (first conformance evidence; S0 exit component).
Contents: `constants` (JCS + SHA-256 + ULID) + `schema` (object definitions + fixture set) + `store` (put/get + one ref transaction). Acceptance: every fixture object serializes → hashes → stores → reads → re-serializes byte-identically; an overwrite attempt fails.
Nothing smaller can produce conformance evidence (C1 is the minimal test); nothing else is needed to produce it (C1's clause touches only pinned constants + §2). This slice is also G1–G2's precondition — the first code and the first commits are the same event.

## §15 The exact self-hosting point of the implementation

Two distinct thresholds, per PAEOS-3:

1. **Implementation handoff (S1→S2 boundary): first C6 pass on the null adapter path (end of P7).** From that commit, every remaining item (P8, P9, refinements) MUST be registered as child goals of G6 and executed by agents under the kernel, with the founder reduced to the handoff rule (PAEOS-3 §2: fired function-by-function). Implementing P8+ by hand after C6 passes would be a clean-intent violation — the kernel that can host the work now exists.
2. **Constitutional self-hosting (S4): the §13.3 criterion — L5's final test** — a kernel-directed change traversing declared→integrated plus one incident→amendment→provisional cycle, founder on the five verbs only, C1–C8 green on both adapters. This is the ratification evidence; genesis authority expires here, and PAEOS-5 ends by definition.

---

*Every element above cites its forcing clause; the traceability matrix (§11.4) makes that claim mechanically checkable rather than rhetorical. Implementation may now proceed as a deterministic exercise: P0 through P7 by hand or by host-runtime agents under genesis authority, P8 onward by PAEOS itself.*
