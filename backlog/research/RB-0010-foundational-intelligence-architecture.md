# RB-0010 — Post-RCL / Foundational Intelligence Architecture

- **Status:** Research Backlog *(Architecture Addendum — Not Authorized for Implementation)*
- **Priority:** Foundational (Phase 4 / Post-RCL Roadmap Target)
- **Filed:** 2026-08-10
- **Origin:** Research synthesis on post-RCL orchestration, computational reasoning economics, hierarchical mission trees, and multi-branch intelligence architectures.
- **Dependencies:** RB-0001/0003 (Deliberation Councils), RB-0004 (KAE), RB-0007 (ADE), RB-0008 (Autonomous Technical Leadership), RB-0009 (Epistemic Sandboxing), SAKG

---

## Executive Summary & Core Purpose

This research backlog preserves architectural ideas, structural upgrades, and investigations that emerged during the PAEOS Reasoning Continuity Layer (RCL) work. It defines the broader **Foundational Intelligence Architecture** sitting above continuity, specifying how PAEOS orchestrates multi-agent deliberation, allocates reasoning budgets, searches solution spaces, and enforces non-anchored vetoes across the 19-layer lifecycle.

```text
                                 PAEOS
                                   │
          ┌────────────────────────┼────────────────────────┐
          │                        │                        │
     CONSTITUTION              REASONING               CONTINUITY
          │                        │                        │
       L01-L19             Council / Search                RCL
          │                Economy / Routing                │
          │                        │                        │
          └────────────────────────┼────────────────────────┘
                                   │
                             ORCHESTRATION
                                   │
                          Mission / Sub-Goals
                          Branches / Workers
                                   │
                            MODEL WORKERS
                     Claude / Gemini / GPT / etc.
```

---

# Part I: P0 Foundational Research Items

---

## R-01 — Canonical 19-Layer Runtime Completion

### Question
How should the existing Phase-1 `SoftLoop` substrate evolve into the actual canonical 19-layer PAEOS runtime?

The 19-layer lifecycle is already documented as the constitutional target, while SoftLoop was intentionally implemented as a Phase-1 vertical slice. The previous audits therefore did not establish full 19-layer conformance.

### Investigate
* Exact intended runtime topology for L01–L19.
* How each layer should map onto existing kernel primitives.
* Which layers should be sequential, branch, or loop.
* Which layers should spawn sub-goals.
* How failures/remands move backwards through the topology.
* How L17 Retrospective, L18 Knowledge Extraction, and L19 Constitutional Evolution become actual runtime operations.
* Whether `SoftLoop` should evolve incrementally or whether a successor orchestration abstraction is intended.
* How the canonical CLI remains the authoritative entrypoint.

### Deliverable
`PAEOS_CANONICAL_RUNTIME_IMPLEMENTATION_RESEARCH.md`

### Priority
**P0 — Foundational**

---

## R-02 — Hierarchical Mission / Sub-Goal Architecture

### Question
How should PAEOS represent recursive reasoning missions in which a parent objective delegates independently governed sub-problems to multiple workers?

This emerged as the strongest candidate for the RCL's orchestration foundation: a hierarchical mission tree naturally maps onto existing `GoalId`, `TaskPackage`, Ledger, and ContextCompiler primitives.

### Investigate
* Parent Goal $\rightarrow$ Child Goal relationships and child lifecycle.
* Parent/child authority and child result promotion back to parent.
* Nested budgets, capabilities, cancellations, and remands.
* Parallel vs. sequential children; recursive depth limits.
* Context inheritance (`FRESH`, `BLIND`, continuation policies).
* Topology validation (Tree vs. DAG vs. Tree-of-DAGs).

### Deliverable
`PAEOS_HIERARCHICAL_MISSION_RESEARCH.md`

### Priority
**P0**

---

## R-03 — PAEOS-Native Multi-Branch Reasoning

### Question
What is the canonical PAEOS mechanism for:

```text
Problem
   ↓
Branch A ─┐
Branch B ─┼→ Critique → Synthesis → Verification
Branch C ─┘
```

without bypassing the constitutional lifecycle?

### Investigate
* Native branch creation and identity.
* Independent context construction and branch-specific capability tokens.
* Branch-specific write scopes, completion, aggregation, and synthesis.
* Branch disagreement, cancellation, and budget allocation.
* Branch-level Court verification.
* Mapping onto L09 Critique / L10 Adversarial Review and other lifecycle layers.

### Deliverable
`PAEOS_MULTI_BRANCH_REASONING_RESEARCH.md`

### Priority
**P0**

---

## R-04 — Epistemic State / Provenance Graph

### Question
How should PAEOS represent the semantic relationships between reasoning objects?

Beyond basic object types (Decision, Hypothesis, Rejection, Evidence, Constraint), the deeper architectural question is the **reasoning graph connecting them**.

```text
Evidence E1 ──(supports)──> Hypothesis H1 ──(motivates)──> Proposal P1 ──(produces)──> Decision D1
```

### Investigate
* Canonical node and edge ontologies.
* Provenance semantics and invalidation propagation.
* Supersession, contradiction, and dependency contamination.
* Branch reconciliation and evidence lineage.
* Human authority versus model-generated state.
* Integration into `ReasoningState`, Ledger projections, or SAKG.

### Deliverable
`PAEOS_REASONING_PROVENANCE_GRAPH_RESEARCH.md`

### Priority
**P0**

---

## R-05 — Context Policy / Epistemic Isolation Architecture

### Question
How should PAEOS systematically decide **what a worker is allowed to know** for every reasoning situation?

Modes required: `CONTINUATION`, `FRESH`, `BLIND`, `ADVERSARIAL`, `SPECIALIST`, `EVIDENCE_ONLY`, `SYNTHESIS`, `AUDITOR`.

### Investigate
* Policy inheritance, composition, and precedence.
* Context leakage detection and proof of blind context.
* Cryptographic/sealed context manifests.
* Context-policy auditing and policy-aware Council members.
* Policy-aware sub-goals, SAKG retrieval, and tool access.

### Deliverable
`PAEOS_CONTEXT_POLICY_RESEARCH.md`

### Priority
**P0**

---

## R-06 — Reasoning Economy / Computational Economics

### Question
How should PAEOS decide **how much reasoning to spend** on a problem?

The objective is to allocate reasoning resources where additional reasoning has the highest expected value:

```text
Problem ──> Estimate difficulty/stakes ──> Determine reasoning budget ──> Execute ──> Measure marginal info gained
```

### Investigate
* Expected Value of Information (EVI) and marginal reasoning value.
* Token, latency, and model economics.
* Probability of error vs. cost of an incorrect decision.
* Cost of additional verification vs. diminishing returns from additional agents.
* When cheap specialists should be used before expensive reasoning.
* Early termination vs. escalation rules.

### Deliverable
`PAEOS_REASONING_ECONOMY_RESEARCH.md`

### Priority
**P0 — Foundational**

---

## R-07 — Optimal Solution Discovery Architecture

*(Distinct from R-06 Reasoning Economy: R-06 addresses resource allocation; R-07 addresses solution-space search).*

### Question
How can PAEOS search for the **best available solution**, rather than merely asking one agent to propose a solution and another to critique it?

```text
Problem ──> Search Space ──> Candidate Proposals ──> Comparative Court ──> Adversarial Attack ──> Trade-off Eval ──> Optimal Candidate
```

### Investigate
* Search vs. debate topologies.
* Candidate-space exploration and Pareto-front solutions.
* Multi-objective optimization and constraint satisfaction.
* Iterative refinement and adversarial candidate elimination.
* Stopping conditions for optimal discovery.

### Deliverable
`PAEOS_OPTIMAL_SOLUTION_DISCOVERY_RESEARCH.md`

### Priority
**P0**

---

## R-08 — Council Architecture 2.0

### Question
What should a **PAEOS Council** actually be?

### Investigate
* Council formation, member selection, and capability-based assignment.
* Specialist vs. generalist, fresh, blind, and adversarial members.
* Voting models: weighted voting, confidence scoring, evidence-weighted decisions, quorum, veto, deadlock resolution.
* Dynamic council construction vs. fixed groups.
* Empirical testing: *Is N equally capable agents better than a heterogeneous council of specialized reasoning roles?*

### Deliverable
`PAEOS_COUNCIL_ARCHITECTURE_RESEARCH.md`

### Priority
**P0**

---

## R-09 — Veto / Constitutional Authority Architecture

### Question
How should PAEOS distinguish proposals, opinions, recommendations, decisions, approvals, vetoes, constitutional prohibitions, and human overrides?

### Investigate
* Veto hierarchy (Safety, Evidence, Constitutional, Founder, Council, Court, Runtime).
* Absolute vs. conditional vetoes.
* Conflict resolution between veto authorities.
* Expiration, appeal, emergency halts, and veto provenance.

### Deliverable
`PAEOS_AUTHORITY_AND_VETO_RESEARCH.md`

### Priority
**P0**

---

## R-10 — Model Capability Routing

### Question
Should PAEOS choose a model based on *"Which model is best?"* or *"What capability does this task require?"*

### Investigate
* Capability taxonomy: coding, mathematics, research, synthesis, critique, planning, adversarial reasoning, long-context reconstruction, fast classification, multimodal analysis, constitutional reasoning.
* Model capability profiles, benchmark evidence, and historical performance.
* Task-specific fitness, cost, latency, reliability, quota state, and failure history.
* Dynamic routing, fallback routing, and escalation.

### Deliverable
`PAEOS_CAPABILITY_ROUTING_RESEARCH.md`

### Priority
**P0**

---

## R-16 — Constitutional Evolution Mechanism

### Question
How can PAEOS improve **PAEOS itself** without allowing models to silently rewrite its constitution (Stage 19 / L19)?

### Investigate
* Constitutional proposals and amendment lifecycles.
* Founder authority and CER-5 ratification rules.
* Versioning, rollback, compatibility, and migration.
* Constitutional diffing and regression test suites.

### Deliverable
`PAEOS_CONSTITUTIONAL_EVOLUTION_RESEARCH.md`

### Priority
**P0**

---

## R-17 — PAEOS Self-Dogfooding Architecture

### Question
Can PAEOS eventually perform the research, critique, design, and implementation of PAEOS itself **through its own canonical lifecycle**, rather than an external harness acting as a substitute?

### Investigate
* Complete self-hosting loop: receive upgrade objective $\rightarrow$ research $\rightarrow$ competing designs $\rightarrow$ adversarial critique $\rightarrow$ council synthesis $\rightarrow$ implementation $\rightarrow$ court verification $\rightarrow$ scar extraction $\rightarrow$ constitutional evolution.

### Deliverable
`PAEOS_SELF_DOGFOODING_RESEARCH.md`

### Priority
**P0**

---

# Part II: P1 Intermediate Research Items

---

## R-11 — Provider / Account / Quota Failover

### Question
Can a PAEOS mission continue seamlessly across provider rate limits, account blackouts, API failures, or model deprecations?

```text
Provider A ──(quota exhausted)──> PAEOS Checkpoint ──> Provider B ──> Canonical State Preserved
```

### Investigate
* Provider failover economics: *Is switching providers optimal, or is waiting for quota reset on the primary provider worth the latency trade-off?*
* Cross-provider checkpoint compatibility.

### Deliverable
`PAEOS_PROVIDER_QUOTA_FAILOVER_RESEARCH.md`

### Priority
**P1**

---

## R-12 — Continuity Quality / Fidelity Benchmarking

### Investigate
* Benchmark harness to measure: reconstruction accuracy, decision preservation, constraint preservation, negative-knowledge preservation, uncertainty preservation, execution continuity, provider portability, contradiction rates, and context leakage.

### Deliverable
`PAEOS_CONTINUITY_FIDELITY_BENCHMARK_RESEARCH.md`

### Priority
**P1**

---

## R-13 — Context Compression / Context Economics

### Question
How aggressively can PAEOS compress historical reasoning **without degrading reasoning quality**?

### Investigate
* Semantic compression, provenance-preserving summaries, decision compression, transcript archival, hierarchical summaries, retrieval-on-demand, and "expand if uncertain" triggers.

### Deliverable
`PAEOS_CONTEXT_COMPRESSION_RESEARCH.md`

### Priority
**P1**

---

## R-14 — Reasoning Termination / "Enough Reasoning" Criterion

### Question
How does PAEOS know when it has completed **enough** reasoning?

### Investigate
* Stopping rules: confidence saturation, marginal information gain, disagreement saturation, repeated conclusion detection, unresolved high-impact uncertainty, and mandatory escalation triggers.

### Deliverable
`PAEOS_REASONING_TERMINATION_RESEARCH.md`

### Priority
**P1**

---

## R-15 — Learning From Reasoning Outcomes

### Question
How does PAEOS turn successful and failed reasoning into **future reasoning improvements** (L17–L18)?

### Investigate
* Retrospective analysis, lesson extraction, failure pattern detection, scar generation, lesson validation, and false lesson prevention.

### Deliverable
`PAEOS_REASONING_LEARNING_RESEARCH.md`

### Priority
**P1**

---

## R-18 — External Host vs. PAEOS Boundary

### Question
What exactly should **Antigravity / Claude Code / Gemini / Codex / terminal environments** be responsible for versus PAEOS?

### Investigate
* Host vs. PAEOS vs. Model vs. Filesystem vs. Tool authority boundaries.
* Emergency host intervention protocols and bypass detection.

### Deliverable
`PAEOS_HOST_BOUNDARY_RESEARCH.md`

### Priority
**P1**

---

## R-19 — PAEOS Mission Scheduler / Autonomous Continuation

### Question
Once continuity and branching exist, how should PAEOS continue missions **without a human sitting at the terminal**?

### Investigate
* Checkpoint polling, pending-task queues, automatic resumption, quota-aware scheduling, sleep/wake cycles, failure escalation, and autonomous branch execution.

### Deliverable
`PAEOS_AUTONOMOUS_MISSION_CONTINUATION_RESEARCH.md`

### Priority
**P1**

---

## R-20 — Reasoning Portfolio / Resource Allocation

### Question
What portfolio of reasoning resources should be deployed for a given task?

```text
£1.00 Reasoning Budget:
  ├── 60% Primary Reasoning
  ├── 15% Independent Critic
  ├── 10% Adversarial Critic
  ├── 10% Research
  └──  5% Verification
```

### Investigate
* Dynamic portfolio allocation, multi-model ensembles, diversity vs. redundancy, and opportunity cost optimization.

### Deliverable
`PAEOS_REASONING_RESOURCE_ALLOCATION_RESEARCH.md`

### Priority
**P1**

---

## R-21 — Optimal Council Composition

### Question
For a given problem, **what combination of minds produces the best decision?**

### Investigate
* Dynamic council sizing based on task complexity.
* Model diversity, role diversity, provider diversity, and independent vs. correlated reasoning.

### Deliverable
`PAEOS_OPTIMAL_COUNCIL_COMPOSITION_RESEARCH.md`

### Priority
**P1**

---

## R-22 — Decision Confidence Is Not Model Confidence

### Question
How should PAEOS distinguish Model Confidence, Evidence Confidence, Decision Confidence, and Constitutional Confidence?

### Investigate
* Confidence provenance, evidence-weighted confidence, independence-adjusted confidence, and confidence decay when underlying evidence changes.

### Deliverable
`PAEOS_CONFIDENCE_AND_INDEPENDENCE_RESEARCH.md`

### Priority
**P1**

---

## R-23 — Reasoning Diversity / Anti-Groupthink Architecture

### Question
How does PAEOS deliberately generate **different reasoning**, rather than multiple copies of the same reasoning?

### Investigate
* Epistemic diversity via varied prompts, models, providers, context policies, assumptions, and controlled disagreement.

### Deliverable
`PAEOS_REASONING_DIVERSITY_RESEARCH.md`

### Priority
**P1**

---

# Part III: P2 Meta-Intelligence Research Items

---

## R-24 — Research Backlog Intelligence

### Question
Can PAEOS autonomously determine *"What should we research next?"* based on unresolved uncertainty, architectural dependencies, expected information gain, and project objectives?

```text
Known Architecture ──> Gaps ──> Unknowns ──> Dependency Graph ──> EVI ──> Research Priority ──> Next Mission
```

### Deliverable
`PAEOS_RESEARCH_PRIORITIZATION_RESEARCH.md`

### Priority
**P2 — Long-Term Meta-Intelligence**
