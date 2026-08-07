# CONSTITUTIONAL REFLECTION PRINCIPLE

**Status**: RATIFIED CONSTITUTIONAL METHODOLOGY RULE  
**Scope**: Cross-Cutting Governance Rule (Stages 15–18 Evolution Phase)  

---

## 1. Core Principle: Mandatory Constitutional Reflection

Implementation is an empirical experiment. No amount of prior architectural reasoning outweighs empirical evidence gathered during implementation (**Reality Has Legislative Priority**).

Every completed implementation cycle SHALL conclude with a mandatory **Constitutional Review**. The review is a formal falsification attempt: it tests current constitutional, architectural, and runtime assumptions against empirical reality.

> **Rule of Reflection**:
> *The Constitutional Review is mandatory. The resulting Improvement Proposal is optional (produced only when reality warrants a change).*

---

## 2. The 3 Mandatory Outputs of Implementation

Every completed implementation cycle produces up to three distinct structural outputs:

```
                  ┌─────────────────────────────────────────┐
                  │          IMPLEMENTATION CYCLE           │
                  └─────────────────────────────────────────┘
                                       │
            ┌──────────────────────────┼──────────────────────────┐
            ▼                          ▼                          ▼
 ┌────────────────────┐     ┌────────────────────┐     ┌────────────────────┐
 │  1. RETROSPECTIVE  │     │   2. DEBT ENTRY    │     │ 3. PROPOSAL (IP)   │
 │   What worked?     │     │   What failed?     │     │ What did reality   │
 │ (Execution metrics │     │(Tracked technical  │     │ teach constitution?│
 │  & verification)   │     │   compromises)     │     │(Warranted IP-series│
 └────────────────────┘     └────────────────────┘     └────────────────────┘
```

1. **Retrospective (`reviews/` / Ledger)**: Records operational execution facts, test verification metrics, and performance bounds.
2. **Technical Debt Entry (`ledger/debt/`)**: Records temporary, non-constitutional compromises made during execution that require future repayment (`DEBT-` series).
3. **Improvement Proposal (`proposals/`)**: Records warranted constitutional or architectural enhancements surfaced when implementation exposes specification gaps (`IP-` series).

---

## 3. Reality Has Legislative Priority

If repeated implementation cycles independently surface the exact same specification friction or architectural limitation:

1. **Evidence Thresholding**: Repeated findings across multiple runs automatically elevate the priority of the corresponding Improvement Proposal.
2. **Falsification Dominance**: Spec docs and architectural docs MUST yield to empirical evidence. The constitution does not treat itself as beyond question—it continually tests itself against implementation reality while preserving the separation between **discovering** an improvement and **adopting** it via Founder ratification.

---

## 4. Operationalization in Lifecycle Stages 15–18

Inside the Evolution Phase:
- **Stage 15 (RETROSPECT)**: Gathers empirical execution facts and log evidence.
- **Stage 15A (CONSTITUTIONAL REFLECTION)**: Conducts the mandatory falsification review against current spec assumptions.
- **Stage 16 (EVOLVE)**: Authors warranted Improvement Proposals (`proposals/PAEOS-IP-XXXX.md`).
- **Stage 17 (MEMORY_UPDATE)**: Synthesizes canonical scars and lessons into institutional memory.
- **Stage 18 (IMPROVE_RUNTIME)**: Submits ratified proposals to the Founder for constitutional amendment.
