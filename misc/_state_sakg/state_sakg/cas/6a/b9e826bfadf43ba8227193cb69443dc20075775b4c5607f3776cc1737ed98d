# Phase 3 Architectural Review (CER-1) — what the implementation revealed

**Date**: 2026-08-01 · **Scope**: Phase 3 (B2.O..B2.Q, CER-1 EvidenceSource, WorkerTransport trilogy
R5.1–R5.3, IP-0008 Universal WorkerTransport) · **Mode**: governance review, **no implementation** · **Author role**: Auditor
(recommends; does not legislate — CER-5).

The question: has *building* Phase 3 revealed architectural laws, abstractions, or constitutional
improvements not visible when PAEOS was designed? Method below is the founder's five phases; each
conclusion is falsified before it is kept (CER-1).

---

## Phase 1 — First principles: derive, then falsify against what exists

Deriving the architecture *cold* from the constitution's axioms and forcing requirements, then
comparing to the built system:

| Constitutional source | What it *forces* | What now exists | Verdict |
|---|---|---|---|
| Axiom **"runtimes churn, artifacts persist"** + FR-1 (TCB minimality) | The vendor runtime must be **replaceable without touching the durable core** ⇒ a hard boundary between core and vendor | `WorkerTransport`/`AgentRuntime` ports + `runtime/transports/` adapters; **adding the whole MCP SDK touched zero core code** | **Derived, not invented.** The transport boundary was *latent in the axiom* — Phase 3 made it explicit and *proved* it. |
| FR-4 (evidence-gated) + "generation cheap, **verification scarce**" | Evidence must actually *discriminate* — a check that passes regardless of the change is worthless | B2.O vacuous-evidence gate (same result with/without the change ⇒ REMAND); CANARY-0002 | **Refinement the constitution did not state.** FR-4 said "evidence-gated"; it did **not** say "probative." Phase 3 found the *vacuous-evidence* class. |
| FR-3 (independent adversary) | The adversary's verdict must **gate the seal**, not merely be recorded | B2.K (seal requires adversary PASS; IP-0007) | **Latent defect surfaced.** The design *assumed* FR-3; the loop *ignored* the verdict until Phase 3. |
| MR (**separation of powers**) | Applies wherever authority is exercised — including **memory creation** | Trigger (Court) → Author (Evolution 15–17) → Commit (Kernel); IP-0005 | **Generalisation.** Separation-of-powers was stated for *building* (builder≠verifier≠adversary≠sealer); Phase 3 found it also governs *memory*. |
| Axiom **"artifacts durable, context ephemeral"** | Data has a *lifetime*, and lifetime dictates ownership | L0–L5 ontology (IP-0006); `ExecutionContext` (L1) vs `Scar` (L3) | **Refinement.** The design had durable vs derived (ledger vs projections); Phase 3 found the full ephemeral→historical gradient. |
| FR-1 (frozen kernel) + F1/F2/F3 CI gates | Architectural truth should be **checked**, not trusted | AI-001..; IP-0010 (invariants-as-CI) | **Generalisation** of the CI gates into "architecture as an enforced property." |

**Falsification of what exists** (do not assume it is right):

- *Is `WorkerTransport` over-abstracted?* No — three real, different adapters use it (file, CLI, MCP).
  **But** a real seam-crack: `WorkerTransport`'s verbs (`submit`/`status`/`receive`) are **evidence-
  typed**, while the name implies *worker execution*. Execution actually lives in the separate
  `AgentRuntime` port; `ClaudeCliWorkerTransport` implements *both*. So "WorkerTransport" is really an
  **EvidenceTransport**, and worker *execution* is a distinct port. Not a defect (a class may satisfy
  two ports), but a **naming/segregation smudge** (see Phase 5).
- *Is `EvidenceSource` right?* Yes — minimal, read-only, and the runtime depends on nothing else
  (grep-proven). Survives.
- *Is the memory trilogy right?* Yes — B2.G removed the loop's inline scar; one committer holds.
- *Do ports live where the core can own them?* **Mostly** — but `ScarBackend`/`CourtBackend` Protocols
  are defined in `runtime/transports/mcp/servers.py` (an adapter module), not in a core `ports`
  location. A port defined inside an adapter is a latent inversion (see Phase 5, improvements).

**Phase 1 conclusion:** the built architecture is *consistent with* a cold re-derivation — and in four
places the implementation **discovered refinements the constitution implied but did not state**
(probative evidence, adversary-gated seal, memory separation-of-powers, the lifetime gradient). Two
smudges (WorkerTransport naming; port-in-adapter) are improvements, not defects.

---

## Phase 2 — Pattern discovery: recurring structures now behaving as laws

Searching the implementation, these recur so consistently they read as principles, not accidents:

1. **Port / Adapter separation (narrow waist).** Eight Protocols — `LedgerStore`, `CasStore`,
   `Projector`, `AgentRuntime`, `CourtBackend`, `ScarBackend`, `EvidenceSource`, `WorkerTransport` —
   are *ports the core owns*; storage/vendor/transport implementations are *adapters* the core never
   imports. This is Ports-and-Adapters (hexagonal), and it is **pervasive**, not local.
2. **Least-privilege interface (interface segregation by authority).** The core depends on the
   *smallest* facet it needs: the `SoftLoop` reads evidence through the **read-only** `EvidenceSource`,
   never the writable `WorkerTransport`. Read and write are different interfaces to the same data.
3. **Vendor isolation / dependency inversion.** Churny things (the `claude` CLI, the MCP SDK) sit
   behind ports under `runtime/transports/`; the core depends on abstractions. AI-001.
4. **Deny-by-default gates, everywhere.** Adversary gate (BLOCK/unclear ⇒ remand), vacuous gate,
   fail-safe classification (unresolvable path ⇒ HARD), quarantine on over-broad scars, empty
   calibration ⇒ alarm. *Absence of an explicit affirmative ⇒ refuse.*
5. **Recursive separation of powers.** The same governance shape appears at three layers: **building**
   (roles), **memory** (trigger/author/commit), **amendment** (propose/ratify, runtime never applies).
6. **Lifetime-scoped ownership.** Every datum has a lifetime class (L0–L5) and exactly one owning
   authority; promotion between classes is a *verified transition*, not a copy.
7. **Falsify-then-formalise.** Nearly every Phase-3 task followed: build → CER-1 falsification →
   proposal → ratification → refinement. The *process itself* is a stable pattern (Phase 3, §Loop).

Patterns 1–3 are facets of one structure; 4–6 are facets of one governance model; 7 is the engine.

---

## Phase 3 — Architectural compression: are these one larger principle?

**Compression A — the eight ports + EvidenceSource + WorkerTransport are one concept: the runtime is
a *policy kernel over ports*.** `EvidenceSource` is literally the read-facet of `WorkerTransport`;
both are ports; all eight ports share the rule "core owns the port, adapters are leaves, core imports
no adapter." This is the **OS the constitution promised**, made literal: *ports = syscalls, adapters =
drivers, the SoftLoop = the kernel scheduler of policy.* PAEOS-7 already said "narrow-waist Protocols /
build the constitution, buy the plumbing" — Phase 3 **proved** it (a whole SDK added at a leaf). So
this is not new law; it is **existing law, now empirically validated and unifiable under one named
principle: *Port Independence*** — the core depends only on ports, never adapters or vendors.

**Compression B — L0–L5 + the memory trilogy + read-only interfaces are one concept: a *data-
governance model*** = (lifetime class × owning authority × access facet) for every datum. "Who may
touch this, for how long, through which interface" is *one* question asked of scars, evidence,
execution context, ledger, and constitution alike. IP-0004/0005/0006 are three views of it.

**Compression C — AI-001.. + F1/F2/F3 + the memory/seal gates are one concept: *architecture-as-
enforced-property*.** Structure is not a diagram to trust but a set of checks CI runs (IP-0010).

**The single largest principle** behind A+B+C: **PAEOS separates POLICY from MECHANISM, and the
separation is itself a checked invariant.** Policy (what must be true — ownership, lifetimes, gates,
port-independence) lives in the core and the constitution; mechanism (how — vendors, transports,
storage) lives in swappable leaves; and the boundary between them is *enforced*, not hoped. This is
the OS kernel/driver split turned into constitutional law. **It was predicted by the constitution
("hosts intelligence, does not contain it"); Phase 3 is its proof of existence.**

---

## Phase 4 — Proposal discovery (only what CER-1 justifies)

Most discoveries are **clarifications of existing law** or **refinements to the invariants registry**, not new
proposals (CER-6: derive, don't invent). Specifically fold into the invariants registry (re-filed as **IP-0010** after IP-0008 was re-used for the ratified WorkerTransport architecture):
**AI-010 Port Independence** (core imports no adapter/vendor; verifier = grep excluding
`runtime/transports/`), and **AI-011 Least-Privilege Interface** (the core depends on the minimal
read-only facet of a port). No new proposal for Ports-and-Adapters — PAEOS-7 already states it.

**One genuinely new proposal is justified:** the *Constitutional Evolution Loop* — the distinct,
continuous process (build → CER-1 falsify → proposal → ratify → refine) that produced every Phase-3
amendment. It is **not** the 19-stage goal lifecycle (which executes one goal); it is a second,
higher-order lifecycle governing how PAEOS's *own architecture* evolves. The mechanism already exists
(FR-2 amendment path + CER-1..6); what is missing is **naming and characterising the loop as a
first-class process**. Filed as **PAEOS-IP-0009** (accompanying). It invents no mechanism (CER-6-safe);
it names an existing, unnamed, dominant process. It does **not** supersede any proposal; it is the
companion IP-0010 §6 recommended.

---

## Phase 5 — If PAEOS were designed again today: discoveries vs improvements vs mistakes vs clarifications

**Discoveries** (the implementation revealed; not visible at design time):
- Port Independence is a *consequence* of "runtimes churn," not a design choice — and it is *provable*
  (adding a vendor SDK is a leaf edit).
- **Probative ≠ reproducible.** A whole evidence-defect class (vacuous evidence) that FR-4 did not name.
- Memory creation has its own separation of powers (trigger/author/commit).
- Data **lifetime** (L0–L5) is a first-class architectural axis, not a storage detail.
- PAEOS runs **two lifecycles** — goal execution *and* constitutional evolution.
- Architecture is a set of **enforced properties**, not a diagram.

**Improvements** (do better, non-defect):
- Rename `WorkerTransport` → an **EvidenceTransport** + keep worker *execution* as `AgentRuntime`;
  the "worker" name over-claims. Segregate the two ports explicitly.
- Move core-owned ports (`CourtBackend`, `ScarBackend`, `EvidenceSource`, `WorkerTransport`) into a
  single `runtime/ports.py` (or `kernel`-adjacent) so a port is never *defined inside an adapter*.
- Generalise AI-001 to **AI-010 Port Independence** (all vendors, not just MCP) in IP-0010.

**Implementation mistakes** (honest self-audit of Phase 3):
- The staged-evidence **hollow seals**: it took ~6 live R4 runs to discover the seal ignored the
  adversary (B2.K) and that echo evidence was vacuous (B2.O). The *gaps were real*, but a colder
  Phase-1 derivation ("does the seal actually require an adversary PASS?") would have found B2.K
  before the live runs.
- The **`mcp/` namespace collision** with the official SDK — a naming mistake avoidable at design
  (never name a local package after a likely dependency).
- A **`git add -A`** that swept founder doc-track files into a commit (caught and reverted) — a
  process error; staging must always be explicit.
- The **B2.Q unify attempt was unsound** and only caught by falsification — the premise ("calibration
  can reuse the runtime discrimination gate") ignored that a calibration canary has no real artifact.
  Falsification worked, but the initial reach was wrong.

**Constitutional clarifications** (the constitution already implied these; state them):
- "runtimes churn, artifacts persist" ⇒ Port Independence.
- MR ⇒ memory-creation separation of powers.
- FR-4 ⇒ evidence must be *probative*, not merely reproducible.
- FR-3 ⇒ the adversary's verdict *gates* the seal.
These need no amendment — only sharper wording in PAEOS-7 (an execution-architecture clarification).

---

## Summary for the founder

- **The architecture is sound and matches a cold re-derivation** — and the implementation *proved* the
  narrow-waist / OS-kernel structure the constitution predicted (adding a vendor SDK touched zero core).
- **Four refinements the constitution implied but did not state** were discovered: probative evidence,
  adversary-gated seal, memory separation-of-powers, the L0–L5 lifetime gradient. All are already
  implemented + ratified; PAEOS-7 wording should be sharpened (clarification, not amendment).
- **One unifying principle**: *policy/mechanism separation, itself enforced* — the OS made law.
- **New proposal**: **PAEOS-IP-0009** — name the *Constitutional Evolution Loop* (invents no mechanism).
- **Fold into IP-0010** (the re-filed invariants registry): AI-010 Port Independence, AI-011 Least-Privilege Interface.
- **Two improvements** (rename `WorkerTransport`; relocate core ports out of the adapter module) and an
  honest mistake log. **No implementation, no code, no constitutional edit** — recommendation only.
