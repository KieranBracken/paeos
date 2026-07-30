# PAEOS Improvement Proposals

The formal channel for CER-2 (Constitutional Execution Rule 2, Engineering Lifecycle v1.1).
**No implementation may silently improve the constitution.** Every discovered improvement to
PAEOS — the kernel, lifecycle, authority, invariants, or any constitutional law — is written
here as a proposal, and left for the **founder** to ratify or reject.

## What a proposal is (and is not)

A proposal is a **recommendation**, not a change. In kernel terms it is a *draft
amendment-goal awaiting founder ratification* (K7 / §14.5). Writing a proposal changes
nothing; implementation continues regardless of whether it is later accepted. This is the
separation of powers (CER-5): **the runtime may recommend; it may never legislate.**

## Naming

`proposals/PAEOS-IP-NNNN.md`, zero-padded, monotonic (PAEOS-IP-0001, PAEOS-IP-0002, …).

## Required fields (every proposal)

1. **Observation** — what was noticed.
2. **Current behaviour** — what PAEOS does today.
3. **Proposed improvement** — the change, precisely.
4. **Justification** — why it is better (which invariant/axiom it serves).
5. **Risks** — what could go wrong.
6. **Backwards compatibility** — effect on existing artifacts/stores/conformance.
7. **Constitutional impact** — which documents/§§ it would amend; whether kernel-surface
   (needs §14.5 ceremony + founder) or operational.
8. **Recommendation** — ratify / reject / defer, with the smallest amendment.

## Lifecycle of a proposal

`drafted (here)` → routed to the founder decision queue (K7) → **founder ratifies** (becomes
a constitutional amendment, applied via the normal amendment lifecycle A-06) **or rejects**
(recorded, closed). A proposal MUST NOT be applied by any agent; only a founder-ratified
amendment may change constitutional law.

## Index

- `PAEOS-IP-0001.md` — Capability-based skill loading (CAP-1). Status: **awaiting founder
  ratification** (source finding: `reviews/7-skills-as-capabilities.md`; also excluded from
  PAEOS-4 v1.1 pending ratification per §16).
- `PAEOS-IP-0002.md` — Define `EvidenceRef` (used but undefined in PAEOS-7.6 §4/§5). Status:
  **RATIFIED BY FOUNDER** (2026-07-27). `EvidenceRef = Hash` added to 7.6 §3; `TransitionRequest`
  + `CapabilityToken` completed in B0.4 (`kernel/types.py`).
- `PAEOS-IP-0003.md` — Pin the `StageId` legal-edge table: weight-class semantics + failure-edge
  scope (source: Task B0.5). Status: **RATIFIED BY FOUNDER** (2026-07-27). Failure edges are
  kernel-routed (not `is_legal`); ROUTINE/Trace-A adds `TRIAGE→IMPLEMENT` + `RAW→INTAKE`.
  Implemented in `kernel/lifecycle.py`; canonical table added to PAEOS-7 §4.1.
- `PAEOS-IP-0004.md` — Ephemeral Execution Context vs. Constitutional Institutional Memory (source:
  Task B2.F). Status: **RATIFIED BY FOUNDER** (2026-07-30). Establishes **L1 Ephemeral Execution
  Context** (run-scoped operational retry state on the TaskPackage; destroyed at run-scope end; never
  institutional memory) as the operational complement to IP-0005. Enforced by **Task B2.G**.
- `PAEOS-IP-0005.md` — Constitutional Memory Authority & Separation of Powers (source: Task B2.F +
  founder-directed first-principles analysis). Status: **RATIFIED BY FOUNDER** (2026-07-30). The
  memory trilogy: **Trigger** (Verification Court) → **Author** (Evolution Layer, stages 15→17) →
  **Commit** (Kernel TCB, stage 17). Operational execution (`SoftLoop`/`Builder`) may never author or
  commit institutional memory. Enforced by **Task B2.G**.
- `PAEOS-IP-0006.md` — Constitutional Knowledge Lifetime Ontology (L0–L5). Status: **RATIFIED BY
  FOUNDER** (2026-07-30). A second classification axis (Purpose × Lifetime): L0 Scratch (Worker),
  **L1 Ephemeral Execution Context (Runtime)**, L2 Runtime Projection (Runtime), **L3 Institutional
  Memory (Evolution)**, L4 Constitutional Knowledge (Founder), L5 Historical Truth (Kernel).
  Promotion between classes only via verified transitions (L1→L3 via Stage 17). B2.G enforces the
  L1/L3 boundary; full per-artifact `lifetime_class` annotation is a follow-on conformance pass.
- `PAEOS-IP-0007.md` — **security-critical**: the soft loop **seals despite a blocking adversarial
  dissent** (FR-3 toothless), found via the live R4 runs. Status: **awaiting founder ratification**.
  Recommends gating the seal on a machine-readable adversary verdict (REMAND on BLOCK) as **B2.K**;
  companion gaps B2.J (materialise agent workspace context) + live-evidence flow. **Not implemented.**
