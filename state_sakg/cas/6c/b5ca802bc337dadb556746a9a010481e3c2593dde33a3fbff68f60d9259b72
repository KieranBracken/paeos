# 01 — Kernel Stress Test (Ontology & Abstraction Attacks)

Investigations 1, 10, 11, 12. Format per finding: violated principle / why it matters / corpus evidence / classification / smallest amendment.

---

## F1 — The unifying abstraction overclaims: PAEOS has two ontological categories, not one **[CONFIRMED — ARCHITECTURAL]**

**Violated principle:** PAEOS-0 M3 (falsifiability of components); intellectual honesty of the kernel sentence.

**Evidence:** PAEOS-1 §0: *"Every kernel object carries a spec (desired state) and a status (evidence state). Agents … reconcile spec toward status. Nothing else exists."* But PAEOS-1 §1.2: Evidence *"is immutable and append-only. It is never edited, only superseded."* Evidence has no spec, no status, and is never reconciled. The same holds for Incident, Decision, and Amendment as specified — they are records with lifecycles, not reconciled spec/status pairs. Only Goal (and Policy, via Amendment) actually reconciles.

**Why it matters:** PAEOS-4 will freeze schemas from this sentence. A schema generator following "every object has spec+status" produces four nonsensical schemas out of six. The kernel sentence is the Grundnorm of the spec; it must be true.

**Classification:** Architectural (definitional), cheap to fix.

**Smallest amendment (A-01):** Restate the kernel: *"PAEOS is a reconciliation system over a typed, append-only artifact store containing two categories: **reconciled objects** (Goal, Policy) carrying spec+status, and **immutable records** (Evidence, and the F2 subtypes) that gate and justify reconciliation."*

---

## F2 — Incident, Decision, and Amendment are Goal in costume: the six primitives compress to four **[CONFIRMED — ARCHITECTURAL]**

**Violated principle:** PAEOS-0 M5 (minimality budget); PAEOS-1's own rejection rule ("the minimality budget forbids two names for one object" — used to kill Task, then not applied to three other objects).

**Evidence, three independent witnesses:**
1. PAEOS-1 §8 already routes Amendments through the goal machinery: *"a Constitution amendment is itself irreversible-ish and hard to verify, so the router sends it through Trace-B ceremony."* An object that is classified by the Router, given ceremony, and integrated **is a Goal** by the corpus's own definitions.
2. PAEOS-1 §1.4: Incident lifecycle `captured → mined → resolved` is the goal lattice with renamed states — a declared desire ("this policy gap is closed") reconciled to integration.
3. PAEOS-1 §1.5: a Decision is a queued question with an evidence spec ("resolution recorded") assigned to a specific oracle (the founder). PAEOS-2 §5 escalation is precisely goal-assignment to the founder. Investigation 12's answer: **the Decision object reduces; the founder-oracle does not.** What is irreducible is that certain goals can only be reconciled by the founder (A4). That is a property of an evidence spec, not a distinct primitive.

**Why it matters:** Three parallel implementations of lifecycle, escalation, and evidence-gating machinery in PAEOS-4/5; three ways for the machinery to drift apart; a fatter kernel taxing every compiled context (I12's own logic).

**Classification:** Architectural (schema-level), must land before PAEOS-4.

**Smallest amendment (A-02):** Retype as Goal subtypes: `goal.kind ∈ {work, incident, decision, amendment}`, preserving each subtype's required fields (scar-mining obligation, founder-only assignment, policy-delta payload). Kernel invariants I7/I8 rebind to the subtypes unchanged. Ontology becomes: **Artifact (base), Goal, Evidence, Policy** (see F3).

---

## F3 — A hidden primitive: the work product itself is untyped and "trunk" is undefined **[CONFIRMED — ARCHITECTURAL]**

**Violated principle:** PAEOS-1's typed-store claim; A6 (only mechanical structure survives).

**Evidence:** I9 mandates *"single-threaded integration per trunk"* — **trunk** appears in an invariant yet no kernel object defines it. Code, documents, and designs — the actual outputs the OS exists to produce — are none of the six objects; they float in the store as untyped blobs that Evidence binds to by hash. The validator (SVK item 3) cannot validate what has no schema.

**Why it matters:** Evidence expiry (I2) — the architecture's most load-bearing mechanism — binds to objects the kernel does not model. Integration (I9) targets a structure the kernel does not model.

**Classification:** Architectural.

**Smallest amendment (A-03):** Admit the base type explicitly: **Artifact** (content-addressed blob + provenance), with Goal/Evidence/Policy as typed refinements, and define **Trunk** as a named, integrator-owned ref over Artifacts (git branch semantics at adapter level).

---

## F4 — The seven roles compress to three stances × four domains **[CONFIRMED — COMPRESSION, NOT DEFECT]**

**Evidence:** Apply the corpus's own definitions:

| Stance ↓ / Domain → | Work products | Goal structure | Policy | Trunk |
|---|---|---|---|---|
| **Generate** | Builder | Decomposer | Steward | Integrator |
| **Falsify** | Adversary | decomposition audit (PAEOS-1 §4) | pruning pass (PAEOS-0 M3) | conformance test |
| **Select** | Judge | decomposition tournament | amendment tournament | **Router** (= select over goal×protocol) |

Every named role is one cell; the corpus already assigns the unnamed cells to existing roles ad hoc (e.g., PAEOS-1 §3 gives the Adversary decomposition audits — the Falsify×GoalStructure cell). The Router is the Select stance applied to dispatch.

**Why it matters:** Investigation 10's answer: "agent" is already not a kernel object (PAEOS-1 rejected it — correctly). But "Role" as seven bespoke definitions hides the real structure. Three stances (generate / falsify / select) are the epistemic primitives forced by A1+A3; domains are just the kernel object types. Seven role files would encode 12 cells inconsistently.

**Classification:** Minimality defect, schema-level.

**Smallest amendment (A-04):** Define Role = (stance, domain) in the kernel; retain the seven names as conventional bindings of common cells. No behavior changes.

---

## F5 — Attack on Skills as primitives: **REJECTED** (already non-primitive, spec is consistent)

Investigation 11 attempted to reduce Skills to Protocols, Goals, or Compiler transforms. Result: Skills are already specified as Policy-kind artifacts (PAEOS-1 §1.3), i.e., non-primitive. The sharpest reduction — "a Skill is a conditional Compiler transform" — is true but is exactly what the spec says (trigger-matched context injection). No two Policy kinds collapse: Constitution/Protocol/Skill/Role differ in *loading semantics* (always / router-selected / trigger-matched / at-spawn), which is a legitimate discriminator field. **No defect proven.**

## F6 — Attack on the Compiler's claimed determinism **[CONFIRMED — ARCHITECTURAL]**

**Violated principle:** I6's enforceability (A6).

**Evidence:** PAEOS-1 §3: the Compiler assembles *"the Goal + linked artifacts + live Evidence, within a token budget."* "Linked" by whom? If links are discovered by relevance ranking, the Compiler exercises judgment and is an eighth (ungoverned, unstanced) intelligence — I6's "compiled deterministically" is false. If links are explicit, the corpus never assigns link-authoring to any role.

**Why it matters:** I6 is the invariant that makes agent behavior reproducible and auditable. A judging Compiler is a hidden agent inside the trusted computing base.

**Classification:** Architectural (contract definition).

**Smallest amendment (A-05):** The Compiler is deterministic over the **explicit link graph only**; authoring links is a Generate-stance duty (Decomposer links context into child goals; Builders link what they consult). Relevance discovery, where needed, is a routable research goal, not a Compiler behavior.
