# RB-0009 — Organizational Cognition & Capability Brokering Architecture

Status: **RESEARCH** · Level: **Architecture / Meta-Runtime** · Track: **Cognitive Foundations**
Prerequisites: RB-0008 (Autonomous Technical Leadership), PAEOS-7 (Runtime Architecture)

---

## 1. Executive Summary

PAEOS currently models autonomous execution as a pipeline of sequential stages (`DESIGN` → `PLAN` → `IMPLEMENT` → `VERIFY` → `ADVERSARIAL_REVIEW`).

While this prevents unvalidated code from reaching main, it suffers from a fundamental structural flaw:

> **PAEOS assumes that every engineering obstacle has an implementation solution, and grants stages local authority over their own remediation.**

In reality:
1. **Not all obstacles are implementation bugs**: Some require research, architectural simplification, capability development, or founder escalation.
2. **Local vs. Global Optimization**: Each role in an engineering organization operates under distinct incentives, biases, and fears. Giving any single role authority to prescribe the solution biases the system toward local optima (e.g. Builder hacking code, Designer over-abstracting).

This research item establishes the architectural foundation for **Organizational Cognition**: replacing local retry loops with a **Capability Broker** that aggregates diagnostic signals (`CapabilityRequest`) from roles with *voice, but not authority*, and routes them to global organizational responses.

---

## 2. Core Principles

### Principle 1: Voice vs. Authority
No operational stage (Builder, Planner, Designer) possesses the global perspective required to dictate organizational response. 
- **Voice**: Stages emit structured diagnostic signals (`CapabilityRequest`) describing what is blocking them and what trade-offs they observe.
- **Authority**: The **Capability Broker** evaluates requests across all stages, assesses ROI, merges duplicates, and decides the global response (Simplify Design, Re-Plan, Research, Build Substrate Tool, or Escalate).

### Principle 2: Role-Incentive & Blind-Spot Modeling
Every agent role carries a distinct cognitive profile:
- **Builder**: Objective: Working implementation. Bias: Prefers simpler code. Fear: Being blocked.
- **Designer**: Objective: Elegant architecture. Bias: Over-abstraction. Fear: Technical debt.
- **Planner**: Objective: Schedule completion. Bias: Underestimating complexity. Fear: Slippage.
- **Adversary**: Objective: Expose flaws. Bias: False-positives over false-negatives. Fear: Undiscovered regressions.

Every stage self-reflection must explicitly answer:
> **"What trade-offs am I blind to because of my role?"**

---

## 3. The Capability Broker Subsystem

```text
               Stage Execution (Designer / Planner / Builder / Verifier)
                                       │
                                       ▼
                       Emits: [ CapabilityRequest ]
                                       │
                                       ▼
                         ┌──────────────────────────┐
                         │    Capability Broker     │
                         │ ─── Aggregates Requests  │
                         │ ─── Merges Duplicates    │
                         │ ─── Evaluates ROI        │
                         └─────────────┬────────────┘
                                       │
         ┌─────────────────────────────┼─────────────────────────────┐
         ▼                             ▼                             ▼
 [ Local Re-Route ]           [ Capability Building ]       [ Organizational Escalation ]
 ├── Simplify Design          ├── Build Substrate Tool      ├── Escalate to Research (RB)
 ├── Decompose Plan           └── Mint New Agent Skill      ├── Escalate to Proposal (IP)
 └── Re-assign Builder                                      └── Escalate to Founder (A4)
```

---

## 4. Demand-Driven Ecosystem Self-Improvement

When the Capability Broker logs recurring requests across multiple independent goals (e.g., 50+ requests for `GraphReasoning`, 30+ requests for `FormalVerification`), it recognizes an **ecosystem capability gap**.

Instead of repeatedly spawning temporary, isolated subagents, the Broker files an **Autonomic Capability Intake**, directing PAEOS to build and test a permanent Substrate Tool or Skill, driving true demand-led evolution.

---

## 5. Next Steps & Research Deliverables

- **S-1**: Formalize `CapabilityRequest` schema and `BlockedReason` enums in `kernel/types.py`.
- **S-2**: Implement `CapabilityBroker` evaluation harness in `runtime/broker.py`.
- **S-3**: Inject role-incentive prompts into `DESIGN`, `PLAN`, `IMPLEMENT`, and `CRITIQUE` system prompts.
