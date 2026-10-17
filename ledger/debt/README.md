# Architectural Debt Ledger

The persistence channel for CER-3 (Constitutional Execution Rule 3, Engineering Lifecycle
v1.1). **Whenever an implementation deliberately chooses a non-ideal solution, it is recorded
here.** Architectural debt MUST NOT exist only inside conversation history — PAEOS-0 axiom A2
(artifacts durable, context ephemeral) and the Sentium buried-decisions scar make this
non-negotiable: undocumented compromises are exactly the failure PAEOS exists to prevent.

## What a debt entry is

A deliberate, evidenced compromise plus its repayment plan. In kernel terms it is a recorded
compromise / open incident (K7) — a debt is *open* until repaid or explicitly written off.
Recording debt is not a failure; **hiding** it is.

## Naming

`ledger/debt/DEBT-NNNN.md`, zero-padded, monotonic.

## Required fields (every entry)

1. **Compromise** — the non-ideal choice made.
2. **Reason** — why it was necessary now.
3. **Ideal solution** — what should be done instead.
4. **Repayment conditions** — the evidence/trigger that makes repayment due.
5. **Priority** — low / medium / high / blocking-before-X.
6. **Estimated impact** — cost of leaving it unpaid.

## Distinction from Proposals

A **Proposal** (`proposals/`) recommends improving PAEOS itself (the constitution). A **Debt
entry** records a compromise in an *implementation* against the current constitution. A debt
whose ideal solution requires a constitutional change SHOULD also file a Proposal and link it.

## Index

> **Integrity warning (2026-09-09):** DEBT-0105 proves that several historical identifiers no
> longer match this index after partial-workspace autonomous allocation. Do not treat this index as
> authoritative until the reconciliation in DEBT-0105 is complete. Existing files are preserved.

- `DEBT-0001.md` — Provisional genesis parameters set without tournament evidence.
- `DEBT-0002.md` — B0.0 Day-1 spawnability spike (RESOLVED).
- `DEBT-0003.md` — Production persistence backend (SQLite built, Postgres deferred).
- `DEBT-0004.md` — Constitutional corpus not yet populated; clause-id scheme not yet ratified.
- `DEBT-0005.md` — Evidence reproduction runs without OS-level sandboxing.
- `DEBT-0006.md` — Consolidate `SealAuthority` Index Under `Projector[SealRecord]`.
- `DEBT-0007.md` — Dual TCB Prefix Definitions (`tcb_diff.py` vs `classifier.py`).
- `DEBT-0008.md` — Live `AgentRuntime` CLI Invoker Deployment Seam.
- `DEBT-0009.md` — Constitutional Amendment Hard-Loop Implemented in Runtime (Z2) Without Kernel (Z0/Z1) Gate or Ledger Persistence.
- `DEBT-0010.md` — Duplicated Context Compilation Logic (`build_prompt` vs `compile_context`).
- `DEBT-0011.md` — Evolution Engine Stage-17 Memory Update Bypasses Kernel Gate & Reference Monitor.
- `DEBT-0012.md` — Silent Zero-Cost Fallback in CLI Output Parser (`ClaudeCodeRuntime`).
- `DEBT-0013.md` — Standing Canary Calibration Category Hardcoding & Unratified Pre-Flight Gate.
- `DEBT-0014.md` — Unenforced Ephemeral Memory Boundaries at CAS/Ledger Substrate Level.
- `DEBT-0015.md` — Control Plane Duplication Between In-Memory CLI and Self-Host Drivers.
- `DEBT-0016.md` — Physical Repository Tree Duplication in Probative Verification Workspace.
- `DEBT-0017.md` — Ad-hoc Serialization of Evidence Bundles in Adversary Workspace Context.
- `DEBT-0018.md` — Continuous Scheduler Global Governor Halts Lack Kernel Ledger Event Logging.
- `DEBT-0019.md` — Autonomous evidence path blocked in headless builder sessions (`_allowed_tools` omits `Bash`) (RESOLVED).
- `DEBT-0020.md` — T2 evidence result normalization lacks formal specification (IP candidate) (RESOLVED — IP-0011 ratified).
- `DEBT-0021.md` — Over-broad tool authority in session tool allow-list (`Bash` granted to non-Builder sub-sessions) (RESOLVED).
- `DEBT-0022.md` — Artifact selection prefers compiled `.pyc` over source; fragile adversary materialization (RESOLVED).
- `DEBT-0023.md` — Fixed write-scope coupling in autonomous intake generation drops valid deliverable files (OPEN).
- `DEBT-0024.md` — Traceability broken by uncommitted `PAEOS-9-execution-architecture.md` dependency in `SAEOS-1` (OPEN).
- `DEBT-0025.md` — Parallel backlog format duplication (YAML DAG vs. JSON Intake list) (OPEN).
- `DEBT-0105.md` — Debt-ledger identifiers reused and historical entries displaced (BLOCKING).
- `DEBT-0106.md` — IP-0017 Founder hierarchy resolved; derived projection reconciliation remains OPEN.
- `DEBT-0107.md` — Premature L11 freeze and competing acceptance mechanisms (BLOCKING).
- `DEBT-0108.md` — Self-attested completeness and unenforced manifest fields (BLOCKING).
- `DEBT-0109.md` — Candidate environment/restart identity gaps (BLOCKING).
- `DEBT-0110.md` — Mutable/incomplete L14 scope and synthetic accounting (BLOCKING).
- `DEBT-0111.md` — Corrupt taint metadata fails open (HIGH).
- `DEBT-0112.md` — Test-only worker authority stack returns successful no-ops (BLOCKING BEFORE ACTIVATION).
- `DEBT-0113.md` — Duplicate sandbox kernels leave Court on weaker implementation (BLOCKING).
- `DEBT-0114.md` — Routing-policy bypass permits homogeneous review (BLOCKING).
- `DEBT-0115.md` — Provider workers inherit host credentials and lack read confinement (CRITICAL).
- `DEBT-0116.md` — Governed Codex Builder exhausted usage quota before candidate production (OPEN).
- `DEBT-0117.md` — Autonomous Gap Adaptation and Delegated Self-Remediation capability not yet physically demonstrated (OPEN · NOT P1-BLOCKING).
- `DEBT-0118.md` — Chat-Bridge compatibility response timeout before provider candidate production (OPEN / historical).
- `DEBT-0119.md` — Governed planner handoff deadline exceeded before provider candidate production (OPEN / historical).
- `DEBT-0120.md` — Isolated Builder identity repair could not affect parent runtime before L12 (OPEN / historical).
- `DEBT-0121.md` — Parent runtime identity binding was absent before candidate collection (OPEN / historical).
- `DEBT-0122.md` — Candidate archive rejected developer-only `.claude` symlink projection (REMEDIATED).
- `DEBT-0123.md` — Provider prerequisite candidate correctly failed the unrelated full P1 manifest scope (OPEN / expected remand).
- `DEBT-0124.md` — Host cannot launch the destination-scoped confined provider process (OPEN / provider prerequisite blocker).
- `DEBT-0156.md` — Reasoning Economy, Failure Locality, and Execution Efficiency (HIGH / SYSTEMIC / NON-P1-BLOCKING).
- `DEBT-0157.md` — Builder Produced No Artifact — Write-Scope or Agent Failure (OPEN / autonomous friction record).
- `DEBT-0158.md` — Semantic Authority, Founder Escalation, and Convergence Classification (HIGH / SYSTEMIC / NON-P1-BLOCKING).
- `DEBT-0249.md` — PAEOS Hardening — Soft Doctrine to Executable Law (HIGH / SYSTEMIC / POST_P2 / NON_P2_BLOCKING / OPEN / ACTIVE_PROGRAMME).
- `DEBT-0250.md` — PAEOS Semantic Intent Preservation & Design Completeness (CRITICAL / SYSTEMIC / IMMEDIATE_POST_P2 / QUALIFIED & COURT_SEALED).
- `DEBT-0261.md` — Dependency-Aware Admission and Goal-Isolated Concurrent Execution (HIGH / BLOCKING BEFORE UNQUALIFIED MULTI-GOAL CONCURRENCY ACTIVATION / OPEN / FORMALIZED, NOT IMPLEMENTED).
- `DEBT-0262.md` — Founder `resolve` CLI verb is absent (MEDIUM / IMPLEMENTATION DEBT / NON-BLOCKING TO CURRENT DIRECT-INSTRUCTION PRECEDENT / OPEN).
