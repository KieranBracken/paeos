# 01_CANONICAL_INVENTORY: The 19-Layer Execution Doctrine

This document serves as the canonical inventory of the 19-layer execution doctrine as defined in `operations/ENGINEERING_LIFECYCLE.md` (v1.1) and `spec/PAEOS-9-execution-architecture.md`.

## The 19 Canonical Execution Layers

| Layer | Name | Runtime `StageId` | Lattice Mapping | Purpose & Responsibilities |
|---|---|---|---|---|
| **L01** | Intake | `INTAKE` | `declared` | Accepts tasks (Goal submissions) via Founder or automated sources. |
| **L02** | Triage | `TRIAGE` | `declared` | Assigns ceremony depth (Trace-A vs Trace-B) and weight class. Routes trivial tasks to fast path. |
| **L03** | First-Principles Re-Derivation | `RE_DERIVE` | `declared` | Ensures the goal is grounded in reality and fundamental truths before exploring solutions. Derives constraints from first principles. |
| **L04** | Ambitious Ideation | `IDEATE` | `declared` | Generates a wide candidate set of solutions. |
| **L05** | Frontier Research | `RESEARCH` | `declared` | Researches domain knowledge, literature, and precedence. May execute quarantined external queries. |
| **L06** | Trade-off Analysis | `TRADEOFF` | `declared` | Analyzes trade-offs of ideated solutions (time vs cost vs correctness). |
| **L07** | Trade-off Mitigation | `MITIGATION` | `declared` | Selects mitigations for accepted trade-offs. |
| **L08** | System Design | `DESIGN` | `declared` | Produces the formal architectural design artifact (components, interfaces, schemas). |
| **L09** | Multi-Perspective Critique | `CRITIQUE` | `declared` | Collaborative, builder-side critique (8 stances: Security, Performance, Simplicity, Maintainability, Testability, Backward Compatibility, Constitutional Alignment, Functionality) to improve the design before formal review. |
| **L10** | Adversarial Review | `ADVERSARIAL_REVIEW` | `declared` (gate) | Design-time adversarial falsification attempt. Emits RATIFY, RATIFY-WITH-AMENDMENTS, or REJECT. |
| **L11** | Formal Planning | `PLAN` | `declared` | Freezes the implementation contract and creates an actionable plan. |
| **L12** | Branch Implementation | `IMPLEMENT` | `speculated` → `executed` | Implements the frozen L11 contract on an isolated worktree. |
| **L13** | Verification (The Court) | `VERIFY` | `executed` → `verified` | Reproducible, deterministic verification of artifacts. The kernel re-runs deterministic evidence. |
| **L14** | Independent Audit | `VERIFY`/`ADV_REVIEW` | `verified` (gate) | Implementation-time adversarial review. Must use a decorrelated model family (A-08). |
| **L15** | Documentation & Ledger | `LEDGER_SYNC` | `verified` → `integrated` | Writes the permanent ledger and documentation records. |
| **L16** | Promotion Decision | `SEAL` | `integrated` | The final merge and idempotent sealing of the execution block (K8). |
| **L17** | Retrospective & CER | `RETROSPECT` | (Evolution Loop) | Root cause analysis and the 6 CER questions. Generates scars to become future guards. |
| **L18** | Knowledge Extraction | `MEMORY_UPDATE` | (Evolution Loop) | Extracts versioned skills, templates, and patterns. |
| **L19** | Constitutional Evolution | `IMPROVE_RUNTIME` / `RESTART` | (Evolution Loop) | Hard loop for TCB changes. Requires founder ratification signature. |

## Core Principles of the Pipeline

1. **The loop of loops**: The outer loop walks the spine (L01-L19). The inner loop (kernel minting, context compilation, package compilation, sandboxed worker execution, and kernel gating) repeats *at every state*.
2. **Backward-flowing Evidence**: Every gate provides back-pressure and can remand a goal to an earlier state.
3. **Trust Zones**: The loop crosses three trust zones on every execution: Kernel (Z1) -> Context/Package Compilation (Z2) -> Worker Runtime (isolated Z2).
4. **Feed-Forward Learning**: The Evolution Loop (L17-L19) mutates the context of all future tasks by updating scars, skills, and the constitution, making PAEOS a self-improving system.
