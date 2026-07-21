# PAEOS-1: The Architecture

> **Archival status:** Frozen derivation document, archived 2026-07-19 from the original
> derivation session (July 2026). Preserved as derived and as reviewed by PAEOS-3.5 —
> NOT updated for subsequent amendments (notably: the six-primitive ontology below was
> compressed to four by PAEOS-3.5 F2/F3; the seven roles to stance×domain by F4; the
> lattice gained probationary states by A-06). Effective current law is PAEOS-4 as
> amended. Do not edit: changes to this document falsify the derivation lineage.

---

**Derivation discipline.** Nothing below is included because it seems useful. Each element cites the axiom or principle that *forces* it, and a rejection list is kept — candidate primitives that dissolved under derivation — because an ontology is only credible if it shows what it refused. Where PAEOS-0 established them, the axioms are referenced as (A1 generation-cheap/verification-scarce, A2 artifacts-durable/context-ephemeral, A3 stance-decorrelation, A4 founder's four inputs, A5 runtimes-churn, A6 unenforced-rules-decay) and principles (evidence states, router-not-pipeline, crash-only agents, interventions-become-policy, no-rule-without-a-scar, tournament evolution, minimality budget).

## 0. The unifying kernel idea

Every mature infrastructure system in the reference class has one load-bearing abstraction: Linux has *everything is a file*, Git has *content-addressed immutable history*, Kubernetes has *declarative reconciliation*, LLVM has *one IR, many backends*. PAEOS needs its own, and the methodology forces it:

> **PAEOS is a reconciliation system over a typed, append-only artifact store. Every kernel object carries a *spec* (desired state) and a *status* (evidence state). Agents are stateless, disposable processes that reconcile spec toward status by producing artifacts and evidence. Nothing else exists.**

This single sentence is derivable term by term: *artifact store* from A2 (only files persist), *append-only* from crash-only agents (mutation in place destroys restartability and audit), *typed* from A6 (untyped rules decay; only mechanical structure survives), *evidence state* from the evidence-lattice principle, *reconciliation* because it is the only control model that needs no long-running coordinator — any process can die at any time and the system's next action is always re-derivable from the store, which is exactly the crash-only requirement. The four reference systems fuse naturally: Git's history model for the store, Kubernetes' reconciliation for control, LLVM's IR/backend split for portability, Linux's process model for agents.

Everything below is elaboration of that sentence.

## 1. Kernel objects — the ontology

Six objects. Each is derived, then the rejections are shown.

### 1.1 Goal

*The representation of intent.* Forced by A4: intent enters the system exactly once, from the founder, and must survive without them; by A2 it must be an artifact.

A Goal contains:
- **Desired delta** — the change to the world it names, in falsifiable terms.
- **Evidence spec** — what observations would prove it achieved (PAEOS-0: a plan that can't fail is a vibe; a goal without an evidence spec is unreconcilable and the kernel rejects it).
- **Constraints** — inherited plus local invariants that bound acceptable solutions.
- **Parent link + serving-clause citation** — which clause of the parent this goal serves (the load-bearing field for §4's intent conservation).
- **Router classification** — verifiability × reversibility, assigned at dispatch.
- **Status** — position on the evidence lattice (§2).

Goals are **recursive**: a goal decomposes into child goals plus an **aggregation contract** stating how children's `verified` statuses compose into the parent's. The recursion bottoms out at a **leaf goal**: one whose evidence spec can be satisfied by a single reconciliation loop. This is why *Task* is not a primitive — a task is just a leaf Goal, and the minimality budget forbids two names for one object. Likewise *Mission* and *Vision* are just the root region of the Goal tree.

### 1.2 Evidence

*The representation of truth.* Forced by A1: since verification is the scarce resource, its output must be a first-class, durable, inspectable object — not a vibe in a context window.

Evidence contains: the **claim** it bears on, the **observation** (command + output, judge verdict, tournament result, user data), **polarity** (supports/refutes), **provenance** (which role, which stance, which model — required by A3, because a judge must be able to discount correlated evidence), and — the critical field — a **binding**: the content hashes of the world-state the observation was made against.

This binding yields the architecture's most important derived rule: **evidence expires**. When any artifact it was bound to changes, the evidence is automatically stale, and every status that rested on it regresses down the lattice. Re-verification is never a policy that someone must remember (A6 says they won't); it is a mechanical consequence of the type system. This one invariant replaces entire categories of process discipline — "always re-test after changes," "reviews go stale," "docs drift" — with a single kernel behavior.

Evidence is immutable and append-only. It is never edited, only superseded.

### 1.3 Policy

*The representation of the rules.* Forced by the self-hosting requirement: if PAEOS evolves by amendment and tournament, its rules must be data in the same store they govern.

Policy has four kinds, all one object type:

| Kind | Loading | Content |
|---|---|---|
| **Constitution** | Always, into every compiled context | Kernel invariants only; hard size cap |
| **Protocol** | Selected by the Router per quadrant | A workflow: roles, parallelism, evidence spec template, gates |
| **Skill** | Trigger-matched by the Compiler | A procedure: when-to-fire, how-to-do, composition requirements |
| **Role** | At agent spawn | A stance definition (§3) |

Every Policy object, regardless of kind, must carry three fields or the kernel rejects it: its **scar** (a link to the Incident that motivated it — no rule without a scar), its **falsifier** (what observation would prove it useless), and its **firing record** (when it last actually changed behavior — the input to pruning). This makes PAEOS-0's evolution rules *structural* rather than aspirational.

### 1.4 Incident

*The representation of failure.* One could try to reduce Incident to "Evidence with refuting polarity," but it resists reduction because it has its own lifecycle that Evidence lacks: `captured → mined → resolved` — an Incident is *open* until the Steward has either derived an Amendment from it or recorded why no rule is warranted. Failure-driven derivation requires failures to be trackable debts, not passive records. That lifecycle is what earns Incident its place as a primitive. The Sentium excavation output is the seed population of this table.

### 1.5 Decision

*The representation of founder judgment.* Forced by A4: four inputs are irreplaceably the founder's, so the kernel needs exactly one object for requesting them. A Decision contains the question, the options with an agent recommendation, the router classification that triggered escalation, and a resolution. The kernel invariant that makes PAEOS-0's "interventions become policy" real: **a Decision cannot close without either producing an Amendment or recording an explicit one-off justification.** The Decision queue is the founder's entire synchronous interface to the system — the founder ABI (§7).

### 1.6 Amendment

*The representation of change to the rules.* The only mutation path for Policy. An Amendment binds: the Policy delta, the motivating Incident(s) or tournament Evidence, and its own evidence spec ("we'll know this amendment worked if…"), which makes every rule change itself falsifiable and reversible. Amendments are how the constitution stays alive without becoming an accretion: they can *remove* as well as add, and pruning passes are Amendments like any other.

### 1.7 Rejected primitives

- **Plan** → a Goal decomposition plus aggregation contract. Prose plans are exactly what PAEOS-0 abolished.
- **Task** → a leaf Goal.
- **Review** → Evidence produced by an Adversary stance.
- **Report / Doc / Memory** → artifacts in the store; no special type needed. The store *is* the memory (A2).
- **Agent** (as persistent entity) → not an object at all; a process (§3). Persisting agents would accumulate hidden state, violating crash-only.
- **Team / Org** → a Protocol's role-and-parallelism specification.
- **Roadmap** → an ordering over the Goal tree.
- **Runtime / Adapter** → deliberately *outside* the kernel; the kernel defines only the contract they satisfy (§6).

Six objects, four of which (Goal, Evidence, Incident, Decision) are about the work and two (Policy, Amendment) about the rules — the minimal ontology for a system that must both act and evolve.

## 2. The evidence lattice — the kernel's type system

Every Goal's status is a position on one lattice:

```
declared → speculated → executed → verified → integrated
                ↘         ↘          ↘
                    failed (with Incident)
```

- **declared**: spec exists, no work products.
- **speculated**: candidate artifacts exist, unexecuted. (Parallel candidates coexist here — this is where tournaments live.)
- **executed**: artifacts ran; success is self-reported by their builder.
- **verified**: the goal's evidence spec is satisfied by *independent* evidence — produced by a different stance than the builder's (A3; self-verification is correlated with the error it's checking for).
- **integrated**: merged into the trunk world-state; contributes to the parent's aggregation contract.

Two transition rules are kernel invariants: **promotion only via Evidence** (never by assertion, never by seniority of the asserting agent), and **automatic regression on evidence expiry** (§1.2). The lattice is why linear phases never return through the back door: nothing about it is temporal. A goal can sit at `speculated` with three rival candidates while its sibling is `integrated`; a `verified` goal can silently regress to `executed` when a dependency changes. State, not schedule.

## 3. Agents — processes, not entities

From crash-only: an **agent is an ephemeral process** — `(Role × compiled context) applied to one kernel object` — that reads artifacts, writes artifacts, and dies. It holds nothing the store doesn't hold. Killing any agent at any moment loses zero information; the Router simply re-dispatches. What persists is the **Role**, a Policy artifact defining a stance.

The roles are derived from what reconciliation structurally requires, not from human job titles — and stances, not domains, because A3 says stance diversity is what decorrelates errors. Seven are irreducible:

1. **Router** — classifies a goal (verifiability × reversibility), selects the Protocol, dispatches. Required because the router-not-pipeline principle needs an executor.
2. **Decomposer** — turns a non-leaf Goal into children plus an aggregation contract. Required by Goal recursion. (What people call "Chief Architect" is the Decomposer operating on high-altitude goals — same stance, bigger object.)
3. **Builder** — moves objects `declared → speculated → executed`. The generative stance.
4. **Adversary** — attempts to *falsify*: constructs failing inputs, audits intent conservation, attacks decompositions. Produces refuting-or-surviving Evidence. Required by A3: verification must be adversarial and independent, or it's theater. ("Researcher" and "Scout" reduce to Builder/Adversary stances applied to knowledge-goals — evidence about the outside world — not separate roles.)
5. **Judge** — selects among parallel candidates; renders verdict Evidence. Required wherever tournaments run, and by A1: selection is the cheap way to spend verification budget.
6. **Integrator** — merges `verified` work into trunk, **single-threaded per trunk**. Required by PAEOS-0's finding that architectural coherence is precisely the property that fragments under parallelism. The Integrator is the one place concurrency is forbidden by design.
7. **Steward** — runs the evolution loop: mines Incidents, drafts Amendments, runs pruning passes, maintains the firing records. Required by no-rule-without-a-scar; without a Steward, the constitution is write-only and dies by accretion.

Note what is *not* a role: the **Compiler**. Context assembly — Constitution + Role + trigger-matched Skills + the Goal + linked artifacts + live Evidence, within a token budget — is a *deterministic function*, not a judgment call. Making it mechanical is what makes prompts compiled-not-written enforceable rather than aspirational. And the **Founder** is not a role inside the system; the founder is the system's *environment* (§7).

Every specialized agent anyone will ever propose ("security reviewer," "performance engineer," "UX critic") is one of these seven stances plus a Skill bundle. Stances are the instruction set; Skills are the libraries.

## 4. Goal propagation — founder intent to a hundred tasks

The mechanism is **recursive reconciliation**, and it needs no orchestrator:

1. The founder writes the **root Goal** — desired delta, evidence spec, constraints. This is the founder's largest single act.
2. The Router finds a `declared` goal too large for one loop → dispatches a Decomposer.
3. The Decomposer emits child Goals, each with its own evidence spec, its inherited constraints, and its **serving-clause citation** into the parent — plus the aggregation contract.
4. Decomposition is itself work, so it goes through the matrix like anything else: it is hard-to-verify and expensive-to-reverse, which routes it to the ceremony quadrant — adversarial critique of the decomposition, tournaments between rival decompositions at high altitude, and a founder Decision only at the topmost, most irreversible splits.
5. Recursion continues until every frontier goal is a leaf. Leaves dispatch to Builders under their quadrant's Protocol. Verified leaves roll up through aggregation contracts; parents promote when their contracts are satisfied.

Unattended recursion drifts, so two mechanical safeguards (both Adversary duties, both producing Evidence):

- **Intent conservation audit**: every goal must cite the parent clause it serves; the audit walks the tree hunting *orphans* (goals serving no clause — scope creep made visible) and *gaps* (parent clauses no child serves — silent underdelivery). Any leaf task is answerable in one traversal: *why does this exist?*
- **Constraint monotonicity**: children may tighten inherited constraints, never loosen them. Loosening requires a Decision — because relaxing a founder constraint is precisely an A4 event.

This is how "founder goal → 100 implementation tasks" happens with the founder touching only the root and the few Decisions the matrix genuinely escalates.

## 5. Skills — the userland

A **Skill** is a Policy artifact: *trigger conditions* (matched mechanically by the Compiler against the goal's classification, the artifacts in scope, and the active Role), *procedure*, *composition requirements* (Skills form a DAG; a Skill may require others, and the Compiler loads the closure), plus the mandatory scar, falsifier, and firing record.

Lifecycle, fully determined by PAEOS-0: **born** from an Incident via Amendment (never from "this seems like a good practice" — that's how bloat enters); **versioned** in git like everything else, with the compiled context recording exact versions used, so any outcome is attributable to the Skill versions that produced it — which is what makes tournaments *between Skill versions* possible; **evolved** by those tournaments; **pruned** when the firing record goes quiet or the falsifier fires. **Owned** by the Steward — no other role may amend userland, which prevents Builders from quietly rewriting the rules they're governed by.

Skills are always lazily loaded. Nothing enters the Constitution because it's important; things enter the Constitution only if *every* compiled context needs them. The minimality budget is enforced at the kernel/userland boundary, mechanically.

## 6. The narrow waist — runtime abstraction

Like the syscall boundary or LLVM's IR, PAEOS's portability comes from a deliberately tiny contract. Derive what an agent-process minimally needs, and you get **four syscalls**:

1. **READ** — query artifacts from the store.
2. **WRITE** — append artifacts (including Evidence, Incidents, Decisions).
3. **EXEC** — run an executable check and capture its output as observation.
4. **SPAWN** — instantiate a Role with a compiled context; collect its artifact deltas.

That is the entire kernel-runtime interface. Everything a modern runtime offers beyond it — subagent orchestration, MCP servers, hooks, IDE integration — is an optimization an adapter **may** exploit and the kernel **must not** require. SPAWN degrades gracefully by design: a runtime with no subagent support implements it as sequential self-invocation; slower, semantically identical. This degradation rule is what makes "Claude Code today, Orca-strator tomorrow" a configuration change instead of a migration.

An **adapter** is then two thin translations: the four syscalls onto the runtime's capabilities, and the compiled context *lowered* into the runtime's native instruction format (CLAUDE.md, .cursorrules, AGENTS.md, …) — generated artifacts, never handwritten, exactly as LLVM lowers IR to a target. **Conformance is a test, not a claim**: a reference Goal in the repo that must reach `verified` on a candidate runtime using only the four syscalls. Passing it is what "PAEOS runs here" means. Any behavior that can't survive conformance on two runtimes is, by definition, adapter content — the kernel stays clean by CI, not by discipline (A6).

## 7. The founder ABI

The founder interfaces with PAEOS through exactly four channels, matching A4's four irreplaceable inputs:

- **Intent**: authoring root Goals and their constraints.
- **Taste**: a maintained *taste corpus* — judgeable exemplar artifacts ("this is good, that is not, here's why") that Judges cite as ground truth. Taste enters as data, not as interruptions.
- **Ground truth**: injecting external Evidence — user feedback, market signal, money — which the system cannot generate and must treat as the highest-provenance evidence class.
- **Accountability**: resolving the Decision queue — asynchronous, batched, each resolution terminating in an Amendment or an explicit one-off.

Nothing else. If the founder is doing anything outside these four channels, that is itself an Incident: the system has a gap, and the Steward owes an Amendment.

## 8. The two loops

The OS runs two reconciliation loops over the same store. The canonical execution graph (Goal → Architecture → Plan → Task Graph → … → Constitution Update) must not be frozen as *the* OS — that would resurrect the pipeline through the back door; the router exists precisely to skip stations. A reversible, cheaply-verified goal legitimately goes `declared → executed → verified → integrated` with no decomposition, no tournament, no gate. The graph is *emergent* from reconciliation plus routing; only the lattice and the invariants are fixed.

```
WORK LOOP (continuous, parallel)
  unreconciled Goal → Route → [Protocol: decompose | build | tournament | escalate]
     → Evidence → lattice promotion → Integrate (single-threaded) → parent aggregation

EVOLUTION LOOP (continuous, slower)
  Incident / Decision one-offs / firing records → Steward mines
     → Amendment (with its own evidence spec) → [tournament if contested]
     → Policy delta → changes every future compiled context
```

The two loops close on each other: the work loop generates the Incidents and Decisions that feed the evolution loop; the evolution loop rewrites the policies under which the work loop compiles. That closure — policy as data in the store it governs — is what makes PAEOS self-hosting, and it is the whole reason the Constitution can stay small: it doesn't need to anticipate anything, because it can amend.

## 9. Kernel invariants

The complete, numbered set. Each is mechanical (A6: anything less decays).

- **I1 — Evidence-gated promotion.** No status promotes without Evidence satisfying the goal's evidence spec. Assertion is not evidence.
- **I2 — Evidence expiry.** Evidence binds to content hashes; when bound state changes, evidence expires and dependent statuses regress.
- **I3 — Independent verification.** `verified` requires evidence from a stance other than the builder's.
- **I4 — Append-only store.** Artifacts are immutable; change is a new artifact; history is never rewritten.
- **I5 — Crash-only agents.** Any agent, killed at any moment, loses nothing: all state lives in the store.
- **I6 — Compiled contexts only.** No agent acts on instructions that aren't compiled from versioned artifacts.
- **I7 — Scar, falsifier, firing record.** Every Policy carries all three or is rejected; quiet policies get pruning Amendments.
- **I8 — Decisions terminate in policy.** Every founder Decision closes with an Amendment or an explicit one-off record.
- **I9 — Single-threaded integration.** One Integrator per trunk; coherence is never parallelized.
- **I10 — Constraint monotonicity.** Children tighten inherited constraints; loosening requires a Decision.
- **I11 — Narrow waist.** The kernel assumes only READ/WRITE/EXEC/SPAWN; runtime-specific behavior lives in adapters, enforced by the conformance test.
- **I12 — Kernel size cap.** The Constitution has a hard budget; additions displace or pay.

## 10. What is frozen vs. what bootstrap decides

**Frozen (structure):** the six kernel objects and their required fields; the lattice and its two transition rules; the seven roles; the four syscalls; the two loops; invariants I1–I12.

**Open (parameters, to be set empirically during bootstrap — deciding them now would violate the methodology's own tournament rule):** the kernel size cap's number; tournament fan-out N per quadrant; the classification rubric's thresholds; evidence-binding granularity (file vs. hunk); Steward cadence; the Decision queue's escalation defaults.

And the architecture's own first test is already implied by everything above: **PAEOS-1's first root Goal is "build PAEOS," executed under a hand-bootstrapped minimal kernel** — the Sentium excavation mined into the Incident table as the seed corpus, the first Skills derived from those scars, and the first conformance run on Claude Code with a second runtime as the portability check. If the architecture can't govern its own construction, that's an Incident, and the Steward's first Amendment will be to this document.
