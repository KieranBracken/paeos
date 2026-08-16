# RB-0009 — Bounded Epistemic Sandboxing & Anchoring Prevention

- **Status:** Research Backlog *(Architecture Enhancement)*
- **Priority:** High *(Veto & Adversarial Integrity)*
- **Filed:** 2026-08-08
- **Dependencies:** PAEOS-7.6 §5 (`TaskPackage`), PAEOS-9 §10 (Execution Architecture), RB-0001/0003 (Council Deliberation), SAKG

---

## 1. Executive Summary & Core Philosophy

When an AI worker session critiques its own output or reviews a candidate artifact authored by another session, the primary failure mode is **anchoring bias**. When a reviewer session receives the builder's justificatory prose, reasoning trace, or confidence rating, its evaluation collapses toward confirming the builder's prior conclusion.

Multi-account arrangements ("Account A vs Account B") are an operational workaround for a structural problem. Model identity does not create independence—**epistemic boundary isolation** creates independence.

PAEOS enforces this through a core principle:

> **"A critic inherits facts, constraints, and target artifacts. A critic NEVER inherits interpretations, justifications, or conclusions."**

```text
                         PAEOS Runtime
                               │
                      Target Task Package
                               │
                ┌──────────────┴──────────────┐
                │                             │
          Builder Context               Critic Sandbox
                │                             │
        full working history           fresh session
                │                             │
         - chain of thought            ┌──────┴──────┐
         - proposed justification      │             │
         - intermediate attempts    Target artifact  Relevant
                                                    contracts
                                       + evaluation criteria
                                       + necessary evidence
                                       + executable verifiers
                                       
                                       NO builder reasoning
                                       NO builder conclusion
                                       NO justificatory narrative
                                       
                └──────────────┬──────────────┘
                               ↓
                   Unanchored Adversarial Veto
```

---

## 2. The Four Levels of Epistemic Independence

PAEOS defines four formal levels of epistemic independence for reasoning tasks:

| Level | Independence Tier | Epistemic Boundary | Use Case |
| :--- | :--- | :--- | :--- |
| **Level 0** | **Same-Context Critique** | Same session, full history. Prompted to self-critique. | Cheap, fast pre-flight check. Weakest independence. |
| **Level 1** | **Context-Isolated Subagent** | Ephemeral session, scoped evidence, zero transcript history. | Standard Reviewer / Auditor stage. |
| **Level 2** | **Blind Critique** | Ephemeral session. Receives requirements and candidate $X$, but **does not know $X$ is the proposed answer**. | Adversarial Veto / Security Audit / Safety Gate. |
| **Level 3** | **Competitive Generation** | $N$ independent subagents receive the problem and constraints in parallel. None see other proposals. | High-leverage architecture design (RB-0007 / ADE). |

---

## 3. Contract Specification (`ContextPolicy`)

To enforce epistemic isolation at the Z2 boundary (`runtime/`), `TaskPackage` (PAEOS-7.6 §5) is extended with an explicit `ContextPolicy`:

```python
@dataclass(frozen=True, slots=True)
class ContextPolicy:
    """Rules governing what context artifacts and prior state may enter a session."""

    independence_level: int = 1  # 0: Same, 1: Isolated, 2: Blind, 3: Competitive
    inherit_evidence: bool = True       # Raw test outputs, CAS hashes, environmental facts
    inherit_constraints: bool = True    # Schemas, contracts, constitutional rules
    inherit_reasoning: bool = False     # Chain-of-thought, intermediate attempts, design rationale
    inherit_conclusion: bool = False    # Proposed answers, builder's confidence ratings
    prohibited_patterns: tuple[str, ...] = ("rationale", "justification", "builder_notes")
```

`TaskPackage` incorporates `context_policy: ContextPolicy`:

```python
@dataclass(frozen=True, slots=True)
class TaskPackage:
    ...
    context_policy: ContextPolicy = field(default_factory=ContextPolicy)
```

---

## 4. Runtime Context Sanitization

When `ClaudeCodeRuntime` materializes context artifacts into an ephemeral workspace (`_materialize_context` in `runtime/integrations/__init__.py`), it enforces `context_policy`:

1. **Filtering Context Artifacts**: If `inherit_reasoning` is `False`, context refs matching `prohibited_patterns` (e.g. builder design notes, justifiability prose) are excluded from the `context/` directory.
2. **Prompt Compilation (`build_prompt`)**: Prompts for `Role.REVIEWER` and `Role.ADVERSARY` are generated exclusively from:
   - Objective & Role definition
   - Required evidence obligations (`required_evidence`)
   - Executable acceptance tests
   - Target files under review
   - Constitutional clauses
3. **Blind Formatting (Level 2)**: For Level 2 tasks, the prompt is formatted neutrally:
   *`"Evaluate whether candidate artifact X satisfies requirements Y and contracts Z."`*
   rather than:
   *`"The builder implemented X to satisfy Y. Verify if X is correct."`*

---

## 5. Impact on Veto & Deliberation Architecture

Implementing bounded epistemic sandboxing delivers three major structural improvements to PAEOS:

1. **Elimination of Anchoring Bias**: Adversary and Reviewer stages evaluate code and design strictly against evidence, schemas, and tests, without being influenced by the author's persuasive prose.
2. **Machine-Auditable Provenance**: Every `TaskResult` and `Ledger` event records `independence_level` and `context_policy_hash`, proving to external verifiers that a seal passed an unanchored veto.
3. **Optimal Token Efficiency**: Stripping unnecessary historical working state reduces prompt context size for reviewer sessions, conserving token budget while maximizing reasoning independence.
