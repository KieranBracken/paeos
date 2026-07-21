# PAEOS-4 — Formal Kernel Specification (v1.1 — CANONICAL)

Status: **CANONICAL SINGLE SOURCE OF TRUTH.** All implementation references this document.
Produced by the **mechanical merge** mandated by PAEOS-8.1 Z-1.3: the frozen PAEOS-4 v1.0
with every ratified amendment applied inline. No redesign, no new content — every change
below carries a provenance tag citing the amendment that produced it. The full amendment
ledger is in §16.

Merged sources: **PAEOS-4 v1.0** (base) · **PAEOS-3.5** A-01..A-19 (already integrated in
base; retained) · **PAEOS-5.5** B-01..B-08, H-01..H-10, SC-01..SC-24 · **PAEOS-8.1**
Z-1..Z-2, A-1, C-1, D-1, E-1, F-1, G-1.

Provenance convention: `⟵ X` cites the forcing source. Tags of form `⟵ B-01`, `⟵ SC-03`,
`⟵ 8.1 A-1` mark content merged from an amendment. Untagged text is base PAEOS-4.
Keywords MUST / MUST NOT / SHALL / SHALL NOT / MAY per RFC 2119.

## §0 Precedence ⟵ 8.1 Z-1

The specification SHALL be read as a single ordered corpus. Precedence, highest first:
(a) **PAEOS-8.1** for the clauses it names; (b) ratified review amendments (PAEOS-3.5,
PAEOS-5.5, PAEOS-7 series); (c) this document (the merged kernel); (d) all other documents.
Where a higher clause conflicts with a lower one, the higher governs and the lower is void
**only to the extent of the conflict**. This document IS the tier-(c) reissue; it already
incorporates tiers (a)/(b) for the kernel surface, so for implementation it is authoritative
standalone.

**Pinned constants** (the only non-derived content; required for cross-implementation
compatibility, semantically neutral):
- `HASH = SHA-256`; a HASH value is serialized as the string `"sha256:" + 64 lowercase hex` ⟵ SC-02
- `SERIAL = JCS (RFC 8785) canonical JSON` for structured objects; raw bytes for blob content
- `ID = ULID`; genesis/fixture objects use the pinned-ULID namespace `01J` + 20×`0` + 3-char suffix ⟵ SC-10
- `SIGN = Ed25519` over `SHA-256(JCS(object body sans signature))`; signature encoded base64url unpadded ⟵ SC-03
- `TIME = RFC3339 UTC, millisecond precision, Z suffix` (`YYYY-MM-DDTHH:MM:SS.sssZ`) ⟵ SC-04
- inline bytes are encoded `{"b64": "<base64url unpadded>"}`; blob refs `{"ref": "sha256:<hex>"}` ⟵ SC-01
- kernel resource units (CAP, truncation, budget `bytes` dimension) are denominated in **UTF-8 bytes**, not tokens ⟵ B-06

Changing a pinned constant is a major-version kernel amendment.

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

### 1.3 Rejected primitives
| Candidate | Still fails because |
|---|---|
| Task / Plan / Mission | Leaf Goal / Goal decomposition + aggregation / root Goal region |
| Incident, Decision, Amendment | `goal.kind` subtypes; all Goal machinery applies unchanged ⟵ A-02 |
| Review / Report | Evidence of class `verdict` / Artifact |
| Agent | A process: (Role × Context) with no persistent identity ⟵ K4+K5 ⟹ D1 |
| Team / Workflow | Protocol-kind Policy content |
| Trunk | A **ref** (§2.1), not an object type ⟵ A-03 |
| Runtime / Adapter | Outside the kernel by K9; governed by contract (§12) |
| Message / Channel | FORBIDDEN. All coordination passes through the store ⟵ A2, K4 |

---

## §2 Store model and schemas

### 2.1 Store ⟵ A2, I4/K4, H4; storage model ⟵ B-04; trunk boundary ⟵ 8.1 D-1
```
Store := (Objects, Refs)
Objects : content-addressed; on disk at store/objects/<sha256-hex>.json   ⟵ B-04
          (kernel hash addresses; git's own hashing is opaque)
          blob content at store/objects/blobs/<sha256-hex>                ⟵ B-04, SC-01
Refs    : mutable manifests at store/refs/<namespace>.json, updated in the
          same commit as the object batch (the commit IS the ref transaction) ⟵ B-04
  reserved ref classes:
    trunk/<workload-id>    integrator-owned; EXACTLY ONE per workload      ⟵ 8.1 D-1
    head/<object-id>       current version
    branch/spec/<goal-id>/<n>  speculation isolation via git worktrees;
                           WORK-PRODUCT FILES ONLY — kernel objects never
                           live on speculation refs                        ⟵ A-16, H-07
    refs/checks.json       live Check inventory                            ⟵ B-07
    refs/dependents.json   derived index (rebuildable cache)               ⟵ H-08
    refs/lease.json        single-writer lease                            ⟵ H-01
Append-only: objects are never deleted or rewritten; ref updates are the only mutation.
Snapshot token = git commit id (opaque; never parsed by kernel code).      ⟵ B-04
Caches (store/index/**, refs/dependents.json) are freely rebuilt from objects;
  NEVER authoritative (D1). A canonical rebuild path MUST exist and be conformance-tested. ⟵ H-08
```
**Trunk semantics** ⟵ 8.1 D-1: there MUST be exactly one trunk per workload,
`trunk/<workload-id>` (`trunk/kernel` for the bootstrap workload). A trunk is created by the
genesis batch (`trunk/kernel`) or at workload-root authoring; no other event creates one.
Every goal integrates to the trunk of its `workload` and MUST NOT integrate to any other.
K8 therefore serializes integration **per workload**; integration MAY proceed in parallel
**across** workloads. Additional trunks within a workload MUST NOT exist absent an Amendment.

### 2.2 Common header (all kernel objects)
```
Header {
  id:       ID            REQUIRED
  type:     artifact|goal|evidence|policy  REQUIRED
  version:  uint          REQUIRED  — 1 for ImmutableRecords, monotonic for ReconciledObjects
  prev:     HASH?         REQUIRED for version>1; MUST be null for ImmutableRecords
  schema:   HASH          REQUIRED  — pins the schema version (§9.5)
  created:  TIME          REQUIRED  ⟵ SC-04
  author:   Provenance    REQUIRED — server-stamped, never proposer-supplied ⟵ B-02
}
Identity: (id). Version identity: (id, version). Global identity: object hash.
Concurrency: WRITE with stale prev ⟹ IDENTITY_CONFLICT (optimistic; single-writer lease H-01)
Meta-schema sentinel: the value schema="sha256:meta.v1" is legal ONLY for schema-artifact
  Policy objects and the GenesisRecord (§13, §2.8); it resolves to the meta-schema (§2.8),
  which is validated at genesis before any store-resident schema exists.  ⟵ B-03, 8.1 Z-2
```

### 2.3 Provenance ⟵ A3, A-08, A-09; kernel actor ⟵ B-01; server-stamping ⟵ B-02
```
Provenance {
  actor:     founder | agent | syscall | kernel   REQUIRED    ⟵ B-01 (adds `kernel`)
  role:      (stance, domain)?             REQUIRED iff actor=agent
  model:     string?                       REQUIRED iff actor=agent — model family id
  adapter:   string?                       REQUIRED iff actor∈{agent,syscall}
  spawn:     HASH?                         — SpawnRecord (§2.8) that produced this actor
  signature: {alg:"ed25519", sig, key_id}? REQUIRED iff evidence class=execution ⟵ A-09, SC-03
}
Provenance is stamped SERVER-SIDE by WRITE from the spawn lease or call context; a proposed
object carrying its own author fields is rejected FORBIDDEN_CLASS.                  ⟵ B-02
actor=kernel is used only by the reactor/liveness/aggregation machinery for
kernel-maintained fields (§2.5 status/budget).                                     ⟵ B-01
```

### 2.4 Artifact
```
Artifact : Header + {
  media_type: string        REQUIRED
  content:    {b64:string} | {ref:HASH}  REQUIRED  ⟵ SC-01
  links:      [HASH]        REQUIRED (may be empty) — explicit link graph ⟵ A-05
  workload:   WorkloadId?               — tenant tag ⟵ A-17
}
```

### 2.5 Goal
```
Goal : Header + {
  kind:            work | incident | decision | amendment   REQUIRED
  spec: {
    delta:         text            REQUIRED — falsifiable; clauses tagged [c1],[c2],… ⟵ SC-05
    evidence_spec: [EvidenceReq]   REQUIRED, non-empty ⟵ I1
                   (for a non-leaf goal, DISCHARGED BY the AggregationContract — no
                    independent evidence required beyond §2.5-aggregation) ⟵ 8.1 A-1.1
    constraints:   [HASH]          REQUIRED (may be empty)
  }
  parent:          GoalId?         — null ⟺ root goal
  serving_clause:  ClauseRef?      REQUIRED iff parent≠null; format "<parent-ulid>#c<n>" ⟵ SC-05
  aggregation:     AggregationContract?  REQUIRED iff goal has children
  classification:  HASH?           — Evidence(class=classification) ref ⟵ A-14; REQUIRED before dispatch
  budget:          Budget          REQUIRED ⟵ A-12 (§10)
  status:          LatticeState    REQUIRED (§3) — KERNEL-MAINTAINED (agents MUST NOT propose it) ⟵ B-01
  capabilities:    [CapabilityRef]?  — NOT in this merge (CAP-1 unratified); reserved, absent in v1.1
  assignee_class:  agent | founder REQUIRED — MUST be founder iff kind=decision ⟵ A4
  workload:        WorkloadId?     — inherited from parent; null only for kernel-scoped goals
  payload:         (by kind, below)
  links:           [HASH]          — context links ⟵ A-05
}
Kernel-maintained fields (status; budget.spent_direct/delegated) are written only by
actor=kernel; a Goal version proposed by an agent that sets them ⟹ FORBIDDEN_CLASS. ⟵ B-01

payload(work)      := {}
payload(incident)  := { failure_ref: HASH REQUIRED, hazard_class: reversible|irreversible REQUIRED ⟵ A-18 }
payload(decision)  := { question, options:[{label,argument}], recommendation?,
                        resolution:{choice, rationale, terminal: amendment_ref | oneoff_record}? } ⟵ K7
payload(amendment) := { delta: PolicyDelta REQUIRED, falsifier_watch: EvidenceReq REQUIRED ⟵ A-06,
                        motivation:[HASH] REQUIRED ⟵ I7 }

PolicyDelta := { target_policy_id, expected_prev: HASH, operation: create|revise|tombstone,
                 body: <full replacement body> }   — full replacement, no patching ⟵ SC-07

EvidenceReq { claim: text template REQUIRED;
              class: execution|verdict|external|classification REQUIRED;
              decorrelation: mechanical|provenance-decorrelated|none REQUIRED ⟵ A-08;
              min_count: uint = 1 }

AggregationContract {
  rule: all-children-verified | quorum(n) | weighted(W) ;
  W:   [ (child_id, weight:uint) ]  — required iff rule=weighted        ⟵ 8.1 A-1.3
  threshold: uint?                  — optional explicit override         ⟵ 8.1 A-1.3
  composition: text
}
Cardinality: Goal 0..1 parent, 0..n children; child.workload MUST = parent.workload.
```

### 2.6 Evidence ⟵ A-07, A-09, A-14; verdict min read-set ⟵ H-02
```
Evidence : Header(version=1) + {
  goal:      GoalId          REQUIRED
  claim:     text            REQUIRED
  polarity:  supports | refutes         REQUIRED
  class:     execution | verdict | external | classification   REQUIRED
  observation: { command?, output_hash?, verdict_text?, source? }  REQUIRED
  read_set:  [(ObjectId|RefName, HASH)] REQUIRED ⟵ A-07
  basis:     [HASH]          REQUIRED (may be empty) — justification edges; MUST be acyclic ⟵ Ω-16
  cost:      Budget          REQUIRED ⟵ A-12
}
Constraints:
  class=execution  ⟹ author.actor=syscall ∧ signature present (Ed25519) ⟵ A-09, SC-03
  class=external   ⟹ author.actor=founder
  class=verdict    ⟹ author.actor=agent ∧ role.stance ∈ {FALSIFY, SELECT};
                     WRITE stamps a mandatory minimum read_set = {goal version,
                     context manifest hash} ∪ agent-declared extras          ⟵ H-02
Liveness (computed, never stored):
  live(e) ⟺ ∀(o,h) ∈ read_set: head(o)=h  ∧  ∀b ∈ basis: live(b)   (transitive) ⟵ A-07
```

### 2.7 Policy ⟵ A-13, A-17, A-18; TriggerExpr ⟵ SC-06; ExternalScar ⟵ SC-08
```
Policy : Header + {
  kind:      constitution | protocol | skill | role | schema-artifact   REQUIRED ⟵ B-03
  scope:     kernel | workload:<id>                    REQUIRED ⟵ A-17
  scar:      [HASH]   REQUIRED, non-empty — incident refs or ExternalScar ⟵ I7/K6
  scar_class: incurred | vicarious                     REQUIRED ⟵ A-18
  falsifier: { statement: text, watch: EvidenceReq }   REQUIRED
  firing:    [ { at, goal, effect } ]                  REQUIRED (append-only) — FiringEvent §2.8
  tombstone: HASH?                                     ⟵ A-13
  loading:   always | routed | triggered | at-spawn    REQUIRED; MUST match kind
  body:      text | structured
  trigger:   TriggerExpr?   REQUIRED iff kind=skill    ⟵ SC-06
  requires:  [PolicyId]     — skill DAG; MUST be acyclic
  priority:  int = 0        — deterministic truncation order (§6.4)
}
TriggerExpr := JSON predicate AST over paths {goal.kind, goal.classification.v,
  goal.classification.r, goal.workload, role.stance, role.domain}:
  {"all":[…]} {"any":[…]} {"not":…} {"eq":[path,val]} {"in":[path,[…]]}
  {"media_in_links":[media_type]}                                          ⟵ SC-06
ExternalScar := Artifact media_type "application/x-paeos-scar+json",
  body {source, date, description, failure_mode, hazard_class}             ⟵ SC-08
Mutation: Policy versions are appended ONLY as the effect of an integrated amendment-kind
Goal (§3.4, §9.4).
```

### 2.8 Schemas referenced by the kernel (H-04 completion; B-03/B-07 additions)
These object schemas MUST exist as kernel-scope schema-artifact Policies; prior versions
referenced them without definition (5.5 H-04). Field lists are normative:
```
SpawnRecord   { agent, role:(stance,domain), goal:HASH, context_manifest_ref:HASH,
                lease, adapter, model }                                     ⟵ H-04
DispatchRecord{ goal:HASH, classification_ref:HASH, protocol:PolicyRef, fanout:uint,
                evidence_reqs:[EvidenceReq], child_budget:Budget, escalate:bool } ⟵ H-04, §7
FiringEvent   { at_snapshot, goal:HASH, effect:text }                       ⟵ H-04
Check         { cmd:[string], input_selector, expected_exit:int, claim_template:text };
              media_type "application/x-paeos-check+json"; live set at refs/checks.json ⟵ B-07
GenesisRecord { …§13.1 field list… }                                       ⟵ H-04, §13
meta.v1       { the meta-schema of §2.8.1 }                                 ⟵ B-03, 8.1 Z-2
```

#### 2.8.1 The meta-schema (`sha256:meta.v1`) ⟵ 8.1 Z-2
Embedded byte-identically (post-JCS) in every conformant implementation; its content hash
MUST equal the sentinel `sha256:meta.v1` (verified at build time). It validates exactly two
shapes and rejects all others `SCHEMA_VIOLATION`:
```
meta.v1 := {
  "$id": "sha256:meta.v1",
  "validates": ["policy/schema-artifact", "genesis-record"],
  "common_header": {
    "id":{"type":"ULID","required":true}, "type":{"enum":["policy","genesis-record"],"required":true},
    "version":{"type":"uint","const":1,"required":true}, "prev":{"type":["null"],"required":true},
    "schema":{"const":"sha256:meta.v1","required":true}, "created":{"type":"rfc3339-ms-utc","required":true},
    "author":{"$ref":"provenance","required":true}
  },
  "policy/schema-artifact": { "kind":{"const":"schema-artifact","required":true},
    "scope":{"const":"kernel","required":true}, "body":{"type":"json-schema","required":true},
    "loading":{"const":"always","required":true} },
  "genesis-record": { "$ref":"§13.1 field list", "required_all":true }
}
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

### 3.2 Entry conditions (skipping intermediate states is legal when a later state's conditions already hold)
```
declared     : schema-valid Goal exists
speculated   : ≥1 candidate Artifact linked, on an isolated speculation branch (A-16)
executed     : live Evidence(class=execution, supports) for the candidate exists
verified     : (LEAF) goal.spec.evidence_spec fully satisfied by LIVE evidence
                      ∧ decorrelation met (K3) ∧ no live refuting evidence (K1, A-10);
               (NON-LEAF) AggregationContract satisfied per §3.3-T6 — this DISCHARGES the
                      evidence_spec; no separate evidence required            ⟵ 8.1 A-1.1
provisional  : kind=amendment ∧ executed ∧ delta applied to Policy store ∧ falsifier_watch ARMED ⟵ A-06
integrated   : verified ∧ merged to the workload trunk by Integrator (K8, §2.1)
                      ∧ parent aggregation input recorded
               (kind=amendment: auto-transition from verified; delta already live since provisional)
failed       : evidence_spec unsatisfiable (proven) ∨ attempts exhausted per protocol
abandoned    : parent withdrawn ∨ founder withdrawal (recorded)
reverted     : kind=amendment ∧ falsifier_watch produced live refuting evidence ⟹ MECHANICAL revert ⟵ A-06
```

### 3.3 Automatic transitions (reactor is STATE-DRIVEN: every cycle recomputes pending transitions from the snapshot; no event cursor) ⟵ H-05
```
T1 REGRESSION   : any expiry of evidence supporting state s ⟹ status := max state whose
                  entry conditions still hold. Floor: integrated.        ⟵ I2/K2
T2 POST-INTEGRATION EXPIRY : expiry of an integrated goal's evidence does NOT regress it;
                  it MUST auto-spawn Goal(kind=incident).                 ⟵ F15
T3 REVERT       : provisional + live refuting falsifier evidence ⟹ reverted, delta unapplied;
                  the target policy head returns to its pre-provisional version ⟵ A-06, 8.1 E-1.3
T4 AMEND-FINAL  : amendment verified ⟹ integrated (no integrator action; delta live).
T5 BUDGET       : budget exhausted ⟹ no state change; goal flagged blocked (computed);
                  auto-spawn Goal(kind=incident). `blocked` is NOT a lattice state and
                  does NOT itself change status.                          ⟵ A-12, 8.1 C-1.3
T6 AGGREGATE    : the reactor MUST re-evaluate a non-leaf goal's AggregationContract whenever
                  any child status changes, MUST promote the parent to `verified` when the
                  contract is satisfied, and MUST regress it (T1) when it ceases to hold.
                  T6 is a reactor (actor=kernel) action; no agent performs it; it sets
                  `verified` only — integration remains the Integrator's (K8).  ⟵ 8.1 A-1.2
                  Satisfaction: all-children-verified ⟺ every child ∈ {verified,integrated};
                  quorum(n) ⟺ ≥ n children ∈ {verified,integrated};
                  weighted(W) ⟺ Σ weights of children ∈ {verified,integrated}
                    ≥ threshold if given, else ⌈(Σ all weights)/2⌉+1.        ⟵ 8.1 A-1.3
```

### 3.4 Forbidden transitions (validator-enforced)
```
X1: any promotion without the entry condition's live evidence (K1)
X2: → integrated except from verified (or T4)
X3: any transition out of a terminal state
X4: → provisional for kind ≠ amendment
X5: kind=amendment → integrated without passing provisional
X6: status/kernel-maintained fields written by any actor ≠ kernel; GENERATE-stance actors
    writing their own goal's verification states                          ⟵ B-01 (extends base X6)
```

---

## §4 Invariants (K1–K11 axioms, D1–D2 derived)

Format — S: statement · E: enforcement point. (Derivations retained from base; abbreviated here.)
```
K1  EVIDENCE-GATED PROMOTION — status enters a state only on satisfying live evidence; live
    refutation blocks (default-deny). E: Validator on WRITE changing status.
K2  READ-SET BINDING & TRANSITIVE EXPIRY — evidence live iff read_set at head ∧ basis live.
    E: kernel liveness fn, recomputed on ref update.
K3  DECORRELATED VERIFICATION — provenance-decorrelated evidence differs in model family or
    is mechanically augmented with deficit recorded. E: validator provenance compare + §12.
K4  APPEND-ONLY STORE — objects immutable; refs the only mutation. E: syscall (no overwrite/DELETE).
K5  COMPILED CONTEXTS OVER EXPLICIT LINKS — agents act only on compile() output. E: SPAWN.
K6  SCAR + FALSIFIER + FIRING + TOMBSTONE — every Policy carries all; pruned⟹tombstone;
    re-admission needs evidence exceeding original scar. E: validator on Policy WRITE.
K7  FOUNDER GOALS TERMINATE IN POLICY — decision-goal closes only with amendment or one-off. E: validator.
K8  SINGLE INTEGRATOR PER TRUNK — each trunk/<workload-id> accepts one Integrator at a time
    (per-workload serialization; cross-workload parallel). E: syscall ref-update lease. ⟵ 8.1 D-1
K9  NARROW WAIST — kernel assumes exactly §11 syscalls. E: conformance (§12.4) incl. null adapter.
K10 KERNEL SIZE CAP — constitution-kind Policy total ≤ CAP **bytes** (genesis param). E: validator. ⟵ B-06
K11 BUDGET CONSERVATION — Σ children.allocated ≤ parent.allocated − parent.spent_direct, per
    dimension; roots founder-set. E: validator on child WRITE; SPAWN/EXEC debit checks.
D1  CRASH-ONLY AGENTS (theorem) — any agent killed loses nothing (K4 + K5). Conformance-tested.
D2  CONSTRAINT MONOTONICITY (theorem) — children tighten inherited constraints; loosening = decision-goal.
```
Named validator checks additionally include **SIG** (Ed25519 verification of execution-class
evidence against genesis trust roots) ⟵ H-03, and the **acyclicity** of evidence `basis` and
skill `requires` graphs ⟵ Ω-16.

---

## §5 Roles

### 5.1 Definition ⟵ A-04
```
Role := (stance, domain) ; stance ∈ {GENERATE, FALSIFY, SELECT} ; domain ∈ {WORK, GOALSTRUCT, POLICY, TRUNK}
```
Conventional bindings: Builder=(G,WORK) · Decomposer=(G,GOALSTRUCT) · Steward=(G,POLICY) ·
Integrator=(G,TRUNK) · Adversary=(F,WORK) · Judge=(S,WORK) · Router=(S,GOALSTRUCT).

### 5.2 Interface (uniform)
```
spawn-in : Context (compiled, §6) + budget lease
run      : within isolated speculation branch (A-16)
return   : ProposedWrites [objects] + SpawnRecord — committed atomically via WRITE or discarded
terminate: on return, budget exhaustion, or kill (D1 safe)
Demand paging (PAEOS-3 §4): a (stance,domain) is instantiated only when a protocol step or
kernel invariant requires that cell for a live goal.
```

### 5.3 Mutation matrix (validator-enforced)
| actor / stance | MAY write | MUST NOT write |
|---|---|---|
| **kernel** ⟵ B-01 | status transitions (reactor T1–T6); budget spent_direct/delegated | anything requiring judgment (Artifacts, Policy bodies) |
| GENERATE | Artifacts; child Goals (GOALSTRUCT); amendment-payload drafts (POLICY); trunk ref updates (TRUNK, under K8 lease) | **Any Evidence**; **status/kernel-maintained fields** ⟵ B-01 (execution evidence only via EXEC ⟵ A-09; self-testimony ⟵ X6) |
| FALSIFY | Evidence(class=verdict); Goal(kind=incident) | Artifacts on the goal under test; status promotions |
| SELECT | Evidence(class=verdict, selection); Evidence(class=classification) (Router); DispatchRecords | Artifacts; Policy |
| founder (external, not a role) | root Goals; decision resolutions; Evidence(class=external); taste Artifacts | everything else — direct work-product edits are auto-Incidents (§13.2) |
Provenance for every row is stamped server-side by WRITE (B-02); actors cannot self-report identity.

---

## §6 Compiler

`compile(goal: HASH, role: Role, snapshot: StoreView) → Context`

### 6.1 Determinism ⟵ K5, A-05
Pure function of its three arguments. Two conformant implementations MUST produce
byte-identical `Context.manifest` **and** byte-identical `Context.rendered` (§6.3) for
identical inputs. ⟵ 8.1 F-1 (extends base, which pinned manifest only)

### 6.2 Inputs (resolution order)
```
1. Constitution : all Policy(kind=constitution), scope ∈ {kernel, goal.workload}
2. Role         : Policy(kind=role) for (stance,domain)
3. Protocol     : per goal's DispatchRecord (§7)
4. Skills       : { s : kind=skill ∧ scope ∈ {kernel, goal.workload} ∧ tombstone=null
                    ∧ trigger(s)(goal, classification, link-media-types, role)=true }
                  ∪ transitive closure of requires (acyclic)
5. Goal         : the goal version + parent-chain serving-clause context
6. Links        : closure over goal.links ∪ artifact.links to depth DL (genesis param)
7. Evidence     : live evidence for the goal + live refutations (always included, A-10)
```
Scope conflict: workload policy MAY tighten, MUST NOT contradict kernel scope ⟹ COMPILE_FAILURE + auto-incident.

### 6.3 Output + render grammar ⟵ 8.1 F-1 (resolves B-05)
```
Context { manifest:[(slot,object_id,version,HASH)]; rendered:text; truncation:[(HASH,reason)] }
context_hash = HASH(SERIAL(manifest))
```
`render(manifest) → text` MUST be total and deterministic (byte-identical across
implementations). Grammar, exactly: sections in **manifest order** (= resolution order);
each entry as one header line `## <slot> <id>@<version>\n`, then the entry's verbatim body
bytes, then a single `\n`; sections separated by the fixed delimiter `\n---\n`; **no other
bytes** (no preamble, trailer, or body-whitespace normalization). Adapter lowering (§12.1)
MAY wrap this in a declared, hashed preamble but MUST NOT alter bytes between first and last
section. ⟵ 8.1 F-1

### 6.4 Byte budget & truncation ⟵ B-06
Denominated in **UTF-8 bytes** (not tokens). Drop order = reverse of resolution order;
within a slot, ascending `priority`, then descending id. Constitution and Role are never
truncated (K10 guarantees fit). All drops recorded in `truncation`.

### 6.5 Caching & pinning
`context_hash` keys the cache; manifest pins exact policy versions ⟹ outcomes attributable
to the versions that produced them (tournament-between-versions).

---

## §7 Router

### 7.1 Two-step contract ⟵ A-14; Check inventory ⟵ B-07; dependents index ⟵ H-08
```
Step 1 (SELECT,GOALSTRUCT): classify(goal) → Evidence(class=classification) {
  observation: { v: mechanical | adversarial | external , r: reversible | guarded | irreversible }
  read_set: [ refs/checks.json head, refs/dependents.json head, goal version ]  ⟵ A-14, B-07, H-08
}
  v=mechanical ⟺ ∃ Check (§2.8) whose claim_template covers the evidence_spec.       ⟵ B-07
  Expiry (new checks, new dependents) ⟹ re-classification forced.
Step 2 (kernel fn): route(goal, classification, policies) → DispatchRecord (§2.8) {
  protocol: PolicyRef matching (v,r); fanout:N; evidence_reqs; child_budget (§10.3); escalate:bool }
  Deterministic; reproducible from the DispatchRecord.
```

### 7.2 Escalation ⟵ A4, A-15
```
escalate ⟹ spawn Goal(kind=decision) iff:
  (r=irreversible ∧ v=external ∧ no covering Policy) ∨ constraint loosening (D2)
  ∨ classification unachievable ∨ taste starvation.
Root goals MUST pass root-goal ceremony (adversarial interrogation, (F,GOALSTRUCT)) before
first decomposition ⟵ A-15.
```

---

## §8 Evidence semantics (truth model)
```
believed(claim) ⟺ ∃ satisfying live evidence per EvidenceReq ∧ ¬∃ live Evidence(refutes) ⟵ K1, A-10
Authority (descending): external > execution(signed) > verdict > classification.
Conflict at equal authority: default-deny until superseded or expired.
```
- Read-set binding §2.6; execution signatures EXEC-emitted, Ed25519, validator-verified (SIG) ⟵ A-09, H-03.
- Adapter trust: agents untrusted; adapters trusted-but-conformance-verified (keys in §13);
  founder sovereign — enforcement against founder is detection+convention (parchment, H2).
- Expiry transitive along basis edges (acyclic, Ω-16).

---

## §9 Policy system
```
9.1 Namespaces: scope ∈ {kernel, workload:<id>} ⟵ A-17. Workload policies tighten only.
9.2 Promotion workload→kernel: amendment citing independently incurred scars in ≥2 workloads ⟵ A-17.
9.3 Skills: loading=triggered; born only from amendment goals citing scars; versions pinned in manifest.
9.4 Amendment lifecycle (= amendment-kind Goal lattice, §3):
    declared → speculated(delta drafted) → executed(delta schema-valid)
    → provisional(delta APPLIED, falsifier ARMED) → verified → integrated(T4) | reverted(T3) ⟵ A-06
    Concurrency ⟵ 8.1 E-1:
      • PolicyDelta.expected_prev is checked against the target policy's CURRENT HEAD at
        application time; a provisional amendment's applied delta DOES advance the head.
      • Therefore AT MOST ONE amendment to a given policy MAY be provisional at a time; a
        second targeting the same policy MUST block (IDENTITY_CONFLICT) until the first
        integrates or reverts. On revert (T3) the head restores; blocked amendments MAY retry.
9.5 Pruning: firing quiet for window W ⟹ Steward MUST spawn pruning amendment (tombstone);
    re-admission needs strictly-exceeding evidence ⟵ A-13.
9.6 Schemas are kernel-scope schema-artifact Policies; objects pin schema by hash (§2.2);
    schema evolution rides the amendment lifecycle. ⟵ B-03
```

---

## §10 Budget model ⟵ A-12
```
Budget {
  dimensions: { bytes:uint, exec_seconds:uint, verification_passes:uint,
                decisions:uint, wall_clock_s:uint }   ⟵ B-06 (tokens→bytes); decisions=founder attention (A4)
  allocated: Vec, spent_direct: Vec, delegated: Vec
}
10.1 Conservation (K11): delegated ≤ allocated − spent_direct, per dimension, always.
10.2 Roots: allocated set by founder at root-goal authoring (appetite; replaces estimation).
10.3 Propagation: DispatchRecord.child_budget debits parent.delegated at child WRITE;
     EXEC/SPAWN debit spent_direct at call time (two-phase lease: reserve at SPAWN, settle
     at ProposedWrites commit; unsettled reservations expire at boot) ⟵ SC/03; Evidence.cost records actuals.
10.4 Exhaustion: syscalls fail BUDGET_EXCEEDED; T5 fires (blocked flag + auto-incident). No silent overrun.
10.5 Verification economics: verification_passes limits fan-out (tournament N ≤ remaining passes).
10.6 Accrual ⟵ 8.1 C-1:
     • wall_clock_s accrues ONLY while actively dispatched (agent spawned or EXEC in flight);
       time in `blocked` or awaiting a Decision MUST NOT be charged.
     • the `decisions` dimension is debited exactly 1 from the nearest ancestor holding that
       allocation, at Decision spawn (escalation); NOT again on resolution.
     • `blocked` is a computed flag, not a state, and SHALL NOT by itself cause BUDGET_EXCEEDED.
```

---

## §11 Syscalls ⟵ K9
```
READ(selector, snapshot?) → [ObjectVersion]
  selector := pinned conjunctive DSL {type, kind?, status?, workload?, parent?, has_classification?} ⟵ B-08
  Guarantees: immutable results; monotonic snapshot per process. Errors: NOT_FOUND.

WRITE(objects, expect:[(id,prev_hash)]) → [HASH]
  Atomic batch (commit = single ref transaction; single-writer lease H-01).
  STAMPS provenance server-side (B-02); REJECTS proposer-set author/status/kernel-maintained
  fields (FORBIDDEN_CLASS, B-01). Validation: schema (incl. meta-schema at genesis),
  mutation matrix (§5.3), SIG (H-03), K1/K6/K10/K11, X1–X6, acyclicity.
  Errors: SCHEMA_VIOLATION, IDENTITY_CONFLICT, FORBIDDEN_CLASS, INVARIANT_VIOLATION(id), BUDGET_EXCEEDED.
  Guarantee: no partial state ever visible (D1).

EXEC(check_ref: HASH, worktree: RefName, budget_lease) → (output: Artifact, evidence: HASH)  ⟵ B-07
  Runs the referenced Check (§2.8) in the adapter sandbox against the goal's speculation
  worktree; sandbox write-mask = worktree only ⟵ 06-A12. Auto-captures read_set = input_refs
  + declared environment hash; EMITS Evidence(class=execution) signed Ed25519 by the adapter
  (agents receive the ref, never author it) ⟵ A-09.
  Errors: BUDGET_EXCEEDED, SANDBOX_VIOLATION, NONZERO_EXIT (still emits evidence, polarity=refutes).

SPAWN(role, goal, budget_lease) → SpawnHandle → ProposedWrites
  1. context := compile(goal, role, snapshot) (K5)
  2. instantiate on an isolated speculation branch; siblings MUST be mutually unreadable ⟵ A-16
     (sequential emulation MUST branch-isolate; violation = conformance failure)
  3. return deltas as ProposedWrites; caller commits via WRITE or discards.
  Reducibility: SPAWN ≡ EXEC(null-adapter, context). Errors: COMPILE_FAILURE, BUDGET_EXCEEDED, ISOLATION_UNAVAILABLE.
```

---

## §12 Adapter contract
```
12.1 MUST: implement §11 exactly; register Ed25519 signing key in genesis record; declare
     CapabilityVector { model_families:[..], concurrent_spawn:bool, sandbox_class, max_context_bytes,
     preamble_hash }; lower Context.rendered to native format with ZERO semantic addition
     beyond a declared, hashed preamble (§6.3).
12.2 MUST NOT: mutate the store outside WRITE; author or alter Evidence; inject unregistered
     instructions; suppress refuting evidence; share state between speculation branches.
12.3 Degradation: no concurrency ⟹ sequential SPAWN with branch isolation (A-16);
     no second model family ⟹ K3 mechanical-augmentation mode, deficit recorded (A-08/H8).
12.4 Conformance suite (all MUST pass): C1 schema round-trip · C2 forge rejection ·
     C3 expiry cascade · C4 isolation · C5 crash-kill · C6 reference goal→verified ·
     C7 amendment cycle · C8 budget conservation.
12.5 Null adapter: normative minimal impl (shell + model API, sequential SPAWN, branch
     isolation via refs). MUST always remain conformant (portability proof + disaster floor).
12.6 Reference adapter: Claude Code; MAY exploit native subagents/hooks; conformance identical.
12.7 Key rotation: adapter trust roots rotate via Amendment to the genesis record trust set ⟵ 06-A13.
```

---

## §13 Genesis
```
13.1 GenesisRecord (first object; schema="sha256:meta.v1"):
  { authority:{founder_id, host_runtime},
    constitutional_basis:[HASH]      — PAEOS-0..3.5 corpus hashes (genesis/constitutional-basis.sha256)
    scar_corpus:[HASH]               — imported incident catalog (Sentium)
    adapter_trust_roots:[(adapter_id, ed25519_pubkey)]
    parameters:{ CAP (bytes ⟵ B-06), W, DL, N_defaults, thresholds }  — each AMENDABLE
    assumptions:[ single-founder(H1), parchment(H2), NL-as-policy-encoding+falsifier(H5),
                  token-economics scar of K10+falsifier(H6) ] ⟵ A-19
    expiry_condition: §13.3 verbatim }
13.2 Enforcement asymmetry: post-ratification, validator flags founder writes outside the ABI
     (§14.1) as auto-incidents; against the founder this is detection+convention (parchment H2).
13.3 Self-hosting criterion (ratification evidence spec):
     ∃ goal g: subject(g) ⊆ kernel artifacts ∧ g traversed declared→integrated under agent
     execution ∧ ∃ incident i, amendment a: a motivated by i ∧ a reached provisional ∧
     (verified ∨ reverted-cleanly) ∧ founder writes in-window ∈ ABI-only ∧ conformance passes
     on reference AND null adapters.
13.4 Ratification: amendment-kind goal whose falsifier_watch = §13.3; on integrated,
     authority.expired := true.
13.5 Genesis batch ordering ⟵ B-03: G1 (GenesisRecord) and G2 (schema artifacts) are ONE
     ATOMIC WRITE, validated by the meta-schema (§2.8.1) — an object cannot pin a schema not
     yet in the store. All subsequent batches validate against the now-resident schemas.
     Genesis is single-shot: re-running on a non-empty store MUST fail.
```

---

## §14 Kernel ABI
```
14.1 Founder ABI (ONLY sanctioned founder write surface): root Goal authoring · decision
     resolutions · Evidence(class=external) · taste Artifacts · amendment veto via resolution.
14.2 Runtime ABI: §11 syscalls + §12 contract. Signatures frozen per major version.
14.3 Store ABI: §2 object model + pinned constants. v1 objects readable forever.
14.4 Lattice ABI: §3 states + transition names (incl. T6) frozen per major version.
14.5 Everything else — protocols, skills, parameters, role/adapter internals — evolves via §9.4.
14.6 Operational subordination ⟵ 8.1 G-1: the operational lifecycle (operations/, L01–L19) is
     METADATA layered over this lattice; L-states MUST NOT be treated as lattice states and MUST
     NOT gate kernel promotion except through the evidence they produce. Where an L-state and the
     kernel lattice disagree, the KERNEL LATTICE GOVERNS. Binding L→lattice mapping lives in
     operations/WORKFLOW_STATE_MACHINE.yaml (lattice_mapping).
Compatibility rule: a change to §§2,3,4,11 surfaces is a major-version amendment requiring full
Trace-B + decision ceremony (self-application).
```

---

## §15 Kernel size audit
Unchanged from v1.0 in structure: 4 primitives · 9 lattice states · 11 invariants + 2 theorems
· 3 stances × 4 domains · 4 syscalls (3 + 1 optimization) · 2 loops. Resource units are bytes
(B-06). Excluded (scheduling, skill library, protocol refinements, estimation, agent
identity/memory/messaging, summarization, runtime features, multi-founder governance, UI) and
parameters (CAP, W, DL, N, thresholds, budget defaults) are as v1.0 §15.

---

## §16 Amendment ledger (this merge)
Every change above traces to one of:

**PAEOS-3.5 (A-01..A-19)** — already integrated in the v1.0 base; retained: A-01 categories ·
A-02/A-03 four primitives + Artifact/Trunk · A-04 stance×domain · A-05 explicit-link compiler ·
A-06 probationary amendment lattice · A-07 read-set/justification binding · A-08 decorrelated
verification · A-09 signed execution evidence · A-10 default-deny · A-11 spec-sufficiency ·
A-12 budget · A-13 tombstones · A-14 classification-as-evidence · A-15 root-goal ceremony ·
A-16 speculation isolation · A-17 policy namespaces · A-18 vicarious scars · A-19 genesis assumptions.

**PAEOS-5.5** — B-01 kernel-maintained status/budget + `kernel` actor (§2.3, §2.5, §5.3, X6) ·
B-02 server-stamped provenance (§2.2, §2.3, §5.3, §11) · B-03 meta-schema sentinel + atomic
G1/G2 (§2.2, §2.8, §13.5) · B-04 store/git model (§2.1) · B-05 render grammar (→ superseded by
8.1 F-1, §6.3) · B-06 bytes not tokens (§0, §6.4, §10, K10) · B-07 Check object + EXEC(check_ref)
(§2.8, §7.1, §11) · B-08 READ selector DSL (§11) · H-01 single-writer lease (§2.1, §11) · H-02
verdict min read-set (§2.6) · H-03 SIG check (§4, §8, §11) · H-04 missing schemas (§2.8) · H-05
state-driven reactor (§3.3) · H-07 speculation = work files only (§2.1) · H-08 dependents index
(§2.1, §7.1) · SC-01 byte encoding · SC-02 hash string · SC-03 Ed25519 · SC-04 timestamp · SC-05
ClauseRef · SC-06 TriggerExpr · SC-07 PolicyDelta · SC-08 ExternalScar · SC-09 CAP (bytes) ·
SC-10 pinned ULIDs · SC-11 9→4 protocol map (genesis protocols) · SC-12 golden provenance ·
SC-13..24 (03/06 pins: store-root, lease, two-phase budget lease, fsync, sandbox write-mask, key rotation) — applied in §2.1/§10.3/§11/§12.7.

**PAEOS-8.1** — Z-1 precedence (§0) · Z-2 meta-schema literal (§2.8.1) · A-1 T6 + non-leaf
aggregation discharge + weighted/threshold (§2.5, §3.2, §3.3) · C-1 budget accrual (§10.6) ·
D-1 one trunk per workload (§2.1, K8) · E-1 provisional-amendment ordering (§9.4) · F-1 render
grammar (§6.1, §6.3) · G-1 operational subordination (§14.6).

**Excluded from this merge (unratified):** CAP-1 (capabilities/skill.provides, reviews/7) —
field reserved but absent; integrate only when ratified.

---

*Kernel v1.1 CANONICAL. This document is the single source of truth for implementation. Any
ambiguity discovered during implementation is, by definition, a defect in this document and
enters as Goal(kind=incident) against it (§14.5 self-application).*
