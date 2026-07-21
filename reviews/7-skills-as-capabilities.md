# Proposal Assessment: Skills as First-Class Capabilities

Date: 2026-07-20 · Status: assessment of a founder proposal against the frozen kernel.
Proposal (verbatim intent): skills become first-class citizens organized by domain
(python/, rust/, postgres/, react/, debugging/, architecture/, testing/, replay/,
security/, performance/, sentium/); the planner does not know Python — it requests
`python_skill`; the runtime schedules it "exactly like an OS schedules a process."

Per PAEOS-4's closing clause, a proposal touching frozen surfaces is handled as a
candidate Incident: assessed, split into already-covered / rejected / new, with any
kernel-touching part routed to the amendment gate — never a silent rewrite.

---

## Verdict — the proposal splits three ways

| Component | Disposition | Where it goes |
|---|---|---|
| Skills as modular, domain-organized, on-demand capability packages | **Already the architecture** | no change — this is Skills-as-Policy (PAEOS-1 §1.3/§5, PAEOS-4 §6.2) |
| "Planner doesn't know Python, requests the capability" | **Already the *goal*, achieved by a better mechanism** | trigger-matched loading; the planner expresses *work*, the Compiler resolves *capability* |
| "Skill scheduled exactly like an OS process" | **Rejected as stated — off by one** | the *process* is the **agent**; the skill is the **library**. Skill=process breaks D1/K5 |
| Guaranteeing the right skill loads on *greenfield* goals | **NEW — a real gap the proposal exposes** | candidate amendment **CAP-1** → pre-Wave-1 gate |

The headline: you are ~80% describing what PAEOS already is, which is a convergence
signal, not redundancy — the same reassurance the independent re-derivation gave. The
remaining 20% contains one correction that matters for correctness and one genuine
improvement worth an amendment.

## 1. What is already true (affirm)

- **Skills are first-class.** A Skill is a `Policy(kind=skill)` — a versioned, scarred,
  falsifiable store object (PAEOS-4 §2.7), owned by the Steward, born from incidents,
  pruned when quiet. That is as first-class as any kernel citizen gets.
- **Domain organization is the natural stratification of the skill population.**
  python/, rust/, sentium/ … are just how workload- and kernel-scoped skills cluster.
  This is *userland taxonomy* (project layer), not a kernel concept — correct, and
  belongs in the gen-1 skill design, not the frozen spec.
- **Capability abstraction already works.** The Decomposer emits a leaf goal ("implement
  X") and never needs Python knowledge; the Compiler (§6.2) loads python_skill by trigger
  match. The planner-doesn't-know-Python property is *already guaranteed* — and by a
  mechanism strictly better than named request, because named request would force the
  planner to know the skill catalog, partly defeating the abstraction.
- **Composition already exists.** `requires: [PolicyId]` gives skills an acyclic DAG; the
  Compiler loads the transitive closure (§6.2). python_skill can require
  packaging_skill, etc.

## 2. The off-by-one that matters (reject "skill = process")

The OS analogy is right; the mapping is off by one level, and the frozen text already
fixes the level:

> PAEOS-1 §3: *"Stances are the instruction set; Skills are the libraries."*
> PAEOS-1 §1.7: agents "as persistent entity → not an object at all; a process … Persisting agents would accumulate hidden state, violating crash-only."

| OS concept | PAEOS | Why |
|---|---|---|
| Process (scheduled, has state, runs) | **Agent** = (Role × compiled Context) via SPAWN | the only thing that "runs"; ephemeral, crash-only (D1) |
| Executable / instruction set | **Role** (stance) | what the process *is* |
| Dynamically-linked library | **Skill** | linked into the process at compile time; holds no runtime state |
| Linker / loader | **Compiler** (§6) | resolves which libraries link, deterministically |
| The syscall to start a process | **SPAWN** | K4 §11 |

Why this is not pedantry: if a *skill* were "scheduled like a process," it would need
runtime identity and state — exactly the persistent-agent hidden state PAEOS-1 rejected
to preserve crash-only restart (D1/K5). Skills must stay stateless linked policy, or the
whole crash-only guarantee unravels. **Agent = process; skill = library** keeps the OS
intuition *and* the invariant.

## 3. The real gap the proposal exposes (this is the payoff)

Trigger-matching is **reactive to existing artifacts**, and its inputs are narrow. Per
SC-06, a TriggerExpr sees only:
`goal.kind, goal.classification.v, goal.classification.r, goal.workload, role.stance,
role.domain`, plus `media_in_links` (media types of *already-linked* artifacts).

There is **no domain/language/capability axis** anywhere in that set. So consider a
greenfield leaf goal: *"implement the validator in Python"* at the moment it is declared.
Classification carries only (v, r). No Python artifact exists yet, so `media_in_links`
is empty of Python. **python_skill's trigger cannot fire** — and the Builder spawns
*without* the Python capability and produces worse Python. The reactive model fails
exactly on creation, which is most of implementation.

This is precisely the hole the proposal's "request the capability" instinct is pointing
at — and it is a genuine defect in §6.2, not a preference.

## 4. Candidate amendment CAP-1 — capability requirements on goals

The fix makes "the planner requests python_skill" literally true, in the safe way:

**Schema (PAEOS-4 §2.5 addition):**
```
Goal.spec.capabilities: [CapabilityRef]   OPTIONAL   — declared required capabilities
CapabilityRef := a stable capability name (e.g. "lang:python", "db:postgres")
```
A **capability** is an interface name; a **skill** is a provider that declares
`provides: [CapabilityRef]`. The Decomposer, which knows the goal is a Python goal,
declares `capabilities: ["lang:python"]` on the leaf — a *constraint*, exactly like a
build manifest declaring `requires: python`. It still names no skill and needs no Python
knowledge; it declares a *need*, not a *provider*.

**Resolution (PAEOS-4 §6.2 addition):** the Compiler loads skills matched by trigger
**OR** providing a declared capability, then the `requires` closure as before:
```
Skills := { s : trigger(s) = true } ∪ { s : s.provides ∩ goal.capabilities ≠ ∅ } ∪ closure(requires)
```
Multiple providers of one capability resolve by the existing `priority`/id order (§6.4) —
which hands you two things for free: **multi-provider capabilities** (a fast python_skill
vs a thorough one) and **skill-version tournaments** (two providers of `lang:python`,
judged blind — PAEOS-2 §5's evolution-of-skills, now with a clean selection point).

**Why this preserves K5/A-05 (no hand-written context):** a capability name resolving to
a skill is a *deterministic, versioned* lookup — identical in kind to a package name
resolving to a library. The Decomposer authors a declared, auditable requirement (already
its A-05 link-authoring duty); the Compiler resolves it mechanically. Nothing is
hand-assembled; the compiled context stays a pure function of the store.

**Class:** kernel-surface amendment (§2.5, §6.2) ⟹ §14.5 ceremony. **Joins the pre-Wave-1
gate** with B-01/B-02/B-06. Blocking? Not for genesis (greenfield-Python is not on the
kernel-bootstrap critical path), but it should land before the first *workload* with a
technology stack (Sentium) — otherwise every greenfield stack goal under-links its
capability. Recommend: draft now, resolve with the other three.

## 5. The "scheduler," done right

There *is* a legitimate scheduling analog, and it already exists: **§6.4 is admission
control under a resource budget.** When trigger-matched + capability-required + required
skills exceed the context byte budget (B-06), §6.4 deterministically admits/drops them
(reverse resolution order, then priority, then id), recording every drop. That is the OS
scheduler's true counterpart — *deterministic admission under a budget*, not a stateful
run queue with preemption. Honor the OS intuition by pointing here, not by building a
stateful scheduler that would violate D1.

## 6. Disposition

1. **Taxonomy (python/, rust/, sentium/ …):** userland/project-layer design. Add the
   capability namespace and the skill-directory organization to
   `design/PAEOS-skills-gen1.md` as gen-2 userland structure. No kernel change.
2. **Capability requirements (CAP-1):** draft as a kernel amendment; route to the
   pre-Wave-1 §14.5 gate alongside B-01/B-02/B-06; blocking before workload #1, not
   before genesis.
3. **Process framing:** corrected here (agent=process, skill=library); no spec change —
   PAEOS-1 §3 already says it. Propagate the correction into any implementation prose
   that drifts toward "running skills."

Net: the proposal is affirmed in substance, sharpened in one place, and it earned the
project one real amendment — which is exactly what a good architectural instinct should
do to a frozen kernel: not bend it, but find the one seam it genuinely missed.
