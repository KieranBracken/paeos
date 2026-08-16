# PAEOS-9 — Execution Architecture

| | |
|---|---|
| **Artifact** | PAEOS-9 — Execution Architecture |
| **Position in lineage** | The connective layer above PAEOS-7 (Runtime Architecture), PAEOS-7.5 (Threat Model), PAEOS-7.6 (Interface Contracts), PAEOS-8 (Implementation Playbook), PAEOS-8.1 (Runtime Clarifications), and the frozen `operations/ENGINEERING_LIFECYCLE.md` v1.1 (19 states). |
| **Status** | Draft for adversarial ratification (PAEOS-3.5 / CER-1). Not yet sealed. |
| **Type** | **Execution dataflow specification.** Not a runtime redesign; not a re-statement. It is the single document that answers one question end to end: **"How does an engineering task flow through the entire operating system?"** — from *Founder submits task* to *Runtime updates itself and begins the next engineering cycle.* |
| **Governs** | The composition of every existing subsystem into one executable pipeline. It defines *sequencing, dataflow, and boundary hand-offs*; it defines no new invariant, no new lifecycle state, no new agent class, and no new authority. |
| **Does not govern** | The constitution (PAEOS-0…6), the frozen kernel (PAEOS-4 v1.1), the lifecycle definition (v1.1), or any contract in PAEOS-7.6. Where this document appears to conflict with any of them, **they win** (see §0.2, Z-1 precedence). Any real conflict discovered here is a defect in *this* document, to be fixed here — never a license to amend them. |
| **Prime directive inherited** | Correctness over cost (PAEOS-7). Discover the best architecture, never implement the first that works (CER-1). The runtime **hosts** intelligence; it never **contains** it (PAEOS-7 §3.9). |
| **Companion note** | This document **reuses** every mechanism it references and **invents none**. Every arrow in every diagram terminates in a mechanism already specified in the corpus; this document's only new content is the *wiring* between them. |

---

## §0 Framing, precedence, and a numbering advisory

### §0.1 What this document is (and is not)

The constitutional layer answered *what is lawful*. PAEOS-7/7.5/7.6 answered *what the runtime is and why it is safe*. PAEOS-8/8.1 answered *what we build and in what order*. `ENGINEERING_LIFECYCLE.md` v1.1 answered *what the 19 states are*. PAEOS-9-runtime-bootstrap answered *how one session compiles the corpus into an executable context*.

**None of them traces a single task through all of it at once.** That is the gap this document closes. It is the master execution specification: the byte-level-adjacent map a Claude Code worker, an Opus planner, or a second independent implementation team follows to know *which subsystem touches the task next, what it receives, what it emits, and what proves the hand-off was legal.*

It is deliberately a **dataflow** document, not an architecture document. Architecture is frozen upstream. This is the pipeline that runs *on* that architecture.

### §0.2 Precedence (inherited, not re-decided)

This document sits at **tier (d)** of the Z-1 corpus order (PAEOS-8.1 Z-1.1). In descending authority:

```
(a) PAEOS-8.1              — runtime clarifications, for the clauses it names
(b) ratified amendments   — PAEOS-3.5 A-01..A-19, PAEOS-5.5 B-01..B-08 + pins SC-13..SC-24,
                            the PAEOS-7 series, and PAEOS-7.5 A-1..A-10
(c) PAEOS-4 v1.1          — the frozen kernel (canonical build target, per Z-1.3)
(d) all other documents   — operational doctrine, playbooks, AND THIS DOCUMENT
```

Consequently: the **kernel lattice governs promotion** (G-1.3); the **19 operational L-states are metadata layered over the lattice** (G-1.1), never a parallel FSM; the **four-tuple transition contract** (PAEOS-7.6 §4) is the only legal state change; and every claim in this document is subordinate to the contracts in PAEOS-7.6 and the invariants in PAEOS-7.5 §5. Where this document draws a pipeline, the pipeline is an *ordering of already-legal transitions*, nothing more.

### §0.3 Numbering advisory (a surfaced contradiction, not a silent resolution)

The repository already contains `spec/PAEOS-9-runtime-bootstrap.md` — the **session-scope context compiler**. This document also claims the number 9. Per the compiler discipline the corpus itself mandates (*"the compiler never guesses a winner; a residual contradiction ⟹ COMPILE_FAILURE + incident"*, PAEOS-9-bootstrap §2.2), this document **does not silently overwrite or supersede** the bootstrap.

The two are **complementary, not competing**:

- **PAEOS-9 (Runtime Bootstrap)** — *vertical*, one session: corpus → `compiled_context` → worker prompt. The **entrypoint** every worker runs before work begins.
- **PAEOS-9 (Execution Architecture)** — *horizontal*, one task's whole life: Founder → … → self-update. The **pipeline** the whole system runs.

The Execution Architecture **consumes** the Bootstrap as its per-stage context step (§4.6, §11.3). No content of the bootstrap is changed.

> **Founder resolution (ratified 2026-07-21).** The number is resolved cleanly and canonically:
> - **PAEOS-9 — Execution Architecture** (this document) is the canonical entry in the main constitutional sequence: `spec/PAEOS-9-execution-architecture.md`.
> - **PAEOS-9A — Runtime Bootstrap** is a **supporting implementation document**, not a main-sequence artifact: rename `spec/PAEOS-9-runtime-bootstrap.md` → `spec/PAEOS-9A-runtime-bootstrap.md` and retitle its heading `# PAEOS-9A — Runtime Bootstrap Architecture`.
>
> This keeps the canonical numbering unambiguous: the 9-slot is the Execution Architecture; the bootstrap is its `9A` supporting appendix. No content of the bootstrap changes — only its number/filename. The rename is a mechanical L19 housekeeping edit on a non-kernel operational document (touches no invariant, no lattice, no authority); it does not require the hard loop. **Corpus references to update on rename:** the Load Manifest slot 03 note and any `PAEOS-9-runtime-bootstrap` cross-references. Throughout the rest of *this* document, "PAEOS-9-bootstrap" / "the Bootstrap" denotes **PAEOS-9A**.

### §0.4 The two lifecycle numberings, reconciled once (used everywhere below)

Two numbering systems exist in the corpus. They are the **same lifecycle** seen from two layers; this document uses both and binds them here so no reader diverges:

| Layer | Identity | Count | Source | Role in this document |
|-------|----------|-------|--------|-----------------------|
| **Operational L-states** | `L01…L19` | 19 | `ENGINEERING_LIFECYCLE.md` v1.1 (frozen) | The **canonical spine** of the pipeline (§8). Metadata over the lattice (G-1). |
| **Runtime `StageId`** | `RAW, RE_DERIVE…RESTART` | 21 (RAW + 20) | PAEOS-7.6 §3 | The **machine constants** the kernel/ledger/traces record. |
| **Kernel lattice** | `declared → speculated → executed → verified → integrated` | 5 | PAEOS-4 v1.1 §3 | The **authoritative promotion states** (K1, T1–T6). Governs on any disagreement (G-1.3). |

The binding (G-1.2, extended with the PAEOS-7.6 constants) is fixed:

```
L01 Intake                 → StageId INTAKE               → lattice declared
L02 Triage                 → StageId TRIAGE              → lattice declared
L03 First-Principles       → StageId RE_DERIVE           → lattice declared
L04 Ambitious Ideation     → StageId IDEATE              → lattice declared
L05 Frontier Research      → StageId RESEARCH            → lattice declared
L06 Trade-off Analysis     → StageId TRADEOFF           → lattice declared
L07 Trade-off Mitigation   → StageId MITIGATION         → lattice declared
L08 System Design          → StageId DESIGN             → lattice declared
L09 Multi-Perspective Crit.→ StageId CRITIQUE           → lattice declared
L10 Adversarial Review     → StageId ADVERSARIAL_REVIEW  → lattice declared (design-time verdict)
L11 Formal Planning        → StageId PLAN               → lattice declared
L12 Branch Implementation  → StageId IMPLEMENT          → lattice speculated → executed
L13 Verification           → StageId VERIFY             → lattice executed → verified
L14 Independent Audit      → StageId (VERIFY/ADV_REVIEW) → lattice verified (decorrelated gate)
L15 Documentation & Ledger → StageId LEDGER_SYNC        → lattice verified → integrated
L16 Promotion Decision     → StageId SEAL               → lattice integrated
L17 Retrospective + CER    → StageId RETROSPECT         → evolution loop (not the goal's status)
L18 Knowledge Extraction   → StageId EVOLVE/MEMORY_UPDATE→ evolution loop
L19 Constitutional Evolution→ StageId IMPROVE_RUNTIME/RESTART → evolution loop
```

Two operational-vs-runtime asymmetries are deliberate and resolved by G-1.3 (kernel lattice governs):

1. **Re-derivation position.** PAEOS-7 lists `RE_DERIVE` as stage 0 (before intake); the operational spine runs L01 Intake → L02 Triage → L03 Re-Derivation. *Resolution:* re-derivation is **per-run**, gated by ceremony depth (Trace-B only, §8.3). L03 is its canonical operational slot; `RE_DERIVE` as "stage 0" is the runtime's re-derivation-first framing of the same act. No goal is re-derived before it is admitted.
2. **Adversarial review position.** The operational spine runs adversarial review **twice** — L10 (design-time, before build) and L14 (implementation-time independent audit) — whereas PAEOS-7's chambers show a single `ADVERSARIAL_REVIEW` after `VERIFY`. *Resolution:* both are the **same separated power** (MR) invoked at two points; §7.4 and §8 model both explicitly. Independence is constructed identically at each (IBM bundle, decorrelated model family, A-08).

Everywhere below, an L-state is written `L0n` and its lattice effect is named when it matters.

---

## §1 Overall Execution Philosophy

Five principles are load-bearing for the entire pipeline. Each is a restatement of an existing constitutional or architectural commitment, made operative for dataflow. They are not aspirations; every later section is derivable from them.

### §1.1 The lifecycle *is* the operating system

An operating system is not its scheduler, its filesystem, or its syscall table — it is the **discipline** those enforce: that no process acts without permission, that every resource is accounted, that failure is contained. In PAEOS the analogous discipline is the **19-state lifecycle**: the rule that *no artifact reaches Implementation without passing every prior state, and no state closes without evidence* (`ENGINEERING_LIFECYCLE.md`, the spine; K1).

The lifecycle is therefore not *a program that runs on* the OS — it **is** the OS's system-call interface. "Advance a goal from L08 to L09" is the PAEOS equivalent of `write()`: a privileged operation, permission-checked, evidence-gated, ledgered. Everything else in this document — compiler, graphs, workers, stores — exists to **service** lifecycle transitions, exactly as memory management, drivers, and files exist to service syscalls. This is why §8 (the state machine) is the structural heart of the document and every other section feeds it.

### §1.2 The runtime merely *executes* — it holds no opinions

The Runtime (PAEOS-7 Z2: orchestrator, dispatcher, agent harnesses, MCP servers, memory) contains **no engineering judgment and no constitutional judgment**. It is a driver. It reads the legal-edge table (`kernel/lifecycle.py`), mints the next Task Package, spawns the worker, collects artifacts and evidence, and presents the four-tuple to the kernel. If the kernel says COMMITTED, it advances; if REMAND/REJECT/QUARANTINE, it routes per §8.6.

The reason is safety, not modesty: the Runtime is **untrusted** (A1/A3 live there, PAEOS-7.5 §4). A driver that formed opinions would be an unaudited decision-maker inside the attack surface. So the Runtime's opinions are *structurally absent* — it cannot promote a goal, cannot write the ledger, cannot seal, cannot grant itself capability. It can only **ask**. Every "decision" the Runtime appears to make is either (a) a lookup in kernel law, or (b) a delegation to a hosted worker whose output is inert until the kernel accepts it (SI-2).

### §1.3 The constitution *governs* — it is compiled, not consulted

Governance in PAEOS is not "the worker should follow the rules." That is the **Sentium scar**: passive documents lose to a full context window (PAEOS-9-bootstrap §0). Governance here is **mechanical**: the constitution is *compiled* into the only context a worker sees (§4), *enforced* by pre-commit rejection (§7 of the bootstrap; the WRITE validator), and *gated* by the kernel on every transition (the four-tuple). A worker does not *choose* to honor a forbidden-file list; it is handed a capability that physically lacks the write scope (T1, SI-1).

The constitution governs the way a CPU's privilege rings govern: not by asking the program to behave, but by faulting when it does not. "Deny-by-default" (FR-4) is the ring-0 boundary made executable.

### §1.4 Workers never own reasoning — they *rent* it, scoped and revocable

A worker (a Claude Code session) is the most intelligent component in the system and the **least trusted with authority**. This is intentional and it is the resolution of the alignment problem at the core of PAEOS: intelligence is powerful, so it is granted *no standing power*. A worker receives a Task Package (PAEOS-7.6 §5) that is a **complete, expiring lease**: this objective, these read/write scopes, these MCP servers, these skills, this budget, these evidence obligations, for this stage of this run, until this TTL. When the stage closes the lease evaporates (§7.2).

The worker owns its *reasoning* — how to design, how to build, how to attack — but never owns the *consequences*: it cannot decide that its reasoning was correct. Only evidence the kernel re-runs (T2) can decide that. "The worker never owns reasoning" is precise: it never owns the **adjudication** of its reasoning. Build and verdict are different powers, held by different sessions, enforced by construction (MR, SI-3).

### §1.5 Intelligence is *hosted*, not *embedded*

An OS does not know how to render a photograph; Photoshop does. The OS gives Photoshop memory, files, scheduling, and permissions. PAEOS is identical: the kernel and runtime know **nothing** about how to design a distributed system, write a validator, or falsify an architecture. That knowledge lives in the **hosted agent layer** (Claude Code + Skills), which is *not a codebase PAEOS owns* (PAEOS-7 §3.9).

This is the difference between a system that *contains* a fixed intelligence (and rots as the intelligence dates) and one that *hosts* whatever intelligence is current. When a better model ships, PAEOS does not change — the host does. When a method improves, a **skill** changes (a versioned artifact, soft loop), not kernel code. The consequence for dataflow: at every stage the pipeline **injects context and collects artifacts** across a hosting boundary; it never calls an internal "design function." The boundary is the Task Package in, the Task Result out (§6, §7). Everything between is rented cognition.

> **The philosophy in one sentence:** *PAEOS is a permission-and-evidence machine that schedules the 19-state lifecycle, compiles the constitution into every worker's context, hosts (never embeds) the intelligence that does the work, and lets nothing become canonical except by evidence the kernel itself reproduces.*

---

## §2 Complete System Dataflow

The end-to-end pipeline, from founder submission to the runtime beginning its next cycle. The example in the brief is a linear sketch; the real dataflow is a **governed graph with three trust zones, evidence back-pressure at every gate, and two learning loops that feed forward into the next task's context.** Read this section as the map; §3–§11 are the territory.

### §2.1 The canonical pipeline (one task, full ceremony / Trace-B)

Legend: `│` sequential flow · `╞═` a kernel-gated transition (four-tuple required) · `⟲` a feedback edge · `[Zn]` trust zone · `⌂` a persisted write.

```
 FOUNDER  ─ submits task (idea | bug | research | improvement | incident)     [Z2 surface]
    │
    ▼
 INTAKE SURFACE (cli/paeos.py create-goal ; Phase 1: file/API/incident)        [Z2]
    │  emits Goal(kind=work|incident) in lattice `declared`                    ⌂ ledger, goals
    ▼
 ┌─────────────────────────── PER-STAGE LOOP (repeats for every L-state) ──────────────────────────┐
 │                                                                                                   │
 │  (a) KERNEL open_stage(goal, run, stage)  ── mints TaskPackage + CapabilityToken   [Z1 kernel]    │
 │           │                                                                                        │
 │  (b) CONTEXT COMPILER (§4)  ── corpus + graphs → RuntimeContext, content-hashed    [Z2, det.]     │
 │           │   pulls: applicable rules · lifecycle position · contracts · architecture ·           │
 │           │          scars · prior reviews · evidence · repo knowledge · skills · prompts ·       │
 │           │          MCP tools · permissions · task history · dep/goal/rule/arch/impl graphs      │
 │           ▼                                                                                        │
 │  (c) TASK PACKAGE COMPILER (§6)  ── RuntimeContext + stage → deterministic worker package [Z2]    │
 │           ▼                                                                                        │
 │  (d) WORKER RUNTIME (§7)  ── spawn Claude Code (role+skills+scope+MCP allow-list)  [Z2 sandbox]   │
 │           │   worker reasons; reads via MCP; writes only in scope; produces artifacts + evidence  │
 │           ▼                                                                                        │
 │  (e) ARTIFACTS + EVIDENCE → CAS ; AgentTrace → ledger                              ⌂ CAS, ledger  │
 │           ▼                                                                                        │
 │  (f) GATE & EVIDENCE (§8 gate table)  ── kernel checks four-tuple; RE-RUNS deterministic evidence │
 │           │                                                                          [Z1 kernel]  │
 │        ╞═ pass  → TransitionCommitted ; next stage `Pending`                       ⌂ ledger        │
 │        ╞═ fail  → Remand ⟲ (earlier stage)  |  Reject (+scar)  |  Quarantine (human)  |  Abort     │
 │                                                                                                   │
 └───────────────────────────────────────────────────────────────────────────────────────────────┘
    │  (the loop walks the spine)
    ▼
 SPINE (L-states, lattice effect in parentheses):
   L01 Intake(declared) │ L02 Triage(declared, sets ceremony depth + weight class)
   ⟶ [Trace-A auto-discharges L03–L11 with evidence stubs] ⟶
   L03 Re-Derivation │ L04 Ideation │ L05 Research⟲ │ L06 Trade-offs │ L07 Mitigation │ L08 Design
   │ L09 Multi-Persp. Critique │ L10 Adversarial Review (design verdict; gate) │ L11 Formal Plan (freeze)
   ⟶ L12 Implement (speculated→executed, isolated worktree) │ L13 Verify (executed→verified, kernel re-run)
   │ L14 Independent Audit (decorrelated; gate) │ L15 Doc & Ledger (verified→integrated)
   │ L16 Promotion/Seal (integrated; single-threaded merge, K8)
    │
    ▼
 SEAL ── idempotent Ed25519 SealRecord over (artifact_bundle + verdict + adversary + ledger_head)  ⌂ ledger
    │
    ▼
 ┌──────────────────── EVOLUTION LOOP (L17–L19) — runs on every task, success OR failure ───────────┐
 │  L17 Retrospective + Constitutional Review (CER-4) ── root cause ; the 6 CER questions   ⌂ ledger │
 │        │                                                                                            │
 │        ├─▶ MEMORY: write SCAR + detection signature (FR-6)   ⌂ scars   ── SOFT LOOP                │
 │        │        └─▶ becomes an ACTIVE GUARD injected at L03/L08/L09/L13 of FUTURE tasks (⟶ §4)    │
 │        ├─▶ L18 Knowledge Extraction ── skill/template/pattern (versioned)   ⌂ skills   ── SOFT     │
 │        ├─▶ PROPOSAL ENGINE (CER-2) ── proposals/PAEOS-IP-NNNN (never auto-applied)   ⌂ proposals   │
 │        ├─▶ DEBT LEDGER (CER-3) ── ledger/debt/DEBT-NNNN   ⌂ debt                                    │
 │        └─▶ L19 Constitutional Evolution ── IF kernel/lifecycle/authority touched:                  │
 │                    ══════ HARD LOOP ══════                                                          │
 │                    proposal ⟶ full lifecycle run ON the proposal (self-hosting, FR-9)              │
 │                              ⟶ Adversarial Ratification of the safety-invariant DIFF (PAEOS-3.5)  │
 │                              ⟶ MANDATORY human ratifier signature (FR-2, non-delegable)           │
 │                              ⟶ sealed amendment → new frozen kernel version   ⌂ constitution/     │
 └───────────────────────────────────────────────────────────────────────────────────────────────┘
    │
    ▼
 RUNTIME SELF-UPDATE & NEXT CYCLE (L19 → RESTART):
    • recompiled policy/skills/scars now bind EVERY future Context Compiler run (K5/I6) — the system
      that starts the next task is measurably different from the one that finished this one
    • scheduler (Phase 3 RESTART) pulls the next goal whose dependencies are `integrated`
    • ⟲ back to INTAKE SURFACE for the next task
```

### §2.2 Why this is more rigorous than a linear pipeline

The brief's sketch (`Founder ↓ Intake ↓ … ↓ Lifecycle Re-execution`) is a *happy-path list*. The real dataflow has four properties a list cannot express, and every one is load-bearing:

1. **The pipeline is a loop of loops, not a line.** The **outer** loop is the lifecycle spine. The **inner** loop (steps a–f) repeats *at every state* — every state compiles its own context, mints its own package, spawns its own worker, and faces its own gate. The compiler, package compiler, and worker runtime are not stages *in* the pipeline; they are the **machinery each stage runs through**. This is the single most important structural correction: *Context Compiler / Task Package Compiler / Planner / Builder / Verifier are not sequential peers of Intake and Seal — they are the per-stage substrate the whole spine executes on.*

2. **Evidence flows backward as gates, not just forward as data.** Every `╞═` is back-pressure: the gate can **remand** the goal to an earlier state (§8.6). The pipeline therefore has cycles by design (L13→L12 rebuild, L14→L12 audit findings, L10→L08 redesign, capped by SI-9 progress guarantees). A defective task does not fall off the end; it is pushed back until it is correct or rejected — and a rejection *still writes a scar* (a reject is a lesson, PAEOS-7 §4.4).

3. **Three trust zones are crossed on every inner loop.** `open_stage` and the gate are **Z1 (kernel)**; the compiler, package compiler, and worker are **Z2 (untrusted)**; the worker's sandbox is a *further* isolated Z2. Data crossing Z2→Z1 is never trusted without a capability + validation (PAEOS-7.5 §4). The dataflow is thus not just a sequence of *functions* but a sequence of *trust-boundary crossings*, each one a kernel call.

4. **The exit feeds the entrance.** The final act (L17–L19) does not merely close the task — it **mutates the context of every future task**. Scars become guards, skills become methods, amendments become law, all consumed by the next Context Compiler run (§4.7). The system is a control loop whose plant is *itself*: "begins the next engineering cycle" means *begins it as a changed system.* This is FR-9 (self-hosting) expressed as dataflow.

### §2.3 The fast path (Trace-A) is the same pipeline, compressed — never skipped

Most tasks are routine. Triage (L02) assigns **ceremony depth** from verifiability × reversibility (kernel router `v × r`). Trace-A **auto-discharges** L03–L11 and L17–L18 — but *auto-discharge ≠ skip*: each auto-discharged state still emits an evidence stub `{result: auto_pass, reason: trace_a, by: runtime}` so **every transition remains four-tuple-valid** and the ledger remains a complete, replayable record (`WORKFLOW_STATE_MACHINE.yaml` ceremony rule). The load-bearing states — L01, L02, L12–L16, and L19-on-trigger — always execute in full. The pipeline shape is invariant; only the *cost* of the front-end contracts. This is how the router principle (most work is trivial) and the spine (every artifact is routed) both hold at once, and it is the primary economic control (§13.8).

---

## §3 Execution Layers

Twelve layers. This is the *dataflow* decomposition (who does what to the task as it moves), and it maps onto — does not replace — PAEOS-7's nine architectural layers and three trust zones. For each layer: **Purpose · Responsibilities · Inputs · Outputs · Dependencies · Failure modes · Authority.** "Authority" is stated in the only terms that matter: what the layer may cause to become canonical, and by what mechanism it is prevented from more.

The layers stack; a task descends the stack at each state and the results ascend it. Trust **decreases** downward from the constitution and **outward** from the kernel.

### §3.0 Layer stack (at a glance)

```
 ┌────────────────────────────────────────────────────────────────────────────┐
 │ L-A  FOUNDER LAYER            authority source; task origin; amendment gate   │ [human]
 ├────────────────────────────────────────────────────────────────────────────┤
 │ L-B  CONSTITUTION LAYER       frozen law, served read-only                    │ [Z0]
 ├────────────────────────────────────────────────────────────────────────────┤
 │ L-C  LIFECYCLE LAYER          the 19-state spine + lattice mapping (the "ISA") │ [Z1]
 ├────────────────────────────────────────────────────────────────────────────┤
 │ L-D  EXECUTION LAYER          kernel reference monitor: gates, capability,     │ [Z1]
 │                               four-tuple, seal, single-writer ledger append    │
 ├────────────────────────────────────────────────────────────────────────────┤
 │ L-E  CONTEXT LAYER            Context Compiler + graphs → RuntimeContext        │ [Z2, deterministic]
 ├────────────────────────────────────────────────────────────────────────────┤
 │ L-F  PLANNING LAYER           L03–L11 cognition: derive, ideate, design, plan   │ [Z2 hosted]
 ├────────────────────────────────────────────────────────────────────────────┤
 │ L-G  IMPLEMENTATION LAYER     L12 build on isolated worktree                     │ [Z2 hosted, sandboxed]
 ├────────────────────────────────────────────────────────────────────────────┤
 │ L-H  VERIFICATION LAYER       L13 the Court: deterministic + mutation, kernel re-run │ [Z2 hosted]
 ├────────────────────────────────────────────────────────────────────────────┤
 │ L-I  REVIEW LAYER             L10/L14 the Adversary + Auditor, behind the barrier │ [Z2 hosted, isolated]
 ├────────────────────────────────────────────────────────────────────────────┤
 │ L-J  MEMORY LAYER             scars, precedents, retros; signature matching       │ [Z2]
 ├────────────────────────────────────────────────────────────────────────────┤
 │ L-K  EVOLUTION LAYER          L17–L19 retro→memory→proposal→(hard loop)           │ [Z2 → routes to Z1/Z0]
 ├────────────────────────────────────────────────────────────────────────────┤
 │ L-L  PERSISTENCE LAYER        ledger · CAS · projections · graph snapshots         │ [spans; write-mediated by Z1]
 └────────────────────────────────────────────────────────────────────────────┘
```

### §3.1 L-A — Founder Layer

- **Purpose.** Originate tasks and hold the one authority the system may never exercise on itself: ratifying constitutional change (FR-2).
- **Responsibilities.** Submit goals; provide market/user/money ground truth the system cannot generate (L05 founder Inject); make founder Decisions at Trace-B gates (L02 reject-of-founder-intent, L07 irreversible accepted-risk, L11 irreversible scope, L16 seal/reject of founder work, L19 kernel change); sign amendments; own signing-key custody and quarantine release.
- **Inputs.** The world (needs, incidents, priorities); the runtime's `HealthReport` and surfaced proposals/debt.
- **Outputs.** `Goal` submissions; Decisions; **ratification signatures**; quarantine releases.
- **Dependencies.** The intake surface (L-D control plane) and the amendment path (L-K → L-B).
- **Failure modes.** Ratifier bottleneck under high amendment volume (PAEOS-7 §10.5 — *intended* throttle, monitor staffing); a deceived/coerced/overloaded ratifier (PAEOS-7.5 §9.2 — out of technical scope, trust anchor not proof); founder-authored intent mis-triaged (mitigated: reject/dormant on founder intent needs founder confirmation).
- **Authority.** **Supreme and singular for constitutional change; deliberately minimal for everything else.** The founder is the root of trust for the first seals (bootstrap trust anchor, PAEOS-8 §13.4) and the only node that can turn a proposal into law. Human load scales with *constitutional events*, not work volume (PAEOS-7 §9.4).

### §3.2 L-B — Constitution Layer

- **Purpose.** Serve the frozen kernel (PAEOS-4 v1.1), lineage, and hidden-assumptions/canary/classifier corpora as **read-only, queryable law**.
- **Responsibilities.** Answer `get_clause/query/lineage` via the `constitution` MCP server; hold the TCB-resident alarms in Z0 (canaries, threat-model invariants, classification rules — PAEOS-7.5 A-1); expose *no* write method (FR-1).
- **Inputs.** Only from `kernel/amendment.py` — the sole Z0 writer, reachable only through the hard loop.
- **Outputs.** Clauses, invariants, precedence order, canary artifacts, classifier rules — to the Context Compiler (§4) and the classifier.
- **Dependencies.** None downward (it is the floor). The whole system depends on it upward.
- **Failure modes.** Lineage tamper (caught: `constitutional-basis.sha256` verified at boot, PAEOS-9-bootstrap B3); a worker loading superseded v1.0 for rules (caught: v1.0 is `EXCLUDE`, v1.1 canonical); the irreducible risk that the *text itself* is wrong (out of scope here — that is PAEOS-6's job).
- **Authority.** **Absolute over what is lawful; zero agency.** It decides everything and does nothing. Its correctness is the root assumption of PAEOS-7.5 §9.1, mitigated only by the small-kernel thesis.

### §3.3 L-C — Lifecycle Layer

- **Purpose.** Define the legal shape of a task's life: the 19 states, their legal edges, their chambers, and their mapping to the lattice. This is the OS's instruction-set architecture (§1.1).
- **Responsibilities.** `is_legal(from, to, weight_class)` (`kernel/lifecycle.py`); expose the per-state gate requirements (§8); enforce that L-states never gate promotion except through the evidence they produce (G-1.1); provide the sub-state engine `Pending → Active → AwaitingEvidence → Gating → {Passed|Failed}` uniformly across all states (`kernel/state_machine.py`, PAEOS-7 §4.2).
- **Inputs.** The current goal state (from projections); the requested edge (from the Runtime).
- **Outputs.** Legal/illegal verdict on an edge; the next state's requirements; failure targets.
- **Dependencies.** L-B (chambers/gates are constitutional); L-L (reads current state from projections).
- **Failure modes.** An illegal edge requested (denied, deny-by-default); a fast-path/full-path mismatch by weight class (caught by the edge table, B0.5); L-state/lattice disagreement (kernel lattice governs, G-1.3).
- **Authority.** **Defines what transitions are *possible*; grants none.** It is a pure table. It cannot advance anything — it only tells the Execution Layer which advances are legal to *evaluate*.

### §3.4 L-D — Execution Layer (the reference monitor)

- **Purpose.** Be the single choke point through which every privileged action passes: the four-tuple check, capability minting, evidence re-run, sealing, and the single-writer ledger append. This is ring 0.
- **Responsibilities.** `propose_transition` (the four-tuple check, PAEOS-7.6 §4); `mint_capability`; `request_attestation` (kernel signs; agents never hold keys, A-5); `request_seal` (idempotent, A-5); `record_event` (single-writer append, SI-6); `classify_change` (static blast-radius, A-2); **kernel re-run of deterministic evidence** (T2); separation-of-powers enforcement on every transition (SI-3).
- **Inputs.** `TransitionRequest` (four-tuple) from the Runtime; capability requests; seal requests.
- **Outputs.** `TransitionResult` (COMMITTED/REMAND/REJECT/QUARANTINE/ABORT); capability tokens; seal records; ledger sequence numbers; signatures.
- **Dependencies.** L-B (law), L-C (legal edges), L-L (ledger/CAS to write), the classifier and canary corpus in Z0.
- **Failure modes.** All **fail closed** (invariant 8, PAEOS-7.6 §11): missing four-tuple element → deny; role relabel → deny (SI-3); stale evidence (`artifact_hash` mismatch) → reject (SI-4); TCB-touching edge → refuse + route to amendment (SI-8); broken chain / escalation attempt → quarantine.
- **Authority.** **The only layer that can make anything canonical.** It is the sole ledger writer, sole capability minter, sole key holder, sole sealer. Its authority is total *and* its size is capped (~20k LOC security budget) precisely because it is total — it is the TCB, defended only by minimization + audit + amendment-gating (PAEOS-7.5 §3).

### §3.5 L-E — Context Layer

- **Purpose.** Transform the raw corpus + the live graphs into the **one authoritative executable context** a worker consumes, and nothing it does not. Fully specified in §4.
- **Responsibilities.** Run `compile_context` (RESOLVE→OVERLAY→DETECT→EXTRACT→BUDGET→RENDER, PAEOS-9-bootstrap §2); pull the applicable slice of every graph (§5); prune the irrelevant (§4.5); emit a content-hashed `RuntimeContext`; enforce freshness (K2 corpus-hash binding).
- **Inputs.** The Load Manifest (corpus state); the goal + stage + weight class; matched scars; the graph snapshots.
- **Outputs.** `RuntimeContext` (content-hashed) → the Task Package Compiler; `content_hash` → boot.log (determinism proof).
- **Dependencies.** L-B (corpus), L-J (scars), L-L (graph projections). Deterministic given its inputs.
- **Failure modes.** `COMPILE_FAILURE` on unresolved contradiction → HALT + auto-incident (never guess a winner); mandatory-tier overflow → COMPILE_FAILURE + K10 violation; stale context → forced recompile (freshness check gates every transition).
- **Authority.** **None over promotion; total over what the worker sees.** It cannot advance a goal, but it decides the worker's entire world — which is why it is deterministic and content-hashed: its power is real, so it is made reproducible and auditable rather than trusted.

### §3.6 L-F — Planning Layer

- **Purpose.** Host the cognition of L03–L11: re-derive from first principles, ideate widely, research on demand, analyze and mitigate trade-offs, design the architecture, and freeze the implementation contract.
- **Responsibilities.** Produce the derivation, candidate set, trade-off matrix, mitigation catalogue, architecture artifact set, and the frozen L11 implementation contract — each a bound CAS artifact that becomes evidence for the next state.
- **Inputs.** Task Packages for the Planner/Researcher/Reviewer roles; matched scars; research dossiers (quarantined, untrusted).
- **Outputs.** Design + plan artifacts; the L11 contract that L12 is bound to (global rule 3: implementation never creates architecture).
- **Dependencies.** L-E (context), L-D (gates), L-I (L09/L10 critique+adversary verdicts feed back), L-J (scars).
- **Failure modes.** Degenerate candidate space (collapse + note); orphan/gap/loosened-constraint in design (redesign or escalate); ambiguous L11 contract (every ambiguity is an incident, global rule 9); unmitigated high-severity risk with no accepted-risk record (blocks L08).
- **Authority.** **May propose architecture; may not build it or bless it.** The Planner cannot write production code, cannot approve its own design (the L10 adversary does), and cannot seal. Architecture becomes real only after the L10 verdict and L11 freeze.

### §3.7 L-G — Implementation Layer

- **Purpose.** Host L12: implement **only** the approved L11 scope on an isolated branch/worktree.
- **Responsibilities.** Produce a working implementation whose commits each reference the L11 contract; run *local* tests; self-report execution (a non-promoting report, X6); take the goal `speculated → executed`.
- **Inputs.** The Task Package for the Builder (write-scoped to the affected files, forbidden-scoped to everything else); the frozen L11 contract; matched scars.
- **Outputs.** Implementation artifacts + a builder execution self-report (evidence for L13, but never self-promoting).
- **Dependencies.** L-E, L-D, L-L (CAS/worktree), git integration.
- **Failure modes.** Scope creep or speculative improvement (rejected pre-commit by the write-mask; drift → incident, A-11); cannot build within budget (cap-overrun incident, A-12). Rollback is cheap by construction: discard the isolated branch (PAEOS-7 §4.5).
- **Authority.** **May write code, in scope, on an island; may not merge, verify, or seal.** Its output is inert until L13/L14 adjudicate it. The Builder physically lacks merge/seal operations in its capability (T1) — not "is told not to," *cannot*.

### §3.8 L-H — Verification Layer (the Court)

- **Purpose.** Host L13: prove correctness on evidence, on the exact artifact, reproducibly.
- **Responsibilities.** Run the ordered checks (compile → lint → unit → integration → simulation → replay → performance); produce **live, signed, independent** evidence bound to `(artifact_hash, env_hash)`; render a verdict citing every claim; present it so the **kernel re-runs deterministic evidence itself** (T2). Take the goal `executed → verified`.
- **Inputs.** The executed artifact + the L11 acceptance criteria (the claims); the evidence plan.
- **Outputs.** Signed execution evidence, test logs, coverage, perf numbers; a verdict.
- **Dependencies.** L-D (kernel re-run + gate), L-L (CAS), the canary corpus (calibration).
- **Failure modes.** Any live refutation → regress + incident (L13→L19/L12); flaky ≠ refutation (Ω-01, repeatability-aware), but flakiness is treated as **evidence-forgery risk** (T2), blocked not retried-until-green; a missed canary → quarantine that config (T8).
- **Authority.** **May adjudicate correctness; may not modify the artifact or invent claims.** It verifies the builder's enumerated claims; it cannot rescue the work by editing it, and it cannot pass a claim the builder never made. Deterministic evidence it "accepts" is re-run by the kernel — so even the Court is not trusted, it is *checked*.

### §3.9 L-I — Review Layer (the Adversary + Auditor)

- **Purpose.** Host the two adversarial powers: L10 design-time adversarial review (falsify the design before build) and L14 independent audit (a different model family hunts faults after verification). Independence is **constructed, not requested** (FR-3).
- **Responsibilities.** Read **only** the IBM-sealed evidence bundle (never builder scratch/reasoning, SI-5); attempt falsification; file blocking dissents with violated-principle · evidence · severity · smallest-amendment (the 3.5/5.5 court format); attack the *evidence itself*, not only the artifact; catch canaries. Run a **different model family** than the builder (decorrelation, A-08).
- **Inputs.** The IBM bundle for the goal; the constitution; the canary corpus.
- **Outputs.** Adversarial report; verdict (RATIFY / RATIFY-WITH-AMENDMENTS / REJECT) at L10; independent audit report at L14; blocking dissents.
- **Dependencies.** L-D (barrier construction, verdict gate), L-B (constitution), the canary corpus in Z0.
- **Failure modes.** Sandbagging / rubber-stamp (zero findings on a complex change → escalation; missed canary → quarantine, T8); shared-blind-spot if only one capable model exists (residual, PAEOS-7 §10.1); collusion attempts (barrier is by construction, not instruction).
- **Authority.** **May block; may not build or bless.** The adversary can halt a seal with a dissent but cannot write a fix (that would destroy independence) and cannot itself seal. It is the only power whose *job* is to say no.

### §3.10 L-J — Memory Layer

- **Purpose.** Turn past failure into present guardrail (FR-6). Serve scars, precedents, retrospectives; perform **detection-signature matching** so a prior failure is injected as active context on any new task that matches.
- **Responsibilities.** `match_scars(signature)`, `get_precedent(id)`, `propose_scar(draft)` (a *gated transition*, not a direct write, T3/A-10); inject matched scars into the Context Compiler at L03/L08/L09/L13; serialize scar writes through the kernel; never delete a scar.
- **Inputs.** Signature queries at compile time (§4); root-cause bundles at scar-creation time (L17).
- **Outputs.** Matched scars + precedents → RuntimeContext (as active guards and as justification for the active rules).
- **Dependencies.** L-D (scar writes serialize through the kernel; guard-actions may not modify a gate/kernel), L-L (scar store).
- **Failure modes.** Poisoning — false broad-signature scar (DoS: a scar matching > θ of the active backlog is quarantined for human review); guard-action that weakens a control (forbidden; routes to amendment); erosion (detectable — scars are never deleted; a signature that stops matching is a ledgered change); retrieval poisoning (signature-match-first deterministic; semantic is augmentation only, T3).
- **Authority.** **May inform every decision; may decide none.** A scar shapes context and can *block via a matched guard* but cannot itself modify a control. It is read-mostly to agents; its writes are evidence-gated like any other transition.

### §3.11 L-K — Evolution Layer

- **Purpose.** Run L17–L19: extract root cause and lessons, update memory and skills (soft loop), and route TCB-touching change to the human-gated amendment path (hard loop). This is the layer that makes PAEOS self-hosting (FR-9) and is therefore the most carefully fenced (PAEOS-7.5 T4).
- **Responsibilities.** Produce the mandatory Constitutional Review (CER-4) with the six questions; write scars (→ L-J) and skills/templates (L18); emit proposals (CER-2) and debt (CER-3) — surfaced, never auto-applied (CER-5); for any kernel/lifecycle/authority/invariant change, run the **full lifecycle on the proposal itself**, subject it to Adversarial Ratification of the *safety-invariant diff*, and require the founder signature (§14.5, FR-2).
- **Inputs.** The sealed (or failed) task's full lineage; incidents; the cumulative-drift metric vs. the frozen baseline (A-3).
- **Outputs.** Constitutional Review; scars; skills; proposals; debt; (only via the hard loop) a sealed amendment → new kernel version.
- **Dependencies.** L-J (memory), L-D (classifier decides soft vs hard, A-2), L-A (founder signature for hard), L-B (amendment writes Z0).
- **Failure modes.** Root cause not found (G-Retro will not close — no silent close); a repeated mistake with no lesson (the meta-failure, Ω-11); misclassification of hard-as-soft (prevented: classification is a kernel function on static blast radius, not the agent's claim, A-2); boiling-frog drift (prevented: cumulative-drift metric forces a hard-loop review, A-3); meta-recursion (bounded: fixed recursion depth + idempotent-fixpoint base case, A-8).
- **Authority.** **May recommend anything; may legislate nothing.** CER-5 is the hinge of the whole system's safety: unlimited critical thinking and proposal generation, zero unauthorized change. It *proposes* kernel changes and *cannot apply* them — Z0 is unwritable to any autonomous path (SI-8).

### §3.12 L-L — Persistence Layer

- **Purpose.** Hold the source of truth and everything derived from it. Fully specified in §9.
- **Responsibilities.** The **ledger** (append-only, hash-chained, single-writer, total order via sequence numbers); the **CAS** (immutable artifacts + evidence, content-addressed); **projections** (goal state, work queues, scar indices, cost counters, and the **graph snapshots** of §5), all rebuildable by replay; referential-integrity-safe GC.
- **Inputs.** Kernel appends (the only writer); CAS puts (kernel-mediated).
- **Outputs.** Read ranges, chain verification, replayed projections, graph queries — to every layer above.
- **Dependencies.** L-D is its only writer. Storage engine: Postgres 16 (ledger + projections + metadata), filesystem CAS (P0/1); interfaces isolate the eventual swaps.
- **Failure modes.** Tamper (chain + externally anchored head, A-9); fork (single-writer identity is a kernel key, T7); projection poisoning (projections verified against ledger hash before any gate use, T7); CAS deletion of referenced content (GC is referential-integrity-safe, SI-6/7); disk loss (backup/DR is a **flagged open item**, must be resolved before rung R3, PAEOS-8 §13.1).
- **Authority.** **Holds everything, decides nothing, forgets nothing.** Nothing is ever hard-deleted (supersession + retention tiers only). Losing a projection is a rebuild, not a data loss — which is what makes the kernel restartable and the system replay-testable.

### §3.13 Layer dependency & data-descent summary

A task **descends** L-A → L-L at each state (submit → law → legal edge → mint capability → compile context → cognition → build/verify/review → memory → evolution → persist) and results **ascend** back to the gate. The strict rule, enforced by construction: **no layer may perform an action reserved to a layer below its trust level.** L-F/G/H/I (hosted cognition) can *produce and propose*; only L-D can *commit*; only L-A can *ratify constitutional change*. Every downward call that mutates state is a kernel call that terminates in an L-L append performed by L-D — the single-writer invariant is the spine of the whole stack.

---

## §4 The Context Compiler

The Context Compiler is the largest subsystem in the execution architecture because it is where the entire corpus, the entire graph state, and the entire failure memory of the system are **collapsed into the one thing a worker sees**. Everything upstream (constitution, lifecycle, contracts, scars) is *potential* context; the compiler decides, mechanically and deterministically, which slice is *actual* for this task at this state — and, just as importantly, discards the rest.

It is defined at session scope by **PAEOS-9 (Runtime Bootstrap)**. This section does not restate that pipeline; it **extends** it from "compile the corpus" to "compile the corpus *and the live graphs and the applicable history* into an executable context for a specific `(goal, run, stage)`." Where the bootstrap compiler is the LLVM front-end (source → IR), the Execution Architecture's compiler is the same front-end **plus a graph-scoped linker** that resolves which symbols (rules, artifacts, scars, contracts) this translation unit actually references.

### §4.1 The contract: request → executable context

```
compile_execution_context(goal_id, run_id, stage, weight_class) -> RuntimeContext
    PURE and DETERMINISTIC given:
      • the Load Manifest (corpus state, hashed)           — WHICH corpus (bootstrap §1)
      • the goal's ledger lineage (its history, hashed)     — WHAT has happened to it
      • the graph snapshots (§5), each content-hashed       — the WORLD state
      • the stage + weight_class                            — WHICH slice is applicable
    GUARANTEE: identical inputs ⟹ identical RuntimeContext.content_hash
               ⟹ identical worker prompt ⟹ identical pre-work behavior (bootstrap determinism)
```

The determinism guarantee is inherited verbatim from the bootstrap: *two sessions months apart over the same world state compile the same context.* The extension is that "world state" now includes the graph snapshots and the goal's lineage, each content-hashed and folded into `corpus_hash` so that a change to any of them invalidates the context (K2 read-set binding, §4.7).

### §4.2 The pipeline (bootstrap's six stages, extended with graph resolution)

```
1. RESOLVE     order the corpus by precedence (Z-1: 8.1 > amendments > v1.1 > rest). Unchanged from bootstrap §2.
2. OVERLAY     apply ratified amendments over frozen text (§9.4 overlay). Unchanged.
3. SCOPE  ◀NEW query every graph (§5) for the sub-graph reachable from THIS goal/stage:
               • rule-graph      → the invariants/CER/global-rules IN FORCE for this stage (not all 11 K's, the applicable ones)
               • lifecycle-graph → current L-state, applicable_states (router), next_gate, lattice status
               • goal-graph      → this goal's serving-clause chain, parent AggregationContract, siblings
               • dependency-graph→ the goals/artifacts this task depends on that are already `integrated`
               • architecture-graph → the components/interfaces this task's scope touches
               • implementation-graph → the files/modules in scope + their forbidden neighbors
               • capability-graph → the role's allowed MCP servers, skills, kernel APIs
               • artifact/evidence-graph → the design, plan, prior artifacts + their bound evidence
               • scar-graph      → scars whose detection-signature MATCHES this goal (L-J match)
               • review/decision-graph → prior critiques, verdicts, dissents, ADRs on this lineage
4. DETECT      cross-check for residual contradiction not separated by precedence ⟹ COMPILE_FAILURE + auto-incident.
               Extended: a graph-sourced fact that contradicts a corpus rule is ALSO a COMPILE_FAILURE (never reconcile silently).
5. EXTRACT     pull the EXECUTABLE subset (invariants, gates, mutation matrix, forbidden lists, evidence specs, the
               task package skeleton) — NOT prose justification (that is SUMMARY-tier: scars, derivation refs).
6. BUDGET      fit to the byte budget: MANDATORY tier (executable subset + in-scope graph facts) NEVER truncated;
               SUMMARY/INDEX truncate first in reverse precedence, each drop ledgered. Mandatory overflow ⟹
               COMPILE_FAILURE + K10 violation (constitution exceeded its own cap) — an incident, never a silent drop.
7. RENDER      emit RuntimeContext + content_hash = HASH(SERIAL(manifest ‖ scoped-graph-digest ‖ body)); F-1 grammar.
```

Stages 1, 2, 4–7 are the bootstrap compiler unchanged. **Stage 3 (SCOPE) is the whole of this section's addition** and is detailed in §4.3–§4.5. The SCOPE stage is what turns a session-scope context loader into a task-scope execution compiler.

### §4.3 How each "applicable X" is determined (the SCOPE stage in full)

For every category the brief enumerates, the compiler resolves it by a **specific, deterministic query against a specific owner** — never by asking a worker to judge relevance (a judging compiler would be the ungoverned intelligence K5/A-05 forbids). The rule is uniform: *relevance is a graph-reachability question with a fixed traversal, not an opinion.*

| Applicable… | Owner (source) | How determined (the query) | Discard rule |
|-------------|----------------|----------------------------|--------------|
| **Constitutional rules** | Constitution (L-B) + rule-graph (§5.1) | Precedence-resolved active set (RESOLVE+OVERLAY), then filter to invariants/CER/global-rules whose *scope predicate* matches this stage (e.g. CER-1 always; K8 only at L16 merge). | Rules whose scope predicate excludes this stage are INDEX-only (loadable on reference), not in the base context. |
| **Lifecycle stage** | lifecycle-graph (§5.12) | The goal's `current_L_state` from projections + `applicable_states` from ceremony depth (Trace-A prunes L03–L11). | Non-applicable states are not rendered; auto-discharged states contribute only their evidence stub. |
| **Runtime contracts** | PAEOS-7.6 (corpus) | The contract(s) governing this stage's transition (four-tuple always; TaskPackage §5; the gate's evidence contract §6). | Contracts for other boundaries are INDEX-only. |
| **Architecture** | architecture-graph (§5.4) | The components/interfaces reachable from this goal's scope (its serving-clause target + declared touch-set). | Components outside the reachable sub-graph are excluded (this is the core discard, §4.5). |
| **Implementation contracts** | implementation-graph (§5) + L11 artifact | The frozen L11 contract for this goal: affected files, forbidden files, acceptance criteria, rollback plan. | Files outside affected/forbidden are neither writable nor loaded. |
| **Scars** | scar-graph (§5.8) via L-J `match_scars` | Signature match against the goal's fingerprint (failure-class, assumption fingerprint, code/arch smell). Deterministic signature match FIRST; semantic augmentation never sole authority (T3). | A scar whose signature does not match is not injected. A scar matching > θ of the whole backlog is quarantined (DoS guard). |
| **Previous reviews** | review-graph (§5) | Critiques/verdicts/dissents whose `target_artifact` is in this goal's lineage, especially any REMAND verdict that sent it back (required reading, §8.6). | Reviews of unrelated goals are excluded. |
| **Evidence** | evidence-graph (§5.7) | Evidence bound (`artifact_hash`) to artifacts in this goal's lineage; the evidence *plan* (obligations) for this stage's gate. | Evidence bound to a superseded artifact hash is excluded (SI-4 stale-binding). |
| **Repository knowledge** | implementation-graph + CAS | Read-scope files declared by the stage's role (e.g. Builder reads `kernel/` + the plan); the Inventory Atlas slice for the touch-set. | Files outside read-scope are not loaded; the worker cannot even see them (capability, not filter). |
| **Coding skills** | capability-graph (§5.5) | The `SkillRef[]` bound to this `(stage, role)` (e.g. `testing@2.1`, `security-review@1.4`), pinned by version. | Skills not in the role's set are un-invokable (invoke_skill checks membership, §9 of 7.6). |
| **Prompts** | corpus (PROMPT_TEMPLATES.md) | The Universal Preamble (verbatim) + the state's template (F-1 render). | No hand-written prompt is ever admitted (K5). |
| **MCP tools** | capability-graph (§5.5) | The `mcp_servers` allow-list for this `(stage, role)` (e.g. `constitution`, `artifacts`, `memory:read`). | Servers not on the allow-list are unreachable (deny-by-default, §8 of 7.6). |
| **Permissions** | capability-graph (§5.5) | The write_scopes/read_scopes + kernel-API operations minted into the CapabilityToken for this stage. | Any operation outside `operations[]` is denied by the reference monitor (SI-1). |
| **Task history** | goal-graph + ledger lineage | The goal's own transition history + AgentTraces (for retrospective/self-improvement mining at L17). | History of unrelated goals is excluded; secret-scrubbed traces only. |
| **Dependency graph** | dependency-graph (§5.3) | The transitive closure of goals/artifacts this task depends on that are `integrated`; a non-integrated dependency blocks dispatch (FP-1). | Dependencies already satisfied contribute only their integrated artifact refs, not their internals. |
| **Goal graph** | goal-graph (§5.2) | The serving-clause chain up to the workload root + the parent AggregationContract (A-1) that this goal discharges. | Sibling sub-trees not on the serving path are excluded. |
| **Rule graph** | rule-graph (§5.1) | The dependency closure of the in-force rules (a rule that cites another pulls it). | Rules not reachable from the applicable set are INDEX-only. |
| **Architectural graph** | architecture-graph (§5.4) | (as Architecture, above) — the reachable component/interface sub-graph. | (as above) |
| **Implementation graph** | implementation-graph (§5) | The file/module/test sub-graph for the touch-set + its forbidden neighbors (the write-mask). | Modules outside the touch-set + neighbors are excluded. |

### §4.4 Output: the RuntimeContext (extended)

The compiler emits the bootstrap's `RuntimeContext` object (PAEOS-9-bootstrap §3) — `content_hash`, `corpus_hash`, `load_manifest`, `task`, `lifecycle`, `authority`, `constitution` (active subset), `forbidden`, `evidence`, `package`, `proposals`, `debt`, `scars`, `active_amendments` — **plus** a `scoped_graphs` block holding the in-scope sub-graph digests from §4.3, each content-hashed. The worker reads this object; it never reads raw markdown, and it never reads a graph directly (it reads the *compiled slice*). If a field it needs is absent, that is a compiler defect (incident), not the worker's problem to improvise around — the same discipline the bootstrap mandates.

### §4.5 How irrelevant information is discarded (the compiler's most important job)

Discarding is not an optimization; it is a **safety and determinism requirement**. Irrelevant context is (a) an attack surface (more text = more prompt-injection room, T9), (b) a determinism risk (unscoped context varies run to run), and (c) a cost multiplier (T6). The compiler discards by four mechanisms, in order of strength:

1. **Capability exclusion (strongest — the thing is unreachable).** If a file, MCP server, or skill is not in the role's capability for this stage, it is not "hidden" — it is **absent**. The worker cannot load `kernel/` if its read-scope excludes it; there is nothing to be tempted by. This is the primary discard: *most of the world is discarded by never being grantable.* (SI-1, T1.)
2. **Graph-reachability exclusion.** Within what is grantable, only the sub-graph reachable from this goal's serving-clause + declared touch-set is scoped in (§4.3). A component the task does not touch, a scar that does not match, a review of another goal — all fall outside the traversal and are never rendered. Relevance is reachability; unreachable is discarded.
3. **Tier demotion.** Grantable, reachable, but not executable-for-this-stage content is demoted from FULL → SUMMARY → INDEX. Justification prose (why a rule exists) is SUMMARY; lineage/derivation is INDEX (loadable on explicit reference). The executable subset (the rule itself, the gate, the forbidden list) stays FULL. This is the LLVM "strip debug info from the hot path, keep it addressable" move.
4. **Budget truncation (last resort, recorded).** If the SUMMARY/INDEX tiers still overflow the byte budget, they truncate in reverse precedence order, **each drop ledgered**. The MANDATORY tier is *never* truncated; if it alone overflows, that is a COMPILE_FAILURE and a K10 violation (§4.2 stage 6) — the constitution has exceeded its own size cap, an incident against the constitution, not a silent drop.

The discard is **auditable and reversible**: because the compiled context is a rebuildable cache (H-08/D1) content-hashed against its inputs, any question of "why wasn't X in scope?" is answered by replaying the SCOPE traversal — the exclusion is a deterministic function of the graph state, not a lossy summarization.

### §4.6 Where the compiler runs in the pipeline

The compiler is **step (b) of every inner loop** (§2.1): after the kernel `open_stage` mints the package skeleton + capability, before the Task Package Compiler (§6) finalizes the worker package. It runs *per state*, not once per task — L03's context and L12's context are different compilations of the same world, scoped to different stages. On the first state it runs the full bootstrap boot sequence (B1–B9); on subsequent states it re-derives the state-scoped fields (authority, evidence, forbidden, next_gate) and re-checks freshness.

### §4.7 Freshness: the compiler feeds forward from the last cycle

The compiler's inputs include the graph snapshots and the goal lineage, so the **learning from the previous task is automatically in scope for the next** (§2.2 property 4). A scar written at L17 of task T becomes a matched-scar injection at L03/L08/L09/L13 of task T+1 — because the scar-graph snapshot's hash changed, the next `corpus_hash` differs, the context recompiles, and the new guard is present. This is FR-6 (a failure becomes a standing guard) realized through the compiler's read-set binding (K2). The freshness check gates **every** transition: a `content_hash`/`corpus_hash` mismatch is a hard stop (recompile), never a warning — it is mechanically impossible to keep acting on a stale world.

---

## §5 Graph Architecture

PAEOS's state is naturally a set of graphs: goals serve goals, rules cite rules, artifacts supersede artifacts, scars guard designs. This section defines every graph, its ownership, and its consistency model. **The unifying principle (do not miss it): every graph is a *projection* of the ledger (L-L), not a primary store.** A graph is a materialized view rebuilt by replay (FR-5); losing one is a rebuild, not data loss. This is what keeps twelve graphs consistent with each other without a distributed-consensus problem — they all derive from **one** totally-ordered, single-writer log (PAEOS-7 §9.1: single logical ledger, CP).

### §5.0 The invariant that governs all graphs

```
ledger (append-only, hash-chained, single-writer)   ── the ONE source of truth (FR-5)
      │  replay / project (deterministic)
      ▼
graph snapshots (goal, rule, dependency, architecture, capability, artifact,
                 evidence, scar, proposal, memory, decision, lifecycle)
      │  each content-hashed; folded into corpus_hash (§4.7)
      ▼
Context Compiler SCOPE stage (§4.3) queries the in-scope sub-graph
```

- **Ownership.** No graph is written directly. Every graph mutation is the *projection of a ledgered event* performed by the kernel (single writer, SI-6). "Update the goal graph" is never an operation; "append `TransitionCommitted`, re-project the goal graph" is.
- **Queries.** Graphs are read via the substrate MCP servers (capability-gated, deny-by-default) or, for kernel-internal needs, via `projections.py`. Workers never query a raw graph — they receive the compiled in-scope slice (§4.4).
- **Consistency.** Because all graphs derive from one totally-ordered log, they are **mutually consistent by construction at any given ledger head**. A graph read is always taken at a specific `ledger_head` (a sequence number); two graphs read at the same head cannot disagree. (T7: projections are verified against the ledger hash before any gate use.)
- **Synchronization.** There is no cross-graph sync protocol because there is no cross-graph write path — synchronization is replay from the shared log. A projection lagging the head is *stale*, detected by head comparison, and rebuilt; it is never *divergent*.
- **Updates.** Incremental (apply the new event to the existing projection) with periodic full-replay verification (the replay/determinism suite, PAEOS-8 §6) proving the incremental view matches a from-scratch rebuild byte-identically.

### §5.1 Rule Graph

- **Nodes:** invariants (K1–K11), CER-1..5, global rules 1–17, ratified amendments, precedence tiers. **Edges:** *cites*, *amends*, *overrides* (precedence), *scoped-to-stage*.
- **Owner/updates:** the Constitution Layer (L-B); mutated only by a sealed amendment (hard loop) re-projecting the graph. **Query:** "which rules are in force at stage L0n?" (§4.3 rule scoping) — a traversal from the stage's scope predicate across *cites* closure. **Consistency:** amendments overlay by precedence (Z-1); a residual contradiction is a COMPILE_FAILURE (never a silent winner). **SAKG:** §10 — SAKG can serve rule-dependency reasoning ("which invariants does this change's blast radius touch?") as augmentation to the classifier (A-2), never as its authority.

### §5.2 Goal Graph

- **Nodes:** goals (`kind=work|incident|decision|amendment`). **Edges:** *serves* (serving-clause chain), *parent-of* (decomposition), *aggregates* (AggregationContract, A-1), *supersedes*.
- **Owner/updates:** the kernel, on every goal event (declare, promote, regress, aggregate T6). **Query:** the serving-clause chain to the workload root; the parent contract this goal discharges; sibling status for aggregation. **Consistency:** a non-leaf goal's `verified` is *defined* by its AggregationContract over children (A-1.3), re-evaluated by the reactor on any child status change (T6) — the graph encodes this rule directly. **SAKG:** goal-similarity retrieval ("has a goal like this been solved?") augments planning, never gates promotion.

### §5.3 Dependency Graph

- **Nodes:** goals + artifacts. **Edges:** *depends-on*, *blocks*, *satisfied-by*. **Owner/updates:** kernel, from declared dependencies + integration events. **Query:** the transitive closure of dependencies that must be `integrated` before this goal may dispatch (FP-1: select exactly one task whose deps are all integrated). **Consistency:** a cycle is illegal (declared dependencies form a DAG; a cycle is an intake defect → incident). **Synchronization:** integration of a dependency re-projects the graph, unblocking dependents for the scheduler (§2.1 next-cycle). **SAKG:** dependency-impact reasoning ("what breaks if this changes?") is a prime SAKG consumption point (§10).

### §5.4 Architecture Graph

- **Nodes:** components, interfaces, data flows, state machines, schemas, storage, APIs (the L08 design artifact set). **Edges:** *calls*, *implements*, *depends-on*, *owns-data*. **Owner/updates:** produced at L08, sealed at L16, superseded by later designs. **Query:** the reachable sub-graph from a goal's touch-set (§4.3 Architecture scoping — the core discard). **Consistency:** intent-conservation audit at L08 (no orphans/gaps); verification seams must be good product boundaries (Ω-24); constraints tightened only (D2). **SAKG:** architectural-tradeoff and pattern reasoning is the richest SAKG consumption (§10) — "what does the SAKG know about designs shaped like this?"

### §5.5 Capability Graph

- **Nodes:** roles, MCP servers, skills, kernel APIs, filesystem scopes. **Edges:** *may-invoke*, *may-read*, *may-write*, *conflicts-with* (separation of powers). **Owner/updates:** the Capability Broker (L-D); minted per session/goal/stage/role, expired at stage close. **Query:** "what may role R do at stage L0n for goal G?" → the exact CapabilityToken content (§6.3). **Consistency:** the *conflicts-with* edges encode MR (Build/Verify/Adversary/Seal are mutually exclusive per goal-run, SI-3); the broker refuses a mint that would violate them. **Failure/authority:** this graph is the reference monitor's teeth; role binding is immutable per (session, goal) — no relabeling (A-6/T1). **SAKG:** not consumed (capability is pure kernel law, never inferred).

### §5.6 Artifact Graph

- **Nodes:** designs, plans, research briefs, code diffs, docs (CAS entries). **Edges:** *supersedes*, *derived-from*, *produced-by-role*, *bound-evidence*. **Owner/updates:** CAS (content-addressed); immutable nodes, append-only edges. **Query:** lineage walk (this artifact's ancestry); by goal; by hash. **Consistency:** immutability is what makes seal (FR-7) and reproducible evidence (FR-4) meaningful — an artifact never changes, it is superseded. **SAKG:** artifact-similarity retrieval augments L18 knowledge extraction.

### §5.7 Evidence Graph

- **Nodes:** evidence (BUILD/TEST/BENCHMARK/PROOF/CITATION/TRACE/MUTATION/CANARY). **Edges:** *proves-claim*, *bound-to-artifact* (`artifact_hash`), *bound-to-env* (`environment_hash`), *attested-by-kernel*. **Owner/updates:** CAS; produced by workers, attested by the kernel (agents never sign, A-5). **Query:** by claim; by gate; reproducibility replay. **Consistency:** the *bound-to-artifact* edge is the SI-4 anti-stale defense — evidence whose binding ≠ the artifact under review is rejected at the gate. Deterministic evidence is kernel-re-run (T2). **SAKG:** not consumed for adjudication (evidence must be reproduced, never inferred); SAKG may *index* evidence for retrieval only.

### §5.8 Scar Graph

- **Nodes:** scars (`failure_class, root_cause, detection_signature, guard_action, severity, origin_run`). **Edges:** *matches* (signature → goal), *guards* (stage), *derived-from-incident*, *supersedes-precedent*. **Owner/updates:** L-J; scar creation is an **evidence-gated transition** requiring a root-cause bundle (A-10); append-only, signed with run provenance; never deleted. **Query:** signature match at L03/L08/L09/L13 (deterministic first, semantic augmentation only). **Consistency:** a guard-action may **not** modify a gate/kernel (those route to amendment, A-10); a scar matching > θ of the active backlog is quarantined (broad-signature DoS, T3). **SAKG:** semantic scar retrieval is an explicit SAKG augmentation — but signature-match remains the authority (§10 degradation).

### §5.9 Proposal Graph

- **Nodes:** `proposals/PAEOS-IP-NNNN` (draft amendment-goals). **Edges:** *proposes-change-to* (rule/component), *supersedes*, *ratified-into* (amendment), *rejected*. **Owner/updates:** the Proposal Engine (L-K, CER-2); surfaced read-only, **never auto-applied** (CER-5). **Query:** open proposals relevant to a task's domain (surfaced in RuntimeContext.proposals); the ratification lineage of an amendment. **Consistency:** a proposal recommends; only a founder-ratified amendment (hard loop) turns a proposal node into a *ratified-into* edge on the rule graph. **SAKG:** proposal-clustering ("many proposals point at the same weakness") augments the Founder's prioritization.

### §5.10 Memory Graph

- **Nodes:** precedents, retrospectives, lessons, skills/templates (L18 institutional knowledge). **Edges:** *precedent-for*, *generalizes* (scar → pattern), *versioned-from*. **Owner/updates:** L-J + L-K; versioned, scarred, falsifiable artifacts (K6). **Query:** precedent retrieval at planning; skill resolution at dispatch. **Consistency:** memory is read-mostly; writes serialize through the kernel. **SAKG:** the richest augmentation surface — SAKG *is* a memory graph at scale (§10); PAEOS's Memory Graph is the local, always-available floor beneath it.

### §5.11 Decision Graph

- **Nodes:** ADR-style decision records (`context, options[], chosen, rationale, constitutional_basis`). **Edges:** *supersedes*, *grounded-in-clause*, *decided-by-role*, *for-goal*. **Owner/updates:** the Documentation role (L-I/Doc); append-only (supersede). **Query:** by goal; by constitutional clause; timeline. **Consistency:** every decision is traceable to a constitutional basis (global rule 11) — an ungrounded decision is an incident. **SAKG:** decision-rationale retrieval augments future trade-off analysis (L06).

### §5.12 Lifecycle Graph

- **Nodes:** the 19 L-states + lattice states + failure states (Remand/Reject/Quarantine/Abort). **Edges:** *legal-transition* (from lifecycle.py), *maps-to-lattice* (G-1.2), *on-fail-routes-to*, *gate-requires* (evidence). **Owner/updates:** the Lifecycle Layer (L-C); frozen except by amendment (the lifecycle is versioned/amendable via L19 on its own document). **Query:** legal edges from the current state for this weight class; the gate + evidence for a transition; the failure target. **Consistency:** L-states never gate promotion except through evidence (G-1.1); the kernel lattice governs on disagreement (G-1.3). **SAKG:** not consumed (the lifecycle is fixed law, never inferred).

### §5.13 Cross-graph query example (how the compiler uses all twelve at once)

For a task at **L12 (Implement)** on goal `g-validator`, the SCOPE stage (§4.3) runs, at one `ledger_head`:

```
lifecycle-graph  : current=L12, next_gate=G-Build→VERIFY, lattice speculated→executed
goal-graph       : serves clause SC-… ; parent contract = all-children-verified
dependency-graph : depends-on {g-types(integrated), g-lifecycle(integrated)} ✓ dispatch allowed
architecture-graph: touch-set = {validator component} ; reachable interfaces only
implementation-graph: write={kernel/validator.py} forbidden={constitution/,schemas/,everything else}
capability-graph : role=BUILDER ; mcp={constitution,artifacts,memory:read} ; skills={testing@2.1,security-review@1.4}
artifact-graph   : context = plan c3f9… (L11 frozen contract) + design 7a2e…
evidence-graph   : obligations = {builds:exit0, unit:reproducible-green} ; no stale bindings
scar-graph       : matched = 9a1b… (a prior validator off-by-one scar) → injected as active guard
review-graph     : L10 verdict RATIFY-WITH-AMENDMENTS(resolved) — required reading
rule-graph       : in-force = {K1, CER-1, global rules 3 (impl≠arch), 6 (independent audit ahead)}
decision-graph   : ADR-… (why this validator design) — SUMMARY tier
```

All twelve reads are at the same head, so they cannot disagree; the compiler collapses them into one content-hashed RuntimeContext; the Task Package Compiler (§6) turns it into the worker's lease.

---

## §6 Task Package Compiler

The Task Package Compiler converts a `RuntimeContext` (§4) into the **deterministic, fully-scoped worker lease** — the concrete instance of PAEOS-7.6 §5 `TaskPackage`. This is the boundary where "the runtime hosts intelligence" becomes a wire format: everything the worker may touch is *in* the package; everything else is unreachable. The package is the executable form of §1.4 (workers rent reasoning, scoped and revocable).

### §6.1 The contract

```
compile_task_package(RuntimeContext, stage, role) -> TaskPackage      (PAEOS-7.6 §5)
    DETERMINISTIC: identical RuntimeContext + (stage, role) ⟹ byte-identical TaskPackage
                   (⟵ inherits §4 determinism; the package is a pure projection of the context)
```

The determinism requirement is not cosmetic. A non-deterministic package would mean two identical world-states dispatch different work — breaking the founder's core guarantee (bootstrap §0). The package is a **pure function** of the RuntimeContext; the only non-determinism permitted downstream is the worker's own reasoning, which is fenced by evidence (K1) so it cannot promote a wrong result.

### §6.2 Package schema (instantiated from PAEOS-7.6 §5, sourced from the graphs)

| Field | Source (which graph/§4 field) | Determinism note |
|-------|-------------------------------|------------------|
| `task_id, goal_id, run_id, stage, role` | RuntimeContext identity + lifecycle-graph | Deterministic ids per (goal, run, stage). |
| `objective` | corpus PROMPT_TEMPLATES + L11 contract | Rendered by F-1 grammar, not hand-written (K5). |
| `capability` (CapabilityToken) | capability-graph (§5.5), minted by L-D | The *authority* — the only privilege the worker has (§6.3). |
| `permissions.write_scopes` | implementation-graph touch-set | Exactly the affected files of the L11 contract. |
| `permissions.read_scopes` | implementation-graph + architecture-graph | The reachable read set for this role/stage. |
| `permissions.mcp_servers` | capability-graph allow-list | Deny-by-default; e.g. `[constitution, artifacts, memory:read]`. |
| `permissions.skills` | capability-graph SkillRefs | Version-pinned (`testing@2.1`); un-listed skills un-invokable. |
| `forbidden[]` | implementation-graph forbidden neighbors | **Documentation of intent; enforcement is by capability, not this list** (T1). |
| `required_evidence[]` (EvidenceObligation) | evidence-graph obligations for this gate | What MUST be produced to pass (FR-4). |
| `context_refs[]` | artifact + scar graphs | Design, plan, and **matched scars** — always on the path (FR-6). |
| `budget` | goal-graph budget slice (K11 conservation) | Per-goal slice of the two-tier budget (A-7). |

### §6.3 Required artifacts, permissions, and the forbidden set

- **Required artifacts (`required_evidence`).** Every package declares the *evidence obligations* that discharge its gate — for L12: `{builds: exit 0}`, `{unit: reproducible green bound to artifact+env}`. No obligation ⇒ nothing to verify ⇒ the stage cannot pass (FR-4). The obligations are copied verbatim from the gate's evidence contract (§8), never invented by the compiler.
- **Permissions (the CapabilityToken).** The single unforgeable authority object (PAEOS-7.6 §7): kernel-signed, bound to `(goal, run, stage, role, session)`, short TTL, explicit `operations[]` allow-list. It is the *only* privilege the worker holds. There is no ambient authority (SI-1): the Builder can write `kernel/validator.py` because the token says `cas:write:kernel/validator.py`, and cannot merge because no `merge` operation is in the token — not because `forbidden[]` lists it.
- **Forbidden files.** The `forbidden[]` array is **advisory documentation of intent**; the *enforcement* is the write-mask derived from the implementation-graph and encoded in the capability. This distinction is load-bearing (T1): a system that enforced by a deny-list would be defeated by an unlisted path; a system that enforces by an allow-list (capability) is safe by default. `forbidden[]` exists so the worker *understands* the boundary; the capability guarantees it *cannot cross* it.

### §6.4 Skills, tool access, evidence, verification, and review requirements

- **Skills.** The version-pinned `SkillRef[]` for `(stage, role)`. Skills are *capabilities the workflow invokes*, not the workflow (PAEOS-7.6 §9): the lifecycle invokes `testing@2.1`; the worker cannot invoke a skill outside its package. The resolved version is recorded in `TaskResult.cost.skill_vers` (drift audit). Changing a skill that alters a gate's *behavior* is classified HARD (A-2) and routes to amendment.
- **Tool access (MCP).** The `mcp_servers` allow-list, deny-by-default (PAEOS-7.6 §8). `constitution` is read-only always; `ledger` never exposes `append`; `memory` exposes `:read` and `:write` as separate grants; `court` submission is inert until the kernel adjudicates.
- **Evidence requirements.** As §6.3 — the obligations that discharge the gate, bound to `(artifact_hash, env_hash)`.
- **Verification requirements.** Which checks the Court (L13) will run and which the kernel will re-run (deterministic evidence is *always* kernel-reproduced, T2). The package tells the Builder what the Verifier will demand, so the Builder produces reproducible evidence up front.
- **Review requirements.** Whether this stage's output faces the independent adversary (L10 for design, L14 for implementation) and under what decorrelation constraint (auditor/adversary model family ≠ builder family, A-08). For a `kernel/`-touching goal, the package flags that a HARD-loop adversary pass + human sign-off gate the eventual seal.

### §6.5 Rollback instructions and expected outputs

- **Rollback instructions.** Every package carries the goal's rollback semantics (PAEOS-7 §4.5), inherited from the L11 plan: **state** rollback = append a superseding event; **artifact** rollback = a new CAS artifact linked `supersedes → old-hash`; **code** rollback (L12) = discard the isolated worktree (cheap by construction); **seal** rollback is impossible — a post-seal defect is a constitutional incident (quarantine + a re-execution goal whose seal supersedes the defective one). The package states which apply to this stage so a failed worker leaves a clean, replayable state.
- **Expected outputs (the output contract).** The exact artifact shape to return, from the state's `produced_evidence` schema: *"return artifacts only; the Runtime gates the transition"* (bootstrap §4.1 §9). The worker returns a `TaskResult` (PAEOS-7.6 §5): `artifacts[]` (to CAS), `evidence[]` (bound), `trace_ref` (immutable transcript), `cost` (tokens, wallclock, model_ver, skill_vers). Nothing the worker returns is canonical until the four-tuple check accepts it.

### §6.6 Why the output is deterministic (and why that matters)

Determinism is guaranteed by three properties, each inherited: (1) the RuntimeContext is content-hashed and deterministic (§4.1); (2) the package is a pure projection of it (§6.1); (3) the render grammar is byte-identical (F-1). Therefore *the same world state dispatches byte-identical work to the worker* — the reproducible-build fingerprint extends from the compiled context all the way to the worker's lease. A package hash mismatch across two identical world-states is a **detected defect**, never silent drift (bootstrap §10). The worker's reasoning is the only non-deterministic element, and it is fenced: its output is inert until evidence the kernel re-runs proves it (K1, SI-2) — so non-determinism can never become canon.

---

## §7 Worker Runtime

The Worker Runtime is where hosted intelligence executes (§1.5). Every worker is a **Claude Code session** dispatched with a Task Package (§6) and returning a Task Result; the `runtime/agents/*.py` harnesses are thin (build package, spawn, parse result) — the reasoning is rented, not owned. This section defines the ten worker archetypes and the protocol every one obeys. The archetypes are **capability profiles, not personalities** (PAEOS-7 §5): a worker *is* what its capability permits, nothing more.

### §7.1 The ten workers (roles × lifecycle × authority)

| Worker | L-states | Lattice effect | May cause to become canonical | Cannot (enforced by capability) |
|--------|----------|----------------|-------------------------------|--------------------------------|
| **Planner** | L03–L08, L11 | declared | Design + plan artifacts; the frozen L11 contract | Write production code; approve its own design; seal; read adversary context |
| **Builder** | L12 | speculated→executed | Implementation on an isolated worktree; local test results | Merge; verify own work; seal; append ledger; read other goals' workspaces |
| **Verifier** (Court) | L13 | executed→verified | A verdict citing kernel-re-runnable evidence | Modify the artifact; invent claims the builder didn't make; see adversary findings |
| **Adversary** | L10, L14 | declared / verified gate | Blocking dissents; RATIFY/REJECT verdicts | Build fixes; see builder scratch; communicate pre-verdict; self-seal |
| **Reviewer** (critic) | L09 | declared | Multi-perspective finding register (7 stances) | Block a seal (pre-review, not a power); masquerade as the adversary |
| **Researcher** | L05 | declared | Research dossiers (**quarantined, untrusted data**) | Have its output trusted as instruction (T9); run unbounded/consumer-less |
| **Documentation** | L15, L17 | verified→integrated (records only) | Ledger-entry drafts, retrospectives, ADRs, scar drafts | Make engineering decisions; change verdicts; be a cross-role channel (barrier-scoped, T1) |
| **Memory** | L17 (write), L03/L08/L09/L13 (match) | — | Scar drafts (via gated `propose_scar`) | Delete a scar; declare a gate/kernel-modifying guard-action (A-10); write directly |
| **Ledger** *(kernel, not an agent)* | all | — | The single-writer append; sequence numbers | Be invoked by any agent (agents emit via `record_event` only, SI-6) |
| **Proposal / Evolution** | L18, L19 | evolution loop | Proposals (CER-2), debt (CER-3), skills (L18); **recommendations only** | Apply any change (CER-5); write Z0; amend without founder signature (FR-2) |

Note the deliberate asymmetry: **Ledger and Memory are not free-acting agents.** The "Ledger worker" is the kernel's single-writer append (there is no agent that writes the log); the "Memory worker" writes only through an evidence-gated transition. Listing them as workers is a dataflow convenience — their *authority* is kernel-mediated, which is exactly why the log and the failure memory cannot be poisoned by a compromised session (T3, T7).

### §7.2 Activation and termination (the lease lifecycle)

- **Activation.** The kernel `open_stage(goal, run, stage)` mints a `TaskPackage` + `CapabilityToken`; the dispatcher (`agent_dispatcher.py`) spawns a Claude Code subprocess with a **scoped workspace** (only the package's `write_scopes`) and an **MCP allow-list** (only `mcp_servers`). Matched scars are injected as context (FR-6, always on the path). The stage sub-state moves `Pending → Active` (PAEOS-7 §4.2).
- **Termination.** A worker terminates on any of: (a) returning a `TaskResult{COMPLETE}` with all evidence obligations met; (b) `FAILED`/`ABANDONED`; (c) TTL expiry of its capability; (d) budget exhaustion (tokens/wallclock/retries). On termination the **capability evaporates** — no long-lived session, no standing authority (PAEOS-7 §5.3). The workspace is torn down; artifacts already in CAS survive (crash-only, D1: if it matters, it was written to the store before session end).
- **Idempotent restart.** Because the ledger is the source of truth and stages are idempotent (PAEOS-7 §9.1), a crashed worker's stage is simply re-opened; partial CAS writes are content-addressed (a re-run produces the same hashes) and no double-advance is possible (the four-tuple gate commits once).

### §7.3 Authority (restated as the separation invariant)

For one goal in one run, **no session holds two of {Build, Verify, Adversary, Seal}** (MR, SI-3), enforced by the Capability Broker, not by instruction. Role binding is **immutable per (session, goal, run)** — a Builder token can never be relabeled a Verifier token (A-6/T1). The critic (Reviewer, L09) is deliberately *not* one of the separated powers: it is cooperative, builder-side, pre-judgment — its job is to *improve* the work before the independent powers judge it.

### §7.4 Handoff protocol (the only channel between workers is the kernel)

Workers never talk to each other. Every handoff is **mediated by the kernel through the ledger + CAS + the Information-Barrier Manager (IBM)**:

```
Builder ──produces──▶ CAS(artifact) + Evidence(bound) ──▶ [kernel gate G-Build]
                                                              │ commits VERIFY-pending
Kernel ──IBM constructs sealed bundle──▶ Verifier (sees artifact+claims+evidence, NOT builder scratch)
Verifier ──verdict──▶ [kernel gate G-Court] ──▶ IBM constructs adversary bundle
Kernel ──IBM sealed bundle only──▶ Adversary (sees evidence bundle, NOT builder OR verifier reasoning, SI-5)
Adversary ──dissent|clear──▶ [kernel gate G-Adversary] ──▶ Seal Authority (only if verdict passes + no blocking dissent)
```

The IBM (a kernel component, Z1) is what makes independence *constructed, not requested* (FR-3): the adversary physically receives only the bundle the barrier built. There is no filesystem or conversation channel between builder-space, verifier-space, and adversary-space (SI-5). The handoff payload is always a **content-addressed, immutable reference** (an artifact hash, an evidence hash, a verdict hash) — never a live object — so a handoff is replayable and non-repudiable.

### §7.5 Communication (substrate access, deny-by-default)

A worker communicates only with the **substrate MCP servers** its capability allows (PAEOS-7.6 §8): `constitution` (read-only), `artifacts` (CAS put/get), `memory` (`:read` match / `:write` gated propose), `court` (submit evidence, inert until adjudicated), `ledger` (read + verify_chain only; **append is never exposed** — agents emit via kernel `record_event`). No worker has a network egress beyond its allow-listed servers; research egress (L05) is itself quarantined (T9). External content is **provenance-tagged data, never instructions** — the content/instruction separation is enforced, not assumed.

### §7.6 Timeouts, budgets, and failure recovery

- **Timeouts & budgets (two-tier, A-7).** Each package carries a per-goal budget slice (`tokens`, `wallclock_s`, `retries`); a global (org) budget with admission control sheds/queues new goals under pressure. `wall_clock_s` accrues **only while actively dispatched** — time spent `blocked` awaiting a founder Decision is not charged (C-1.1), so escalation never self-triggers BUDGET_EXCEEDED. Cost is a first-class ledgered metric; a goal > Nσ over its class median auto-halts for review (SI-10).
- **Retry logic (bounded, with progress).** Non-deterministic checks retry with exponential backoff under a hard cap (T6); a monotonic **progress measure** is required so a loop that spends budget without advancing halts rather than spins (SI-9, T5). Flaky ≠ refutation (Ω-01), but persistent flakiness is treated as evidence-forgery risk and blocked, not retried-until-green (T2).
- **Failure recovery.** A `FAILED`/`ABANDONED` result routes through the gate's failure target (§8.6): Remand (fixable), Reject (+scar), Quarantine (integrity/canary), or Abort (never admitted). Because state is a ledger projection, recovery is deterministic replay to the last committed transition — never a manual repair of live state.

---

## §8 Execution State Machine

This section expands the frozen 19-state lifecycle (`ENGINEERING_LIFECYCLE.md` v1.1) into the executable machine the runtime drives. It adds **no state and changes no ordering** (that would be an L19 amendment to a frozen document); it makes the *events, guards, transitions, blocking, retry, rollback, incident, proposal, constitutional-review, and runtime-improvement* behavior explicit and binds each to the kernel gate and lattice effect. Every transition is a four-tuple (PAEOS-7.6 §4); every L-state is metadata over the lattice (G-1).

### §8.1 The uniform stage engine (every state is this sub-machine)

```
Pending ──open_stage──▶ Active ──worker returns──▶ AwaitingEvidence ──assemble bundle──▶ Gating
Gating ──four-tuple check (kernel)──▶ Passed  (TransitionCommitted, next state Pending)
                                    └▶ Failed  (route per §8.6: Remand | Reject | Quarantine | Abort)
```

- **Events:** `StageOpened`, `AgentTrace`, `EvidenceSubmitted`, `TransitionProposed`, `TransitionCommitted`, `<Failure>` — all ledgered (single writer). Nothing "happens" except by a ledger append (FR-5).
- **Guards:** the gate's pass-criterion (§8.5) + separation-of-powers (SI-3) + evidence binding (SI-4) + legal-edge check (L-C) + TCB-classification (SI-8). Miss any guard → deny (fail closed).

### §8.2 The state table (events · guard · gate · lattice · on-fail)

| L | Event that opens it | Guard to exit (gate) | Kernel gate (PAEOS-7 §4.3) | Lattice | On fail |
|---|---------------------|----------------------|----------------------------|---------|---------|
| **L01 Intake** | founder/agent/incident submits | well-formed `Goal(declared)` | G-Intake | declared | Abort (malformed) |
| **L02 Triage** | goal declared | disposition + classification (v×r) + ceremony depth + budget | G-Triage | declared | Abort/Reject (founder-confirmed) or → L05 |
| **L03 Re-Derivation** | Trace-B & kept | first-principles model reproduces intent (FR-8) | G-Derive | declared | → L05 (blocked) |
| **L04 Ideation** | L03 done | candidate space genuinely wide | (auto/critique) | declared | collapse+note |
| **L05 Research** ⟲ | pull-driven blocker | named blocker resolves (dossier bound, expiring K2) | (auto) | declared | scope-creep incident |
| **L06 Trade-offs** | ≥1 viable approach | decision axes explicit | (auto) | declared | omitted-axis incident |
| **L07 Mitigation** | matrix has risks | every high-severity risk mitigated or accepted-risk recorded | (auto; founder if irreversible) | declared | blocks L08 |
| **L08 Design** | approach+mitigations | intent-conservation passes; constraints tightened only (D2) | G-Design | declared | redesign/escalate |
| **L09 Critique** | design produced | all 7 perspectives reported | G-Design (critique) | declared | incomplete → cannot advance |
| **L10 Adversarial Review** | design+findings | verdict RATIFY / RATIFY-WITH-AMENDMENTS(resolved); **decorrelated model** | G-Adversary (design-time) | declared | → L08 (REJECT/blocking) |
| **L11 Formal Plan** | L10 ratified | implementation contract approved (affected+forbidden files, rollback, acceptance) | G-Plan | declared | ambiguity = incident |
| **L12 Implement** | contract frozen | scope built + runs; no scope creep; commits cite L11 | G-Build | speculated→executed | scope-creep/cap-overrun incident (A-12) |
| **L13 Verify** | executed | acceptance met by live signed independent evidence; **kernel re-runs** deterministic | G-Court | executed→verified | refutation → regress + incident |
| **L14 Independent Audit** | L13 passed | audit clean; **model family ≠ builder** (A-08) | G-Adversary (impl-time) | verified (gate) | slop/mock/violation → L12 |
| **L15 Doc & Ledger** | L14 clean | institutional records synced; traceable to origin | G-Sync | verified→integrated | stale-ledger incident |
| **L16 Promotion/Seal** | L15 done | idempotent signed seal; single-threaded merge (K8) | G-Seal | integrated | REJECT (unsealable) |
| **L17 Retrospective+CER** | L16 done OR any failure | root cause found; CER-4 written (6 questions) | G-Retro | evolution | no root cause → no close |
| **L18 Knowledge Extraction** | L17 lessons exist | reusable knowledge captured (versioned, scarred K6) | G-Memory | evolution | repeated mistake not converted (rule 10) |
| **L19 Constitutional Evolution** | incident/amendment candidate/kernel finding | amendment provisional→verified|reverted (A-06); kernel change → §14.5 + founder | G-Amend | evolution | falsifier fires → revert |

### §8.3 Ceremony depth (which states fire) — the router made executable

Triage (L02) assigns depth from `v × r`. **Trace-A** auto-discharges L03–L11 and L17–L18 (each emits an evidence stub `{auto_pass, trace_a, runtime}` so every transition stays four-tuple-valid — auto-discharge ≠ skip), executing L01–L02, L12–L16 in full. **Trace-B** executes all 19 in full with founder Decisions at gates. Depth is a **per-artifact property**, not a per-project choice. The router principle and the spine both hold: the shape is invariant, the front-end cost contracts (§2.3, the primary economic control).

### §8.4 Blocking conditions

A transition **blocks** (does not fail — waits) on: an unresolved founder Decision at a Trace-B gate (`blocked` is a computed flag, not a lattice state, C-1.3; it never alters `status` and never itself triggers BUDGET_EXCEEDED); a non-integrated dependency (FP-1: dispatch requires all deps `integrated`); a stale context (freshness check forces recompile before proceeding, §4.7); a concurrent provisional amendment to the same policy (E-1.2: at most one provisional per policy, second blocks `IDENTITY_CONFLICT`). Blocking is safe indefinitely; the clock is paused (C-1.1).

### §8.5 Guards, evidence, and the four-tuple at each gate

Every gate demands the full four-tuple — **Authority** (capability bound to this role/goal/stage), **Goal** (the legal edge), **Evidence** (content-addressed, bound to `artifact_hash`+`env_hash`, reproducible), **Validation** (the explicit pass-criterion). Deterministic evidence is **re-run by the kernel**, never trusted (T2, SI-2). Judgment evidence must cite the artifacts/traces it relied on. No evidence ⇒ no transition (FR-4, deny-by-default). The gate is the *only* legal exit from a state.

### §8.6 Failure states, retry, and rollback

- **Remand** — fixable failure (G-Court/G-Adversary/G-Design). Goal re-enters an earlier state `Pending`; prior artifacts **preserved (superseded, not deleted)**; the failing verdict becomes **required reading** injected into the next context (§4.3 review scoping). **Retry cap:** N remands → escalate to redesign or reject (never infinite, SI-9/T5). **Oscillation guard:** a change that reverts one sealed within the last K runs is flagged as churn → human review.
- **Reject** — unsealable / unresolved blocking dissent with no viable fix in budget. Goal terminates; **a scar is still written** (a reject is a lesson, FR-6).
- **Quarantine** — kernel-integrity failure, broken chain, capability-escalation attempt, missed canary, or budget/drift breach. State frozen; incident recorded; **only human release** or the amendment path resumes (the FR-2/FR-3 tripwire). Fail closed, never open.
- **Abort** — goal never admitted (G-Intake/G-Triage out-of-scope/ill-formed). Recorded and closed cheaply (economic control).
- **Rollback = compensation, never mutation** (FR-5+FR-7): state rollback appends a superseding event; artifact rollback links `supersedes → old-hash`; code rollback discards the isolated worktree; **seal rollback is impossible** — a post-seal defect is a constitutional incident (quarantine + a re-execution goal whose seal supersedes the defective one, and whose retrospective *must* produce a detection-signature scar).

### §8.7 Incident, proposal, constitutional-review, and runtime-improvement creation

These four are not extra states — they are **outputs woven through the machine** (global rules 8, 9, 14, 16):

- **Incident creation.** Every defect and **every ambiguity** becomes an incident (the HALT rule, global rules 8–9). Ambiguity-as-incident is why a worker never improvises: an unresolved decision is a ledgered incident, not a judgment call.
- **Proposal creation (CER-2).** Any discovered improvement emits `proposals/PAEOS-IP-NNNN` — surfaced in the next RuntimeContext, **never auto-applied** (CER-5). Implementation continues regardless of a proposal's fate.
- **Constitutional review (CER-4).** Every completed task ends with the L17 Constitutional Review answering the six questions; a task without it is **not done**.
- **Runtime improvement (L18→L19).** A lesson becomes a skill/template (soft loop) or, if it touches kernel/lifecycle/authority/invariants, a stage-18 proposal that enters the **hard loop** (§8.8).

### §8.8 The hard loop (constitutional review + runtime improvement, executable)

When a change is classified **HARD** — by the **kernel** on static blast-radius, not the agent's claim (A-2), conservative default HARD — L19 runs the amendment machine:

```
proposal (touches TCB) ──▶ classify_change == HARD (kernel) ──▶ REFUSE ordinary transition (SI-8)
   └▶ run the FULL 19-state lifecycle ON the proposal itself (self-hosting, FR-9)
        └▶ Adversarial Ratification (PAEOS-3.5) attacks the SAFETY-INVARIANT DIFF specifically
             (the diff shown to the ratifier is kernel-generated/neutral, never the proposing agent's, T4c)
             └▶ MANDATORY human ratifier signature (FR-2, non-delegable)
                  └▶ amendment.py (the sole Z0 writer) seals a new frozen kernel version
                       └▶ recompiled policy binds every FUTURE Context Compiler run (K5/I6)
```

Guards on the hard loop: **cumulative-drift metric** vs. the frozen baseline forces a hard-loop review even when each step was individually soft (boiling-frog, A-3); **canary corpus + classifier rules live in Z0** (a system cannot edit its own alarms, A-1); **meta-proposals** (proposals about the proposal system) require a fixed recursion depth; **self-hosting has a base case** — an idempotent re-derivation producing no delta from the sealed version is a fixpoint and terminates (A-8). Autonomy grows only in `runtime/`; it never grows in `kernel/`.

### §8.9 Runtime self-update and the next cycle (closing the machine)

L19 completion feeds forward: recompiled policy, new scars, new skills, and (if ratified) a new kernel version all become inputs to the **next** Context Compiler run (§4.7). The Phase-3 `RESTART` scheduler pulls the next goal whose dependencies are `integrated` and re-enters L01 — *as a changed system*. "The runtime updates itself and begins the next engineering cycle" is therefore literal: the machine's terminal transition mutates the machine before the next task starts.

---

## §9 Persistence Architecture

Persistence is the load-bearing layer: **the ledger is the source of truth; everything else is a projection of it** (FR-5). This section specifies every store — ownership, schema sketch, mutability, retention, query patterns — extending PAEOS-7 §6 (eight stores) and PAEOS-8 (Postgres 16 + filesystem CAS) with the compiled-context, compiled-package, and graph-snapshot stores this execution layer adds. The cross-cutting rules are absolute: **single writer (the kernel); nothing hard-deleted (supersession + retention tiers only); artifacts+evidence content-addressed; everything else references them by hash.**

### §9.1 Store catalog

| Store | Owner / writer | Mutability | Addressing | Schema sketch | Retention | Query patterns |
|-------|----------------|-----------|------------|---------------|-----------|----------------|
| **Ledger** | Kernel (single writer) | **Append-only, hash-chained** | seq no. + chain hash | `seq, prev_hash, event_type, goal_id, run_id, stage, payload_ref, actor, ts_logical, schema_ver` | **Permanent** (never pruned; externally anchored head, A-9) | Replay; audit; projection rebuild; chain verify |
| **CAS (Artifacts)** | Kernel-mediated put | **Immutable** | content hash | `hash, type, goal_id, produced_by_role, skill_ver, model_ver, supersedes[]` | Permanent (referential-integrity GC only) | By hash; by goal; lineage walk |
| **CAS (Evidence)** | Kernel-mediated put | **Immutable, kernel-attested** | content hash | `hash, kind, claim_id, artifact_hash, environment_hash, reproducible_command, producer, determinism, attestation` | Permanent | By claim; by gate; reproducibility replay |
| **Goals** | Kernel (projection) | Identity immutable, status is projection | goal id | `id, intake_ref, constitutional_basis, workload, weight_class, budget, status, current_L_state` | Permanent | Work queue; by status/class; by chamber |
| **Reviews** | Kernel (projection) | Immutable | content hash | `hash, kind{critique|verdict|dissent}, target_artifact, severity, evidence_refs[], outcome` | Permanent | By artifact; unresolved dissents; by severity |
| **Scars** | Kernel (gated write, A-10) | **Append-only, signed** | scar id | `id, failure_class, root_cause, detection_signature, guard_action, severity, origin_run, matches[]` | **Permanent (never deleted)** | Signature match at L03/L08/L09/L13; by class |
| **Decisions** | Doc role → kernel | Append-only (supersede) | decision id + hash | `id, context, options[], chosen, rationale, constitutional_basis, decided_by, superseded_by` | Permanent | By goal; by clause; timeline |
| **Proposals** | Proposal engine | Append-only | IP-NNNN | `id, observation, current, proposed, justification, risks, compat, constitutional_impact, status` | Permanent | Open by domain; ratification lineage |
| **Debt** | Evolution (CER-3) | Append-only (close by repayment) | DEBT-NNNN | `id, compromise, reason, ideal, repayment_conditions, priority, impact, status` | Permanent | Open by priority; by domain |
| **Agent Traces** | Runtime → kernel | Immutable, **secret-scrubbed** | content hash | `hash, goal_id, stage, role, prompts, tool_calls, outputs, tokens, cost, model_ver, skill_ver` | Tiered (audit hot → cold) | Audit; self-improvement mining (L17/L18); cost |
| **Projections** | Kernel (replay) | **Derived, disposable** | view key | goal state, work queues, scar indices, cost counters | Rebuildable (not authoritative) | Current state; scheduling; dashboards |
| **Compiled Contexts** | Context Compiler | **Cache, gitignored, rebuildable** | content_hash | `content_hash, corpus_hash, load_manifest, scoped_graphs, compiled_at, compiler_ver` | Ephemeral (regenerated every boot, H-08) | Determinism check; audit via boot.log |
| **Compiled Packages** | Task Package Compiler | **Cache, rebuildable** | package hash | `TaskPackage` (PAEOS-7.6 §5), deterministic from RuntimeContext | Ephemeral | Dispatch record; replay of what was dispatched |
| **Graph Snapshots** | Kernel (projection) | **Derived, content-hashed** | snapshot hash per graph | the twelve graphs of §5, each a materialized view | Rebuildable (folded into corpus_hash) | The SCOPE stage (§4.3); dependency-impact |

### §9.2 The three tiers of durability (what survives a crash)

Grounded in D1 (crash-only) + A2 (artifacts durable, context ephemeral):

- **Permanent (source of truth):** ledger, CAS (artifacts + evidence), scars, reviews, decisions, proposals, debt — written as they are made (crash-only corollary: killing the session loses only cache + chat, never a decision, scar, or work product).
- **Derived (rebuildable by replay):** goals, projections, graph snapshots — losing one is a rebuild, not data loss; this is what makes the kernel restartable and the system replay-testable.
- **Ephemeral (cache):** compiled contexts + packages — regenerated every boot, freshness-checked every transition; a hand-edited cache is overwritten on recompile and its hash won't match (detected).

### §9.3 Consistency, integrity, and the open DR item

- **Consistency model:** CP (consistency over availability, PAEOS-7 §9.1) — a constitutional record must be correct even at the cost of uptime. Single logical ledger, single writer; "Ledger Synchronization" (L15) = merging agent-local event buffers into the canonical log, **not** multi-master replication.
- **Integrity:** hash-chain + **externally anchored head** (A-9, Phase 2) makes tamper detectable, not just chain-internal; single-writer identity is a kernel key (no fork, T7); projections are **verified against the ledger hash before any gate use** (no projection-poisoning, T7); CAS GC is referential-integrity-safe (referenced content never collected, SI-6/7).
- **Schema versioning:** every event carries `schema_ver`; projection migrations are themselves ledgered (the event/schema-versioning caution, PAEOS-8 §13.1 — assign in Phase 1).
- **Open item (flagged, must resolve before rung R3):** **ledger backup / disaster recovery.** Append-only ≠ safe from disk loss; the in-DB hash-chain protects integrity, not availability. This is a standing open decision (PAEOS-8 §13.1) alongside the concrete durable-execution engine, HA topology, and scar-retrieval-at-scale.

---

## §10 SAKG Integration

SAKG (the Software Architecture Knowledge Graph) is assumed to exist in the future. **This document does not design SAKG and does not depend on it.** It specifies exactly how PAEOS *consumes* SAKG when present and how PAEOS *functions unchanged* when it is absent. The governing principle: **SAKG is augmentation, never authority.** Every SAKG consumption point sits behind a deterministic PAEOS mechanism that already works; SAKG makes that mechanism *better-informed*, never *load-bearing*.

### §10.1 The consumption contract (read-only, capability-gated)

PAEOS consumes SAKG as one more **substrate MCP server** (`sakg`, PAEOS-7.6 §8) — read-only, deny-by-default, on a role's allow-list only when its stage benefits. It is queried by the Context Compiler's SCOPE stage (§4.3) as an **augmentation source layered over** the local graphs (§5), never as their replacement. SAKG results enter context as **SUMMARY/INDEX-tier advisory material tagged `provenance: sakg` (untrusted, re-verifiable)** — the same treatment as external research (T9): retrieved knowledge is data, never instruction, never evidence, never a gate authority.

```
sakg MCP (read-only) methods consumed:
  query_architectures(pattern)      → prior designs shaped like this touch-set
  dependency_impact(component)       → what historically breaks when this changes
  tradeoff_precedents(axes)          → how similar trade-offs were resolved + outcomes
  pattern_retrieval(problem)         → reusable patterns/anti-patterns with scars attached
  memory_augment(signature)          → semantic neighbors of a scar/precedent
```

### §10.2 Where PAEOS consumes it (mapped to graphs and stages)

| SAKG consumption | PAEOS graph augmented (§5) | Stage | Local mechanism it augments (never replaces) |
|------------------|---------------------------|-------|----------------------------------------------|
| **Graph queries** | architecture-graph, dependency-graph | L08 Design, L11 Plan | The reachable-sub-graph traversal (§4.3) — SAKG widens the horizon beyond this repo's local graph |
| **Retrieval** | artifact-graph, memory-graph | L04 Ideation, L18 Extraction | Precedent/artifact retrieval — SAKG returns cross-project neighbors |
| **Architectural reasoning** | architecture-graph | L08 Design, L10 Adversarial | The design worker's own reasoning — SAKG supplies "designs like this and how they failed" |
| **Dependency reasoning** | dependency-graph | L08, L11, L19 | The DAG impact analysis — SAKG supplies historical blast-radius, augmenting (not deciding) the classifier |
| **Trade-off reasoning** | decision-graph | L06 Trade-offs, L07 Mitigation | The trade-off matrix — SAKG supplies precedent axes + realized outcomes |
| **Memory augmentation** | scar-graph, memory-graph | L03/L08/L09/L13 (scar match) | **Signature-match-first (deterministic); SAKG semantic recall is augmentation only** (T3) |

**Critical boundary — SAKG never touches the TCB path.** It is never consulted for: capability decisions, evidence adjudication, seal, classification authority (A-2 stays local + conservative), or promotion. A poisoned or wrong SAKG can degrade *suggestions*; it can never advance a defective goal, because everything that makes a goal canonical (four-tuple, kernel re-run, separation of powers) is downstream of SAKG and independent of it. Retrieval poisoning (T3e) is contained because SAKG is *augmentation over a deterministic signature-match floor* — the floor holds even if the augmentation lies.

### §10.3 Optimization via SAKG

When present, SAKG optimizes three costs without changing any guarantee: (a) **fewer L05 research spawns** — cross-project knowledge answers what would otherwise be a research goal; (b) **sharper L08 designs** — the design worker starts from realized patterns, reducing L10 remands; (c) **better triage priors** — historical blast-radius sharpens weight-class estimation (still kernel-final, still appealable-down-not-forceable-up, T6). Each optimization reduces token/latency cost (T6 mitigation) and is measured against the no-SAKG baseline in the cost meter (§9) — if SAKG stops helping, it can be dropped with zero correctness impact.

### §10.4 Graceful degradation — PAEOS functions fully without SAKG

**PAEOS is complete without SAKG.** The `sakg` server is *optional* on every allow-list; if it is absent, unreachable, or returns nothing, the SCOPE stage (§4.3) simply omits the augmentation tier and proceeds on the **local graphs alone** — which are the source of truth regardless (§5.0). Concretely, on SAKG-unavailable:

- scar matching falls back to **deterministic signature-match** (always the authority anyway, §5.8);
- design/trade-off reasoning falls back to the **worker's own cognition + local precedent** (the Phase-1 baseline, before SAKG exists);
- dependency impact falls back to the **local dependency-graph DAG** (§5.3);
- the Context Compiler's `content_hash` is still deterministic (SAKG results are advisory and, when included, folded in with their own provenance hash — so "with SAKG" and "without SAKG" are two distinct, each-reproducible context states, never silent nondeterminism).

The degradation is **invisible to correctness and visible to quality**: fewer priors, more research spawns, possibly more L10 remands — but every gate, every guarantee, every invariant holds. This is required: PAEOS Phases 0–2 are specified to run *before SAKG exists* (PAEOS-8), so a hard SAKG dependency would violate the roadmap. SAKG is a Phase-3+ quality multiplier bolted onto a system that is already correct.

---

## §11 Claude Code Integration

Claude Code is the **agent runtime** — the host for the rented intelligence of §1.5. This section describes exactly how it participates and answers the load-bearing question: *how does a worker automatically follow the Engineering Lifecycle rather than relying on prompt discipline?* The answer, in one line: **the worker cannot do otherwise, because the lifecycle is compiled into its only context and enforced by pre-commit rejection and the kernel gate — discipline is structural, not requested.**

### §11.1 How a Claude Code session participates (the full surface)

| Element | Role in the pipeline | Grounding |
|---------|---------------------|-----------|
| **Skills** | The *method* of a stage/role (e.g. `testing@2.1`), version-pinned in the package; invoked by the lifecycle, not chosen by the worker | PAEOS-7.6 §9; §6.4 |
| **Prompt Templates** | The worker prompt is **generated** (F-1 grammar) from RuntimeContext — never hand-written (K5) | Bootstrap §4; §4 |
| **Context Compiler** | Produces the RuntimeContext the session boots from — the only world it sees | §4 |
| **Compiled Packages** | The TaskPackage = the session's complete, expiring lease (scope, MCP, skills, evidence, budget) | §6 |
| **MCP** | The session's only substrate access, deny-by-default (`constitution`/`artifacts`/`memory`/`court`/`ledger`-read/`sakg`) | PAEOS-7.6 §8; §7.5 |
| **Git** | L12 builds on an **isolated worktree** (A-16); commits cite the L11 contract; rollback = discard branch | §3.7, §8.6 |
| **Reviews** | L09 critique + L10/L14 adversary/audit sessions, isolated behind the IBM, decorrelated model family | §7.4 |
| **Verification** | L13 Court session; deterministic evidence **re-run by the kernel**, not trusted | §3.8 |
| **Evidence** | Produced bound to `(artifact_hash, env_hash)`; the session requests **kernel attestation** (never holds keys, A-5) | §5.7 |
| **Human approvals** | Trace-B gate Decisions + the mandatory hard-loop ratifier signature (FR-2) | §3.1, §8.8 |

### §11.2 The spawn contract (how a session is scoped)

The dispatcher (`integrations/claude_code.py`) spawns each session as a subprocess with, and only with: a **scoped workspace** (exactly the package `write_scopes` — the rest of the tree is absent, not hidden); an **MCP allow-list** (exactly `mcp_servers`); the **pinned skills**; the **capability token** (short TTL, op-allow-listed); the **generated prompt** (the compiled context, nothing else); and the **budget**. There is no ambient filesystem, no network egress beyond allow-listed servers, no shared context with any other role's session (SI-5). This is the enforcement surface FR-3 and MR need at the agent boundary — the reason Claude Code was chosen as the runtime (PAEOS-7 §2.1).

> **Load-bearing hidden assumption (surfaced, must be validated Day-1).** This entire section rests on Claude Code being spawnable programmatically with an isolated workspace + permissioned MCP tooling in the target environment. This is flagged in PAEOS-8 §13.2 as a **Day-1 spike, part of B0.0**. *If it is false, the agent-runtime decision reopens* (PAEOS-7 §13 / the handoff note). PAEOS-9 does not resolve it; it inherits it as the pipeline's single most important external dependency.

### §11.3 Why workers follow the lifecycle automatically (not by prompt discipline)

This is the crux — the Sentium scar (passive docs lose to the context window) solved structurally. Five mechanisms, each removing a way a worker could *not* follow the lifecycle:

1. **The lifecycle is the only context (nothing to ignore *toward*).** The worker prompt contains **only** the compiled context (§4); the raw corpus is not in the window (bootstrap §10). There is no competing "more skippable markdown." The worker cannot ignore the lifecycle because there is nothing else present to attend to instead.
2. **The worker cannot self-advance (structural, not behavioral).** A session returns *artifacts only*; the Runtime gates the transition (bootstrap §4.1 §9; SI-2). "Follow the lifecycle" is not a request the worker could decline — the worker literally cannot promote its own goal; only the kernel commits, only on validated evidence.
3. **Forbidden actions are unreachable, not prohibited.** A worker cannot edit a forbidden file, invoke an un-granted skill, or reach an un-listed MCP server — its capability lacks the operation (T1, SI-1). Lifecycle-violating actions are *absent from the action space*, not *disallowed within it*.
4. **Pre-commit rejection, not post-hoc detection.** Proposed writes are checked against the compiled constraints **before commit** (bootstrap §7 — the WRITE validator, later the kernel gate). The worker cannot commit a violating write; it receives the rejection and must conform or HALT to an incident. Jumping stages, skipping verification, authority violations, scope creep, and unauthorized architecture change each map to a specific pre-commit rejection (bootstrap §7 table).
5. **Freshness gates every transition.** A stale context is a hard stop, not a warning (§4.7, K2). The worker cannot proceed on an outdated view of the lifecycle; the next legal action is always computed from the current world.

The net effect: a worker follows the Engineering Lifecycle for the same reason a program follows the CPU's privilege model — not because it was asked, but because every other path faults. Prompt discipline is *replaced* by mechanism. Where a worker "can't edit X," the fix is a **skill or package change** (soft loop), never kernel code — preserving the small-kernel discipline (PAEOS-7 §3.9).

---

## §12 Implementation Roadmap

This section converts PAEOS-8 (the dependency-ordered task list) into the **execution sequence** — what gets built first, why, the critical path, what parallelizes, the risks, and the expected completion state at each milestone. It **adds no tasks and reorders nothing** in PAEOS-8; it presents PAEOS-8's DAG as an executable plan and binds each milestone to the dataflow this document specifies. The one-line answer is unchanged: **B0.0 today, B0.1 (the Ledger) tomorrow — nothing else can land before a verified, sealed ledger exists** (the ledger *is* the source of truth, §9).

### §12.1 What gets built first, and why

```
B0.0 repo + CI + TCB gates   ── the toolchain that lets B0.1 be VERIFIED (LOC budget + TCB-diff gates live)
   │
B0.1 LEDGER  ◀── THE FIRST REAL CODE. Everything is a projection of it (§9.0). Nothing precedes it.
   │             append-only · hash-chained · single-writer · verify_chain · 1k-event replay
   ├── B0.2 CAS ────────────────┐
   ├── B0.4 types + StageId ──┐  │
   │      B0.5 lifecycle ─────┤  │
   ├── B0.3 constitution ─────┤  │
   ├── B0.7 evidence ─────────┤  │  (needs CAS)
   ├── B0.8 capability broker ┤  │
   │                          ▼  ▼
   │      B0.6 GATES (four-tuple, deny-by-default, failure routing) ◀── the constitution executable
   │              │
   ├── B0.9 SEAL (idempotent Ed25519, refuse without verdict) ◀── needs ledger+CAS+gates
   ├── B0.10 projections + replay
   ├── B0.11 classifier stub (kernel/constitution touch ⇒ HARD; unknown ⇒ HARD, fail-safe)
   ├── B0.13 observability (cost/trace meter — was missing from PAEOS-7, added PAEOS-8)
   ├── B0.12 CLI control plane (create-goal, advance --evidence, ledger, replay, seal, inspect)
   ├── B0.14 canary scaffold
   │              ▼
   └──────▶ B0.SLICE  hello-paeos: INTAKE→IMPLEMENT→VERIFY→SEAL, kernel re-runs evidence, replay byte-identical
```

**Why this order:** the ledger is first because every other component *reads state that only the ledger can authoritatively hold* (§9.0). Gates (B0.6) are the executable constitution and depend on lifecycle + evidence + capability. Seal (B0.9) depends on ledger + CAS + gates. The slice (B0.SLICE) is last in Phase 0 because it exercises *every* Phase-0 module at once — it is the Phase-0 seal.

### §12.2 The critical path

```
B0.0 → B0.1 → B0.2 → B0.7 → B0.6 → B0.9 → B0.12 → B0.SLICE
              (└ B0.4 → B0.5 → B0.6 also required; B0.4→B0.8 → B0.6)
```

The critical path runs **ledger → CAS → evidence → gates → seal → CLI → slice**. B0.6 (gates) is the convergence point: it depends on constitution (B0.3), lifecycle (B0.5), evidence (B0.7), and capability (B0.8), and everything downstream (seal, CLI, slice) depends on it. **Gates are the schedule's tent-pole** — slippage there slips the whole phase.

### §12.3 What parallelizes

After B0.1, three independent tracks run concurrently (distinct workers, separation of powers per PAEOS-8 §5):

- **Track A (content):** B0.2 CAS → B0.7 evidence.
- **Track B (control):** B0.4 types → B0.5 lifecycle; B0.4 → B0.8 capability; B0.3 constitution.
- **Track C (support):** B0.10 projections/replay, B0.13 observability, B0.11 classifier stub, B0.14 canary scaffold.

Tracks A and B converge at B0.6 (gates); Track C converges at B0.12 (CLI). This is the maximal parallelism the DAG permits; the critical path (§12.2) sets the floor on schedule regardless of parallel width.

### §12.4 Risk register (execution risks, from PAEOS-8 §13)

| Risk | Severity | Mitigation / trigger |
|------|----------|---------------------|
| **Claude Code scoped-workspace + MCP allow-list unsupported** in target env | **Critical** | Day-1 spike (B0.0); if false, agent-runtime decision reopens (§11.2) |
| **Ledger backup / DR** — append-only ≠ disk-loss-safe | High | **Open item; must resolve before rung R3** (§9.3) |
| **Kernel exceeds ~20k LOC** with all gates | High | CI LOC-budget gate turns it into an alarm (PAEOS-8 §8 F1); "anything that can live in runtime/ must" |
| **Deterministic evidence not reproducible in CI** (env drift) | High | `env_hash` pinning; flakiness treated as forgery risk, blocked not retried (T2) |
| **Event/schema versioning drift** in projections | High | Every event carries `schema_ver`; migrations ledgered; assign Phase 1 |
| **Human-ratifier bottleneck** under amendment volume | Med | Intended throttle (safety over speed); monitor staffing (FR-2) |
| **AI slop** — inventing architecture to unblock | Med | Prime Rule: unresolved decision ⇒ escalate (it's a spec defect); slice can't be faked green (kernel re-runs) |

### §12.5 Expected completion state per milestone

| Phase | Completion state (all ledgered + sealed) | Rung |
|-------|------------------------------------------|------|
| **Phase 0** | The §11 slice passes: a goal walks INTAKE→IMPLEMENT→VERIFY→SEAL with kernel-re-run evidence, a signed seal, byte-identical replay. Humans play all agents. TCB CI gates live. | R1 (Recorded) |
| **Phase 1** | One autonomous end-to-end run: Claude Code Planner/Builder/Verifier/Adversary take an intake to a sealed, court-passed, adversary-reviewed change behind real barriers, with scars written; triage fast/full path works. | R2→R3 |
| **Phase 2** | PAEOS runs the lifecycle on **its own** backlog goal; soft-loop scar/skill updates live; amendment path wired + human-gated; canary calibration running. | R4 (Self-hosting) |
| **Phase 3** | Continuous RESTART scheduling, multi-goal concurrency + isolation, economic governor, distributed ledger; human reserved to amendment + reject/override only. | R5 (Autonomous) |

**Invariant across all rungs (PAEOS-8 §12):** kernel/TCB changes are *always* hard-loop + human-signed. Autonomy grows in `runtime/`; it never grows in `kernel/`. No Phase N+1 task starts until the Phase N milestone is sealed.

---

## §13 Adversarial Architecture Review

Per CER-1 and the brief, this document attacks itself from ten disciplines. The scope is **this document's contribution** — the execution dataflow, the Context Compiler's SCOPE stage, the graph architecture, the worker protocol, and the SAKG/Claude Code seams. Attacks on the underlying architecture were answered in PAEOS-7 §9 and PAEOS-7.5; here each finding is either **[MODIFY]** (a change folded back above, tagged inline) or **[DEFEND]** (proof it is already correct). Findings that could not be eliminated are carried honestly to §13.11.

### §13.1 Distributed Systems

**Attack:** twelve graphs (§5) as projections invite cross-view inconsistency — a gate reads the goal-graph at head N while the dependency-graph lags at N−k, and dispatches on stale deps. **[DEFEND]** All graphs derive from **one** totally-ordered single-writer ledger and every gate read is taken at a single `ledger_head` (§5.0); two graphs read at the same head cannot disagree, and projections are verified against the ledger hash before any gate use (T7). Cross-view skew is impossible by construction — there is no independent write path to skew.
**Attack:** the SCOPE stage reads twelve graph snapshots per stage — a distributed read amplification. **[MODIFY]** §5.13 pins all twelve reads to one head in a single projection query; §4.2 folds the scoped-graph digest into one `content_hash`, so it is one consistent snapshot read, not twelve races.

### §13.2 Operating Systems

**Attack:** calling the lifecycle "the syscall interface" (§1.1) implies the kernel schedules — reintroducing the god-object PAEOS-7 §9.3 rejected. **[DEFEND]** The kernel is reference-monitor + state-machine only; scheduling and cognition are Z2 (Runtime + hosted agents). The syscall analogy is precise: the kernel *adjudicates* privileged transitions (like a syscall trap), it does not *perform* the work (like userspace does). §3.4 restates the kernel's surface as exactly the PAEOS-7.6 §4 operations — small and fixed.
**Attack:** the per-stage lease (§7.2) means constant context re-compilation — TLB-thrash equivalent. **[DEFEND]** Intended and bounded: only state-scoped fields recompile between stages (§4.6); the cost is the price of freshness (K2) and is the economic tradeoff triage manages (Trace-A compresses the front-end, §8.3).

### §13.3 Programming Languages

**Attack:** the LLVM analogy (source→IR→executable) is decorative; determinism claims need a defined evaluation order. **[DEFEND]** Evaluation order *is* defined: precedence (Z-1) fixes RESOLVE; F-1 fixes RENDER byte-for-byte; the SCOPE traversal is a fixed graph reachability at a fixed head. Determinism is inherited from the bootstrap's proven guarantee (§4.1), not asserted.
**Attack:** template holes / compiled context could admit injection if a graph fact contains adversarial text. **[MODIFY]** §10.1 + §7.5 mandate all retrieved/graph-sourced content is provenance-tagged untrusted data, wrapped so external text cannot become control flow (T9); §13.4 below extends this.

### §13.4 Security

**Attack:** the Context Compiler is a new, powerful, Z2 component that decides the worker's entire world — a single point of context compromise (a poisoned compiler grants a worker a forbidden scope). **[DEFEND]** The compiler decides what the worker *sees*, never what it *may do*: permissions are minted by the kernel Capability Broker (Z1, §6.3), not the compiler. A compromised compiler can degrade or mislead a worker's *reasoning*, but the worker still cannot write out of scope, seal, or advance (SI-1, SI-2, SI-3) — and the compiler's output is content-hashed and reproducible, so tampering is detectable (§4.5). The compiler is powerful over *context* and powerless over *authority* — the exact split §3.5 requires.
**Attack:** SAKG (§10) is an external knowledge source — a supply-chain / poisoning vector into design decisions. **[DEFEND]** SAKG is augmentation over a deterministic floor, never on the TCB path (§10.2); a lying SAKG degrades suggestions, never advances a defective goal. Signature-match-first memory (T3) holds even if semantic recall is poisoned.

### §13.5 AI Alignment

**Attack:** the whole system hosts a powerful optimizer (the worker) whose objective (pass the gate) can be Goodharted — reward-hacked evidence. **[DEFEND]** This is T2, the acknowledged top threat, answered by four inherited mechanisms surfaced in the dataflow: kernel re-runs deterministic evidence (§8.5), evidence is bound to artifact+env (SI-4), the adversary attacks the evidence itself (§7.4), non-deterministic evidence needs two independent producers (§3.8). The worker never owns adjudication (§1.4) — the alignment property is structural.
**Attack:** self-improvement (L17–L19) lets the system weaken its own alignment controls. **[DEFEND]** The hard loop (§8.8): kernel-side classification (A-2), Z0-resident alarms (A-1), cumulative-drift metric (A-3), kernel-generated ratifier diff (T4c), mandatory human signature (FR-2). Autonomy never grows in `kernel/` (§12.5).

### §13.6 Autonomous Agents

**Attack:** the handoff protocol (§7.4) serializes everything through the kernel — a coordination bottleneck that kills agent throughput. **[DEFEND]** Serialization is per-goal and correctness-first (CP, §9.3); cross-goal work parallelizes (Phase 3 concurrency + isolation, §12.5). The bottleneck is the *ledger append*, which is cheap; the expensive work (agent reasoning) runs in parallel Z2 sandboxes. Throughput scales by goal concurrency, not by loosening the single-writer invariant.
**Attack:** ten worker archetypes (§7.1) is over-specification — most tasks need three. **[DEFEND]** They are capability *profiles*, not processes; Trace-A collapses L03–L11 (§8.3), so a routine task instantiates ~4 workers. The ten exist so the *full* ceremony is expressible, phased in by the roadmap (§12), not all built day one.

### §13.7 Software Engineering

**Attack:** this document restates the corpus — the anti-pattern the brief forbids ("do not repeat them"). **[DEFEND]** By design it cites-not-restates: every mechanism carries a back-reference (FR-n, K-n, A-n, §-n) and the *new* content is strictly the wiring (§2 dataflow, §3 layer descent, §4.3 SCOPE resolution, §5.0 graph-as-projection unification, §7.4 handoff, §11.3 auto-follow). The test: remove PAEOS-9 and the *composition* is undefined even though every part is defined — that gap is what this document fills.
**Attack:** the numbering collision (§0.3) is itself a process failure. **[MODIFY]** Surfaced as a recorded incident and resolved by founder ratification (§0.3) — the constitutional response (never guess a winner) applied to the document's own metadata.

### §13.8 Economics

**Attack:** twelve graphs + per-stage compilation + kernel re-run of all deterministic evidence is ruinously expensive per goal — the biggest practical threat (PAEOS-7 §9.4). **[DEFEND]** Triage-as-cost-gate (§8.3) scopes ceremony to risk: Trace-A compresses the front-end and auto-discharges L03–L11; the full twelve-graph SCOPE + adversary + re-derivation runs only for substantial/kernel-touching work. Two-tier budgets (A-7), model tiering (Opus for design/adversary, Sonnet for build/doc), evidence caching (cache evidence, never conclusions, FR-8), and SAKG-reduced research spawns (§10.3) bound cost. Human load scales with constitutional events, not work volume.
**Attack:** SAKG dependency raises cost if it becomes load-bearing. **[DEFEND]** SAKG is optional and measured against a no-SAKG baseline (§10.3–§10.4); it is dropped with zero correctness impact if it stops paying for itself.

### §13.9 Systems Theory

**Attack:** the exit-feeds-entrance loop (§2.2, §8.9) is a positive feedback loop — the system modifies its own context every cycle, risking runaway drift or oscillation. **[DEFEND]** The loop is *negatively* damped by design: cumulative-drift metric forces human review past a threshold (A-3); oscillation/churn detection flags a change reverting a recent seal (§8.6, A-8); self-hosting has an idempotent-fixpoint base case (no-delta re-derivation terminates, A-8). The plant modifies itself, but every modification passes the same gates and the drift governor watches the integral.
**Attack:** a control system whose plant is itself cannot be stable without an external reference. **[DEFEND]** The external reference is the frozen kernel (Z0) + the human ratifier (FR-2) — the two fixed points autonomy can never move. Stability is anchored to what the system cannot change about itself.

### §13.10 Knowledge Representation

**Attack:** twelve overlapping graphs will drift into inconsistency as the same fact appears in several (a component in architecture-graph and implementation-graph). **[DEFEND]** No fact is *stored* in a graph — every graph is a projection of the one ledger (§5.0), so a fact has one authoritative source and N derived views that are consistent by replay. "Overlap" is multiple views of one truth, not multiple truths.
**Attack:** relevance-as-reachability (§4.3) is too rigid — genuinely relevant context outside the traversal is silently dropped. **[MODIFY / carried]** §4.5 makes the traversal auditable (replay the SCOPE to see why X was excluded) and INDEX-tier keeps excluded-but-addressable content loadable on explicit reference; but the residual — a relevant fact with no graph edge to the goal — is real and carried to §13.11. SAKG (§10) is the intended widener of the horizon; the deterministic floor is deliberately conservative.

### §13.11 Residual weaknesses (could not be fully eliminated)

1. **Relevance-as-reachability can miss edge-less relevant context** (§13.10). Mitigated by INDEX-tier addressability + SAKG horizon-widening; not eliminated. A missing graph edge is a modeling gap that surfaces only as a scar (a design that needed context it wasn't given) — which then adds the edge. Self-correcting, but reactively.
2. **The Context Compiler is a large, powerful Z2 component** (§13.4). Its authority over *context* (not permission) is real; defended by determinism + content-hashing + reproducibility, but a subtly-wrong compiler degrades every worker's input quality until a scar catches it. It is the one Z2 component whose correctness most resembles a TCB concern without being in the TCB — a deliberate, monitored tension.
3. **SAKG quality is unbounded from below when present.** Correctness is immune (§10.2), but suggestion quality is only as good as SAKG; a systematically-biased SAKG could steer designs toward its bias without ever tripping a gate. Mitigated by adversary independence (a decorrelated model resists shared bias) and the no-SAKG baseline measurement; not eliminated.
4. **All of PAEOS-7.5's residuals still apply** (kernel correctness, ratifier honesty, static-analysis soundness, canary representativeness, model diversity). PAEOS-9 inherits every one; it adds no new TCB and therefore no new irreducible root assumption — but it removes none either.

The net: PAEOS-9's contribution (dataflow + compiler + graphs + protocol) introduced **no new TCB component and no new invariant**, so it added no new *critical* residual — its residuals are quality/completeness risks (compiler correctness, relevance coverage, SAKG bias), all detectable-via-scar and none capable of advancing a defective goal past the gates that PAEOS-7/7.5 already harden.

---

## §14 Final Verdict

**The question:** *Could two independent teams now build byte-compatible PAEOS runtimes without asking the Founder a single engineering question?*

**The answer: Yes for behavioral compatibility, with the same standing conditions PAEOS-8.1 already ratified — and this document closes the last composition-level gap that sat between the parts and the whole.**

### §14.1 What "byte-compatible" means here (and its honest boundary)

PAEOS-8.1's readiness verdict established that every *kernel behavior* is a single-valued function of store state: promotion (K1 + T1–T6), rendering (F-1), validation (Z-2), integration scope (D-1), amendment ordering (E-1), and the L-state↔lattice mapping (G-1) are all deterministic. PAEOS-9 adds the **composition determinism** those depended on being wired correctly: the pipeline order (§2), the per-stage inner loop (§2.2), the SCOPE resolution (§4.3), the graph-as-projection consistency model (§5.0), the deterministic Task Package (§6.6), and the handoff protocol (§7.4).

The precise, honest claim:

- **Byte-compatible at the determinism-pinned surfaces:** the ledger event stream, the compiled `content_hash`, the rendered prompt (F-1), the TaskPackage projection, the seal hash, and the replay of any recorded event log — two conformant builds produce **byte-identical** output (this is the founder's core guarantee, extended end-to-end).
- **Behaviorally compatible above that surface:** worker *reasoning* is not byte-identical (it is hosted intelligence, model- and version-dependent), but it is **fenced by evidence the kernel re-runs** (K1, T2), so non-determinism there can never become divergent *canon*. Two teams' runtimes will make the same *promotion decisions* on the same evidence even if their workers reason differently getting there.

That distinction is not a gap — it is the design (§1.5): PAEOS pins the *governance* byte-for-byte and hosts the *intelligence* freely. Byte-compatible governance + fenced cognition is the strongest compatibility a system that hosts intelligence can offer, and it is sufficient for two independent runtimes to interoperate on one ledger.

### §14.2 Remaining ambiguities (the honest residual — none block the start, all are pre-flagged)

No *new* engineering question is opened by this document. The open items are exactly those the corpus already flags, restated with the phase that must close each:

1. **PAEOS-9 numbering** — *resolved this session* (§0.3): PAEOS-9 = Execution Architecture; bootstrap → PAEOS-9A. Mechanical rename pending.
2. **Claude Code scoped-workspace + MCP feasibility** — the one load-bearing external dependency (§11.2); **Day-1 spike (B0.0)** before Phase 1 is planned. If false, the agent-runtime contract reopens.
3. **Ledger backup / DR** — open item (§9.3, §12.4); **before rung R3**.
4. **Event/schema versioning + projection migration** — standing caution (§9.3); **assign Phase 1**.
5. **Graph-store realization** — this document specifies graphs as **ledger projections** (§5.0), which is a complete, buildable answer (Postgres projections); whether to add a dedicated property-graph engine for scale is a **Phase-3 optimization**, not a Phase-0/1 question. Not a blocker.
6. **SAKG interface** — consumption contract specified (§10.1); SAKG itself is future and out of scope; PAEOS runs fully without it (§10.4). Not a blocker.
7. **Deferred taxonomies** (weight-class defaults, static blast-radius classifier rules, scar-retrieval-at-scale, concrete durable-execution engine) — each already deferred with a revisit trigger (PAEOS-7 §10, PAEOS-8 §3); each needs its own lifecycle run before the phase that consumes it, **none before B0.1**.

Every item above is a **sequencing requirement, not an engineering question the Founder must answer now** — precisely the standing PAEOS-8.1 reached, now confirmed at the composition level.

### §14.3 The complete implementation corpus

With this document, the corpus that forms the complete implementation specification — sufficient for two independent teams to build interoperable runtimes without a Founder engineering question — is:

**Constitutional layer (what is lawful):**
- PAEOS-0 Foundations · PAEOS-1 Architecture · PAEOS-2 Workflow · PAEOS-3 Bootstrap · PAEOS-3.5 Adversarial Ratification
- **PAEOS-4 v1.1** (the frozen kernel — the canonical build target per Z-1.3) · PAEOS-4.5 Reference Implementation
- PAEOS-5 Backlog · PAEOS-5.5 Implementation Audit · PAEOS-6 Hidden Assumptions

**Runtime layer (what the runtime is and why it is safe):**
- PAEOS-7 Runtime Architecture · PAEOS-7.5 Runtime Threat Model · PAEOS-7.6 Runtime Interface Contracts

**Execution & build layer (what we build, in what order, and how it all composes):**
- PAEOS-8 Implementation Playbook · PAEOS-8.1 Runtime Clarifications
- **PAEOS-9 Execution Architecture (this document)** — the composition/dataflow spec
- **PAEOS-9A Runtime Bootstrap** — the session-scope context-compiler appendix

**Operational doctrine (the lifecycle the runtime executes):**
- `operations/ENGINEERING_LIFECYCLE.md` v1.1 (19 states) · `operations/WORKFLOW_STATE_MACHINE.yaml` (executable form)
- `operations/ROLE_RESPONSIBILITIES.md` · `operations/PROMPT_TEMPLATES.md` · `operations/FOUNDER_IMPLEMENTATION_PRINCIPLES.md`
- `methodology/PAEOS-CONSTITUTIONAL-ENGINEERING-LIFECYCLE.md` (constitutional crosswalk)

**Living stores (populated as the system runs):** the ledger, CAS, scars (`reviews/`), proposals (`proposals/`), debt (`ledger/debt/`), and the Wave-0 worker packages (`backlog/packages/wave-0/`).

### §14.4 Closing

PAEOS-9 is the bridge the brief asked for: not another specification of *what PAEOS is*, but the definition of *how PAEOS executes itself* — one task's journey from a Founder's submission, through a compiled constitution and a hosted intelligence, past evidence the kernel itself reproduces, to a seal that supersedes but never mutates, and finally into a retrospective that changes the system before the next task begins. Every mechanism it invokes was already law; its only new content is the wiring that makes them one machine. The lifecycle is the operating system; the runtime merely executes it; the constitution governs it; the workers never own the reasoning they perform; and the intelligence is hosted, never embedded.

> *This artifact is itself a legal goal for the runtime it describes (FR-9). Once a Phase-1 runtime exists, PAEOS-9 should be re-derived, adversarially ratified, and sealed by the system it specifies — the execution architecture executed by the execution it architected.*

---

*End of PAEOS-9 — Execution Architecture. The pipeline is defined end to end: Founder → compile → host → build → verify → adversary → seal → retrospect → self-update → next cycle. Nothing becomes canonical except by evidence the kernel reproduces; nothing changes the kernel except by a human signature. Build B0.0 today, B0.1 tomorrow.*
