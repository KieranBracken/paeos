# PAEOS-4 — Formal Kernel Specification (v1.0-frozen)

Status: FROZEN upon ratification amendment. Normative corpus: PAEOS-0..3 as amended by PAEOS-3.5 (amendments A-01..A-19 integrated; blocking set mandatory).
Derivation annotations: `⟵` cites the forcing source. Anything without a derivation citation does not belong in this document.
Keywords MUST / MUST NOT / MAY per RFC 2119.

**Pinned constants** (the only non-derived content; required for cross-implementation compatibility, semantically neutral):
`HASH = SHA-256` · `SERIAL = JCS (RFC 8785) canonical JSON` for structured objects, raw bytes for blob content · `ID = ULID`. Changing a pinned constant is a major-version kernel amendment.

---

## §1 Ontology

### 1.1 Categories ⟵ A-01

```
ReconciledObject := carries spec + status; mutates via appended versions
ImmutableRecord  := written once; never versioned; superseded, not edited
```

### 1.2 Primitives (final: 4) ⟵ A-02, A-03

| Primitive | Category | Survives because |
|---|---|---|
| **Artifact** | ImmutableRecord (base) | Work products exist in the store and are bound by Evidence (I2/K2); an unbound base type is unvalidatable ⟵ F3 |
| **Goal** | ReconciledObject | The only object that reconciles a desired delta; kinds absorb Incident/Decision/Amendment ⟵ F2 |
| **Evidence** | ImmutableRecord | Cannot be a Goal (records don't reconcile — F1); cannot be an Artifact field (liveness semantics are kernel behavior) |
| **Policy** | ReconciledObject | Cannot be a Goal (persists and loads; goals terminate); cannot be Artifact (scar/falsifier/firing are enforced fields — K6) |

### 1.3 Rejected primitives (re-verified post-amendment)

| Candidate | Still fails because |
|---|---|
| Task / Plan / Mission | Leaf Goal / Goal decomposition + aggregation / root Goal region. Two names, one object |
| Incident, Decision, Amendment | `goal.kind` subtypes; all Goal machinery (lattice, escalation, evidence-gating) applies unchanged ⟵ A-02 |
| Review / Report | Evidence of class `verdict` / Artifact |
| Agent | A process: (Role × Context) with no persistent identity; persisting it recreates invisible state ⟵ K4+K5 ⟹ D1 |
| Team / Workflow | Protocol-kind Policy content |
| Trunk | A **ref** (store concept, §2.1), not an object type ⟵ A-03 |
| Runtime / Adapter | Outside the kernel by K9; governed by contract (§12), not schema |
| Message / Channel | FORBIDDEN. All coordination passes through the store ⟵ A2, K4. Direct agent-to-agent channels create invisible state |

---

## §2 Store model and schemas

### 2.1 Store ⟵ A2, I4/K4, H4

```
Store := (Objects, Refs)
Objects : content-addressed set; key = HASH(SERIAL(object))
Refs    : named mutable pointers { name → object hash }
          reserved ref classes: trunk/<name> (integrator-owned, §5),
                                head/<object-id> (current version),
                                branch/spec/<goal-id>/<n> (speculation isolation, A-16)
Append-only: objects are never deleted or rewritten. Ref updates are the only mutation.
```
Git realizes this model at adapter level; the kernel requires only content-addressing, append-only objects, and refs. ⟵ H4

### 2.2 Common header (all kernel objects)

```
Header {
  id:       ID            REQUIRED  — stable identity
  type:     artifact|goal|evidence|policy  REQUIRED
  version:  uint          REQUIRED  — 1 for ImmutableRecords, monotonic for ReconciledObjects
  prev:     HASH?         REQUIRED for version>1; MUST be null for ImmutableRecords
  schema:   HASH          REQUIRED  — pins the schema version (schemas are Policy artifacts, §9.5)
  created:  RFC3339 UTC   REQUIRED
  author:   Provenance    REQUIRED
}
Identity: (id). Version identity: (id, version). Global identity: object hash.
Concurrency: WRITE with stale prev ⟹ IDENTITY_CONFLICT (optimistic; no locks) ⟵ D1
```

### 2.3 Provenance ⟵ A3, A-08, A-09

```
Provenance {
  actor:     founder | agent | syscall     REQUIRED
  role:      (stance, domain)?             REQUIRED iff actor=agent
  model:     string?                       REQUIRED iff actor=agent  — model family id
  adapter:   string?                       REQUIRED iff actor∈{agent,syscall}
  spawn:     HASH?                         — SpawnRecord that produced this actor
  signature: bytes?                        REQUIRED iff evidence class=execution (adapter key, §12.2)
}
```

### 2.4 Artifact

```
Artifact : Header + {
  media_type: string        REQUIRED
  content:    bytes | HASH  REQUIRED   — inline or blob ref
  links:      [HASH]        REQUIRED (may be empty) — explicit link graph ⟵ A-05
  workload:   WorkloadId?               — tenant tag ⟵ A-17
}
```

### 2.5 Goal

```
Goal : Header + {
  kind:            work | incident | decision | amendment   REQUIRED
  spec: {
    delta:         text            REQUIRED  — falsifiable desired change
    evidence_spec: [EvidenceReq]   REQUIRED, non-empty ⟵ I1; unreconcilable otherwise
    constraints:   [HASH]          REQUIRED (may be empty) — Policy/constraint artifact refs
  }
  parent:          GoalId?         — null ⟺ root goal
  serving_clause:  ClauseRef?      REQUIRED iff parent≠null ⟵ intent conservation, PAEOS-1 §4
  aggregation:     AggregationContract?  REQUIRED iff goal has children
  classification:  HASH?           — Evidence(class=classification) ref ⟵ A-14; REQUIRED before dispatch
  budget:          Budget          REQUIRED ⟵ A-12 (§10)
  status:          LatticeState    REQUIRED (§3)
  assignee_class:  agent | founder REQUIRED — MUST be founder iff kind=decision ⟵ A4
  workload:        WorkloadId?     — inherited from parent; null only for kernel-scoped goals
  payload:         (by kind, below)
  links:           [HASH]          — context links ⟵ A-05
}

payload(work)      := {}
payload(incident)  := { failure_ref: HASH REQUIRED, hazard_class: reversible|irreversible REQUIRED ⟵ A-18 }
payload(decision)  := { question: text, options: [{label, argument}], recommendation: label?,
                        resolution: {choice, rationale, terminal: amendment_ref | oneoff_record}? } ⟵ K7
payload(amendment) := { delta: PolicyDelta REQUIRED, falsifier_watch: EvidenceReq REQUIRED ⟵ A-06,
                        motivation: [HASH] REQUIRED — incident/tournament evidence ⟵ I7 }

EvidenceReq {
  claim:         text template            REQUIRED
  class:         execution | verdict | external | classification   REQUIRED
  decorrelation: mechanical | provenance-decorrelated | none        REQUIRED ⟵ A-08
  min_count:     uint = 1
}

AggregationContract { rule: all-children-verified | quorum(n) | weighted([...]) ; composition: text }
Cardinality: Goal 0..1 parent, 0..n children; child.workload MUST = parent.workload.
```

### 2.6 Evidence ⟵ A-07, A-09, A-14

```
Evidence : Header(version=1) + {
  goal:      GoalId          REQUIRED  — the claim's subject
  claim:     text            REQUIRED
  polarity:  supports | refutes         REQUIRED
  class:     execution | verdict | external | classification   REQUIRED
  observation: { command?, output_hash?, verdict_text?, source? }  REQUIRED
  read_set:  [(ObjectId|RefName, HASH)] REQUIRED  — what was observed, at which version ⟵ A-07
  basis:     [HASH]          REQUIRED (may be empty) — evidence this evidence depends on (justification edges)
  cost:      Budget          REQUIRED ⟵ A-12
}
Constraints:
  class=execution  ⟹ author.actor=syscall ∧ signature present   ⟵ A-09 (validator-rejected otherwise)
  class=external   ⟹ author.actor=founder
  class=verdict    ⟹ author.actor=agent ∧ author.role.stance ∈ {FALSIFY, SELECT}  (§5.3)
Liveness (computed, never stored):
  live(e) ⟺ ∀(o,h) ∈ read_set: head(o)=h  ∧  ∀b ∈ basis: live(b)
  Expiry is transitive along basis edges (justification graph invalidation) ⟵ A-07, 05-§2a
```

### 2.7 Policy ⟵ A-13, A-17, A-18

```
Policy : Header + {
  kind:      constitution | protocol | skill | role    REQUIRED
  scope:     kernel | workload:<id>                    REQUIRED ⟵ A-17
  scar:      [HASH]   REQUIRED, non-empty — incident refs or ExternalScar ⟵ I7/K6
  scar_class: incurred | vicarious                     REQUIRED ⟵ A-18
             (vicarious permitted only for hazard_class=irreversible, with strict falsifier)
  falsifier: { statement: text, watch: EvidenceReq }   REQUIRED
  firing:    [ { at, goal, effect } ]                  REQUIRED (append-only)
  tombstone: HASH?  — set by pruning amendment ⟵ A-13
  loading:   always | routed | triggered | at-spawn    REQUIRED; MUST match kind
             (constitution→always, protocol→routed, skill→triggered, role→at-spawn)
  body:      text | structured
  trigger:   TriggerExpr?   REQUIRED iff kind=skill — pure predicate over
             (goal.kind, classification, artifact media_types in link closure, role)
  requires:  [PolicyId]     — skill DAG; MUST be acyclic
  priority:  int = 0        — deterministic truncation order (§6.4)
}
Mutation: Policy versions are appended ONLY as the effect of an integrated amendment-kind Goal (§3.4, §9.4).
```

---

## §3 Lattice

### 3.1 States

```
S = { declared, speculated, executed, provisional, verified, integrated,
      failed, abandoned, reverted }
Terminal: integrated, failed, abandoned, reverted
provisional, reverted: legal ONLY for kind=amendment ⟵ A-06
```

### 3.2 Entry conditions (promotion = entering a state whose conditions hold; skipping intermediate states is legal when a later state's conditions are already met)

```
declared     : schema-valid Goal exists
speculated   : ≥1 candidate Artifact linked, on an isolated speculation branch (A-16)
executed     : live Evidence(class=execution, supports) for the candidate exists
verified     : goal.spec.evidence_spec fully satisfied by LIVE evidence
               ∧ decorrelation requirements met (K3)
               ∧ no live refuting evidence on the goal (K1 default-deny, A-10)
provisional  : kind=amendment ∧ executed ∧ delta applied to Policy store
               ∧ falsifier_watch ARMED           ⟵ A-06
integrated   : verified ∧ merged to trunk ref by Integrator (K8)
               ∧ parent aggregation input recorded
               (kind=amendment: auto-transition from verified; delta already live since provisional)
failed       : evidence_spec unsatisfiable (proven) ∨ attempts exhausted per protocol
abandoned    : parent withdrawn ∨ founder withdrawal (recorded)
reverted     : kind=amendment ∧ falsifier_watch produced live refuting evidence
               ⟹ MECHANICAL revert of delta      ⟵ A-06
```

### 3.3 Automatic transitions

```
T1 REGRESSION   : any expiry of evidence supporting state s ⟹ status := max state whose
                  entry conditions still hold. Floor: integrated.        ⟵ I2/K2
T2 POST-INTEGRATION EXPIRY : expiry of an integrated goal's evidence does NOT regress it
                  (merges are history); it MUST auto-spawn Goal(kind=incident).  ⟵ F15 analysis
T3 REVERT       : provisional + live refuting falsifier evidence ⟹ reverted, delta unapplied.
T4 AMEND-FINAL  : amendment verified ⟹ integrated (no integrator action; delta live).
T5 BUDGET       : budget exhausted ⟹ no state change; goal flagged blocked (computed),
                  auto-spawn Goal(kind=incident).                        ⟵ A-12
```

### 3.4 Forbidden transitions (validator-enforced)

```
X1: any promotion without the entry condition's live evidence (K1)
X2: → integrated except from verified (or T4)
X3: any transition out of a terminal state
X4: → provisional for kind ≠ amendment
X5: kind=amendment → integrated without passing provisional (no un-probated policy)
X6: status changes authored by GENERATE-stance actors on their own goal's verification states
```

---

## §4 Invariants (final set: K1–K11 axioms, D1–D2 derived)

Format — S: statement · D: derivation · E: enforcement point · F: failure mode prevented.

```
K1 EVIDENCE-GATED PROMOTION
   S: A goal enters a state only if that state's entry conditions are satisfied by live
      evidence; live refuting evidence blocks promotion (default-deny).
   D: A1 (verification scarce ⟹ its output is the only currency) + A-10.
   E: Validator on WRITE of any Goal version changing status.
   F: Assertion-based progress; promotion past standing refutation.

K2 READ-SET BINDING & TRANSITIVE EXPIRY
   S: Evidence declares its read-set; it is live iff every read-set entry is at head and
      every basis edge is live. Regression per T1/T2.
   D: A2 + F8/A-07 (hash-of-trunk binding proven unstable; justification graph forced).
   E: Kernel liveness function; recomputed on every ref update.
   F: Stale truth; the I2×I9 rebase treadmill (λp ≥ μ livelock).

K3 DECORRELATED VERIFICATION
   S: Where evidence_spec.decorrelation = provenance-decorrelated, verifying evidence MUST
      differ from generating provenance in model family, or be mechanically augmented with
      the deficit recorded on the Evidence.
   D: A3 + F9 (same-model different-stance is the theater PAEOS-0 names).
   E: Validator (provenance comparison at promotion) + adapter capability declaration (§12).
   F: Correlated blind-spot verification in exactly the quadrants lacking mechanical checks.

K4 APPEND-ONLY STORE
   S: Objects are immutable; state change is a new version; refs are the only mutation.
   D: A2 + auditability of the founding (PAEOS-3 §1).
   E: Syscall layer (WRITE cannot overwrite; no DELETE exists).
   F: Invisible state; unauditable history.

K5 COMPILED CONTEXTS OVER EXPLICIT LINKS
   S: Agents act only on Contexts produced by the kernel compile() function (§6), which is
      deterministic over the explicit link graph. No hand-authored, unversioned instruction
      may reach an agent.
   D: A6 + I6 + A-05 (a judging compiler is an ungoverned eighth intelligence).
   E: SPAWN (sole path to agent instantiation); context manifest audit.
   F: Unreproducible behavior; hidden steering.

K6 SCAR + FALSIFIER + FIRING + TOMBSTONE
   S: Every Policy carries non-empty scar (vicarious only for irreversible hazards), a
      falsifier, and an append-only firing record. Pruned policies leave tombstones;
      re-admission requires evidence strictly exceeding the original scar.
   D: PAEOS-0 M2/M3 + A-13 (oscillation) + A-18 (first-occurrence catastrophe).
   E: Validator on Policy WRITE; Steward pruning audits.
   F: Cargo-cult accretion; prune/re-admit oscillation; learn-by-dying in the
      irreversible regime.

K7 FOUNDER GOALS TERMINATE IN POLICY
   S: A decision-kind goal reaches a terminal state only with resolution.terminal set:
      an amendment ref or an explicit one-off record.
   D: A4 + PAEOS-2 §5 (interventions must close their class; decay theorem depends on it).
   E: Validator on decision-goal terminal transition.
   F: Non-decaying founder load; unrecorded judgment.

K8 SINGLE INTEGRATOR PER TRUNK REF
   S: Each trunk/<name> ref accepts updates from exactly one Integrator process at a time.
   D: PAEOS-0 P4 (coherence fragments under parallelism).
   E: Syscall layer (ref-update lease).
   F: Architectural incoherence at merge.

K9 NARROW WAIST
   S: The kernel assumes exactly the syscalls of §11. Kernel objects and behavior MUST NOT
      reference runtime-specific capabilities.
   D: A5 + PAEOS-1 §6.
   E: Conformance suite (§12.4), incl. null-adapter run.
   F: Runtime lock-in; portability decay.

K10 KERNEL SIZE CAP
   S: constitution-kind Policy total ≤ CAP tokens (genesis parameter). Additions displace
      or fail validation.
   D: PAEOS-0 M5 (context tax). Falsifier recorded per H6: collapses if context becomes free.
   E: Validator on constitution-kind WRITE.
   F: Constitutional bloat taxing every compiled context.

K11 BUDGET CONSERVATION
   S: Σ(children.budget.allocated) ≤ parent.budget.allocated − parent.budget.spent_direct,
      per dimension. Root budgets are founder-set.
   D: A1 + F13 (decomposition must not mint resources).
   E: Validator on child-goal WRITE; SPAWN/EXEC debit checks.
   F: Unbounded goal explosion; the money-printer Decomposer.

D1 CRASH-ONLY AGENTS (theorem)
   S: Any agent killed at any point loses nothing.
   D: K4 (all state in store) + K5 (context recompilable deterministically) ⟹ successor
      recompiles and continues. No independent enforcement needed; conformance tests it.

D2 CONSTRAINT MONOTONICITY (theorem, named check retained)
   S: Children tighten inherited constraints; loosening requires a decision-kind goal.
   D: Loosening reverses a founder commitment = A4 channel 4 = decision-kind by definition + K7.
   E: Validator check retained (cheap; guards the theorem's premise).
```

---

## §5 Roles

### 5.1 Definition ⟵ A-04 / F4

```
Role := (stance, domain)
stance ∈ { GENERATE, FALSIFY, SELECT }
domain ∈ { WORK, GOALSTRUCT, POLICY, TRUNK }
```

Conventional bindings: Builder=(G,WORK) · Decomposer=(G,GOALSTRUCT) · Steward=(G,POLICY) · Integrator=(G,TRUNK) · Adversary=(F,WORK) · Judge=(S,WORK) · Router=(S,GOALSTRUCT). FALSIFY and SELECT over other domains are first-class cells (decomposition audit=(F,GOALSTRUCT), pruning audit=(F,POLICY), conformance run=(F,TRUNK), amendment tournament=(S,POLICY), integration ordering=(S,TRUNK)).

### 5.2 Interface (uniform)

```
spawn-in : Context (compiled, §6) + budget lease
run      : within isolated speculation branch (A-16)
return   : ProposedWrites [objects] + SpawnRecord — committed atomically via WRITE or discarded
terminate: on return, budget exhaustion, or kill (D1: both safe)
Spawn condition (demand paging, PAEOS-3 §4): a (stance,domain) is instantiated only when a
protocol step or kernel invariant requires that cell for a live goal.
```

### 5.3 Mutation matrix (validator-enforced)

| stance | MAY write | MUST NOT write |
|---|---|---|
| GENERATE | Artifacts; child Goals (GOALSTRUCT); amendment-payload drafts (POLICY); trunk ref updates (TRUNK, under K8 lease) | **Any Evidence** (execution evidence comes only from EXEC ⟵ A-09; self-testimony is not evidence ⟵ X6) |
| FALSIFY | Evidence(class=verdict); Goal(kind=incident) | Artifacts on the goal under test; status promotions |
| SELECT | Evidence(class=verdict, selection); Evidence(class=classification) (Router); DispatchRecords | Artifacts; Policy |
| founder (external, not a role) | root Goals; decision resolutions; Evidence(class=external); taste Artifacts | everything else — direct work-product edits are auto-Incidents (clean-intent; parchment clause acknowledged §13.2) |

---

## §6 Compiler

```
compile(goal: HASH, role: Role, snapshot: StoreView) → Context
```

### 6.1 Determinism ⟵ K5, A-05
Pure function of its three arguments. Two conformant implementations MUST produce byte-identical `Context.manifest` for identical inputs.

### 6.2 Inputs (resolution order)
```
1. Constitution : all Policy(kind=constitution) where scope ∈ {kernel, goal.workload}
2. Role         : Policy(kind=role) for (stance,domain)
3. Protocol     : per goal's DispatchRecord (§7)
4. Skills       : { s : kind=skill ∧ scope ∈ {kernel, goal.workload} ∧ tombstone=null
                    ∧ trigger(s)(goal, classification, link-media-types, role) = true }
                  ∪ transitive closure of requires (acyclic, K-checked)
5. Goal         : the goal version + parent chain spec clauses (serving-clause context)
6. Links        : closure over goal.links ∪ artifact.links to depth DL (genesis parameter)
7. Evidence     : live evidence for the goal + live refutations (always included, A-10)
```
Scope conflict: workload-scoped policy MAY tighten, MUST NOT contradict kernel scope (D2 analog); contradiction ⟹ COMPILE_FAILURE + auto-incident.

### 6.3 Output
```
Context {
  manifest: [ (slot, object_id, version, HASH) ]   — total, ordered, hashable
  rendered: text                                    — deterministic template over manifest
  truncation: [ (HASH, reason) ]                    — REQUIRED record of anything dropped
}
context_hash = HASH(SERIAL(manifest))
```

### 6.4 Token budget & truncation
Deterministic: drop order = reverse of resolution order (evidence bodies → link bodies → skill bodies …); within a slot, ascending `priority`, then descending id. Constitution and Role are never truncated (K10 guarantees they fit). All drops recorded in `truncation`.

### 6.5 Caching & pinning
`context_hash` keys the cache; manifest pins exact policy versions ⟹ every outcome is attributable to the policy versions that produced it (tournament-between-versions enabled ⟵ PAEOS-2 §5-skills).

---

## §7 Router

### 7.1 Two-step contract ⟵ A-14
Classification is agent work producing Evidence; routing is a pure function consuming it.

```
Step 1 (SELECT,GOALSTRUCT): classify(goal) → Evidence {
  class: classification
  observation: { v: mechanical | adversarial | external ,
                 r: reversible | guarded | irreversible }
  read_set: [ check-inventory head, dependents-set head, goal version ]   ⟵ A-14
}
v: can evidence_spec be satisfied by existing checks (mechanical), by stance testimony
   (adversarial), or only by world contact (external)?
r: revert cost vs consequence horizon; anything with post-integration dependents trends
   irreversible (Hyrum ⟵ F15).
Expiry of this evidence (new checks, new dependents) ⟹ re-classification forced.

Step 2 (kernel function):
route(goal, classification, policies) → DispatchRecord {
  protocol: PolicyRef            — Policy(kind=protocol) matching (v,r) cell
  fanout: N                      — from protocol; tournaments only where selection cheap
  evidence_reqs: [EvidenceReq]   — protocol template ⊕ goal.spec
  child_budget: Budget           — per §10.3
  escalate: bool
}
Deterministic given inputs. MUST be reproducible from the DispatchRecord.
```

### 7.2 Escalation rules ⟵ A4, PAEOS-2 §5
```
escalate ⟹ spawn Goal(kind=decision) iff:
  (r=irreversible ∧ v=external ∧ no covering Policy) ∨ constraint loosening (D2)
  ∨ classification unachievable (novel/unclassifiable) ∨ taste starvation (Judge-declared)
Root goals: MUST pass root-goal ceremony (adversarial interrogation, (F,GOALSTRUCT))
before first decomposition ⟵ A-15.
```

---

## §8 Evidence semantics (truth model)

```
believed(claim) ⟺ ∃ satisfying live evidence per EvidenceReq (count, class, decorrelation)
                  ∧ ¬∃ live Evidence(polarity=refutes) on the claim        ⟵ K1, A-10
Authority order (descending): external (founder ground truth) > execution (signed) >
verdict (stance testimony) > classification.
Conflict at equal authority: default-deny (refutation wins) until superseded or expired.
```

- **Read-set binding**: §2.6; granularity = whatever object the observer actually consulted — fine-grained by construction, not by parameter ⟵ A-07.
- **Execution signatures**: EXEC-emitted only, adapter-signed; validator rejects otherwise ⟵ A-09.
- **Adapter trust model**: agents untrusted; adapters trusted-but-conformance-verified (keys registered in genesis record §13); founder sovereign — enforcement against the founder is detection + convention only (parchment clause ⟵ H2).
- **Expiry**: transitive along basis edges; recomputation triggered by ref updates touching any read-set member.

---

## §9 Policy system

```
9.1 Namespaces: scope ∈ {kernel, workload:<id>} ⟵ A-17. Workload policies tighten only.
9.2 Promotion: workload→kernel requires an amendment goal citing independently incurred
    scars in ≥ 2 distinct workloads ⟵ A-17.
9.3 Skills: loading=triggered; trigger is a pure predicate (§2.7); composition via acyclic
    requires; born only from amendment goals citing incident scars (or vicarious per A-18);
    versions pinned in every context manifest.
9.4 Amendment lifecycle = amendment-kind Goal lattice:
    declared → speculated (delta drafted) → executed (delta validated against schemas)
    → provisional (delta APPLIED, falsifier ARMED) → verified (falsifier_watch satisfied
    in operation) → integrated (T4)  |  reverted (T3, mechanical un-apply)      ⟵ A-06
5. Pruning: firing quiet for window W ⟹ Steward MUST spawn pruning amendment; effect:
    tombstone set (policy no longer loads). Re-admission requires strictly-exceeding
    evidence ⟵ A-13.
9.5 Schemas are kernel-scoped Policy artifacts; objects pin schema by hash (§2.2) —
    schema evolution rides the amendment lifecycle like everything else.
```

---

## §10 Budget model ⟵ A-12, F13, F16

```
Budget {
  dimensions: { tokens: uint, exec_seconds: uint, verification_passes: uint,
                decisions: uint, wall_clock_s: uint }     — founder attention is a priced
                                                            dimension (A4: scarcest)
  allocated: Vec, spent_direct: Vec, delegated: Vec       — per dimension
}
10.1 Conservation (K11): delegated ≤ allocated − spent_direct, per dimension, at all times.
10.2 Roots: allocated set by founder at root-goal authoring (the appetite; estimation is
     replaced by this bound ⟵ PAEOS-2 §1).
10.3 Propagation: DispatchRecord.child_budget debits parent.delegated atomically at child
     WRITE; EXEC/SPAWN debit spent_direct at call time; Evidence.cost records actuals.
10.4 Exhaustion: syscalls fail with BUDGET_EXCEEDED; T5 fires (blocked flag + auto-incident).
     No silent overrun; no state regression.
10.5 Verification economics: verification_passes is the fan-out limiter (tournament N MUST
     satisfy N ≤ remaining verification_passes) ⟵ PAEOS-2 §4.
     Scheduling policy beyond conservation: EXCLUDED from kernel; evolution-layer (§15).
```

---

## §11 Syscalls ⟵ K9

```
READ(selector: {id | hash | ref | type+filter}, snapshot?) → [ObjectVersion]
  Guarantees: immutable results; monotonic snapshot within one process lifetime.
  Errors: NOT_FOUND.

WRITE(objects: [Object], expect: [(id, prev_hash)]) → [HASH]
  Atomic batch: all-or-nothing (commit = single ref transaction).
  Validation: schema, mutation matrix (§5.3), invariants K1/K6/K10/K11, X1–X6.
  Errors: SCHEMA_VIOLATION, IDENTITY_CONFLICT, FORBIDDEN_CLASS, INVARIANT_VIOLATION(Kn|Xn),
          BUDGET_EXCEEDED.
  Guarantee: no partial state ever visible (D1).

EXEC(command, input_refs: [HASH], budget_lease) → (output: Artifact, evidence: HASH)
  Runs in adapter sandbox; auto-captures read_set = input_refs + declared environment hash;
  EMITS Evidence(class=execution) signed by the adapter ⟵ A-09. Agents receive the ref,
  never author the record.
  Errors: BUDGET_EXCEEDED, SANDBOX_VIOLATION, NONZERO_EXIT (still emits evidence,
          polarity=refutes — failure is evidence too).

SPAWN(role: Role, goal: HASH, budget_lease) → SpawnHandle → ProposedWrites
  1. context := compile(goal, role, snapshot)            (kernel compiler, K5)
  2. instantiate on an isolated speculation branch; sibling speculations MUST be mutually
     unreadable ⟵ A-16 (sequential emulation MUST branch-isolate; violation = conformance
     failure, not degradation)
  3. return deltas as ProposedWrites; caller commits via WRITE or discards.
  Reducibility: SPAWN ≡ EXEC(null-adapter, context) — retained as the one optimization
  point; proof of waist minimality ⟵ 04-audit.
  Errors: COMPILE_FAILURE, BUDGET_EXCEEDED, ISOLATION_UNAVAILABLE.
```

---

## §12 Adapter contract

```
12.1 MUST: implement §11 exactly; register signing key in genesis record; declare
     CapabilityVector { model_families: [..], concurrent_spawn: bool, sandbox_class,
     max_context_tokens }; lower Context.rendered to native format with ZERO semantic
     addition beyond a declared, hashed adapter preamble.
12.2 MUST NOT: mutate the store outside WRITE; author or alter Evidence; inject
     unregistered instructions; suppress refuting evidence; share state between
     speculation branches.
12.3 Degradation: absent concurrency ⟹ sequential SPAWN with branch isolation (A-16);
     absent second model family ⟹ K3 mechanical-augmentation mode, deficit recorded (A-08/H8).
12.4 Conformance suite (all MUST pass):
     C1 schema round-trip (byte-identical re-serialization)
     C2 forge rejection (agent-authored execution evidence rejected)
     C3 expiry cascade (ref update ⟹ transitive regression fires)
     C4 isolation (sequential tournament candidates provably unread by siblings)
     C5 crash-kill (kill mid-SPAWN at random point; successor converges; store unchanged)
     C6 reference goal reaches verified end-to-end
     C7 amendment cycle (incident → amendment → provisional → verified/reverted)
     C8 budget conservation (over-delegation rejected)
12.5 Null adapter: normative minimal implementation (shell + model API, sequential SPAWN,
     branch isolation via refs). MUST always remain conformant: it is the portability
     proof and the disaster floor ⟵ PAEOS-3 §5.
12.6 Reference adapter: Claude Code; MAY exploit native subagents/hooks as SPAWN/validator
     accelerations; conformance identical.
```

---

## §13 Genesis

```
13.1 GenesisRecord (first object in any PAEOS store; ImmutableRecord):
  { authority: { founder_id, host_runtime },
    constitutional_basis: [HASH]           — PAEOS-0..3.5 corpus hashes
    scar_corpus: [HASH]                    — imported incident catalog (Sentium)
    adapter_trust_roots: [ (adapter_id, pubkey) ]
    parameters: { CAP, W, DL, N_defaults, thresholds }   — each marked AMENDABLE
    assumptions: [ single-founder (H1), parchment clause (H2), NL-as-policy-encoding
                   + falsifier (H5), token-economics scar of K10 + falsifier (H6) ] ⟵ A-19
    expiry_condition: §13.3 verbatim
  }
13.2 Enforcement asymmetry: post-ratification, validator flags founder-authored writes
     outside the ABI (§14.1) as auto-incidents. Against the founder this is detection +
     convention, not prevention (parchnorm: H2). Stated, not hidden.
13.3 Self-hosting criterion (ratification evidence spec):
     ∃ goal g: subject(g) ⊆ kernel artifacts
       ∧ g traversed declared→integrated under agent execution
       ∧ ∃ incident i, amendment a: a motivated by i ∧ a reached provisional ∧ (verified ∨ reverted-cleanly)
       ∧ founder writes during the window ∈ ABI-only
       ∧ conformance passes on reference AND null adapters.
13.4 Ratification: amendment-kind goal whose falsifier_watch = §13.3; on integrated,
     authority.expired := true. The founder's last constructive act is its decision
     resolution ⟵ PAEOS-3 S4.
```

---

## §14 Kernel ABI (stable contracts)

```
14.1 Founder ABI (the ONLY sanctioned founder write surface):
     root Goal authoring · decision-goal resolutions · Evidence(class=external) ·
     taste Artifacts (designated ref namespace) · amendment veto via decision resolution.
14.2 Runtime ABI: §11 syscalls + §12 contract.  Stability: signatures frozen per major version.
14.3 Store ABI: §2 object model + pinned constants. Guarantee: any v1 object remains
     readable forever (append-only + schema pinning §9.5).
14.4 Lattice ABI: §3 states and transition names frozen per major version.
14.5 Everything else — protocols, skills, parameters, role bodies, adapter internals —
     is EXPLICITLY unstable and evolves via §9.4.
Compatibility rule: a change to §§2,3,4,11 object/state/invariant/syscall surfaces is a
major-version amendment requiring the full Trace-B + decision ceremony (self-application,
PAEOS-1 §8).
```

---

## §15 Kernel size audit

```
INCLUDED (and why it could not be excluded):
  4 primitives            — F1/F2/F3 floor; each pairwise non-collapsible (§1.2)
  9 lattice states        — provisional/reverted forced by F7; terminals forced by T2/T5 semantics
  11 invariants + 2 theorems — each removal reconstructs a demonstrated failure (04-audit)
  3 stances × 4 domains   — epistemic floor from A1+A3; domains = object types
  4 syscalls (3 + 1 optimization) — waist minimality proof in §11
  2 loops                 — work (Goal reconciliation) and evolution (§9.4); the second is
                            what makes the constitution finite (PAEOS-1 §8)

EXCLUDED (and where it lives instead):
  Scheduling/priority policy      → evolution layer; kernel ships conservation only (F16)
  Skill library                   → born from scars post-genesis (I7); zero at genesis
  Protocol refinements            → 4 naive genesis protocols; all else evolves
  Estimation                      → replaced by Budget.allocated (PAEOS-2 §1)
  Agent identity/memory/messaging → forbidden (K4/K5; store-only coordination)
  Summarization/context mgmt      → non-problem by construction (D1)
  Runtime features (MCP, hooks…)  → adapter accelerations, never kernel dependencies (K9)
  Multi-founder governance        → out of scope by declared assumption (H1)
  UI / notification / paging      → adapter concern (§12)

PARAMETERS (amendable, genesis-initialized, NOT kernel structure):
  CAP (K10) · W (pruning window) · DL (link depth) · N defaults per protocol ·
  classification thresholds · budget defaults per quadrant.
```

---

*Kernel v1.0 frozen. Implementation may begin: PAEOS-5 is the mechanical realization of §§2–13 in the reference adapter; any ambiguity discovered during implementation is, by definition, a defect in this document and enters as Goal(kind=incident) against the kernel spec.*
