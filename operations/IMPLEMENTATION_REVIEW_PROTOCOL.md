# Post-Task Implementation Review Protocol

This protocol defines the canonical, mandatory self-adversarial review executed at state **L17 (Retrospective + Constitutional Review)** for every engineering task in PAEOS.

---

## 1. Execution Requirement

Every task implementation (B0.x, Sentium, SAKG, Orca-strator, etc.) MUST finish with this review.

* **No exceptions.**
* **Do not defend your own work.**
* **Attempt to prove that the implementation is incorrect.**
* Output MUST be saved to `reviews/tasks/<task_id>_review.md` and committed to git.

---

## 2. The 10-Point Evaluation Checklist

Evaluate the completed implementation across the following 10 dimensions:

1. **Constitutional Compliance**: Does the implementation violate any clause in $Z_0$, CER-1..CER-6, or kernel invariants?
2. **Architectural Drift**: Does the code introduce concepts, parameters, or behaviors not derived from the specification?
3. **Duplication of Mechanisms**: Does this duplicate any existing helper, schema, or kernel abstraction?
4. **Bypassing Mechanisms**: Were any existing validation, typing, or logging mechanisms bypassed?
5. **Simpler Implementation Possible**: Could this task have been accomplished with fewer lines of code, fewer abstractions, or standard library utilities?
6. **Better Derivation**: Is there a cleaner or more direct mathematical/spec derivation for this logic?
7. **Hidden Technical Debt**: Are there unrecorded assumptions, hardcoded values, or deferred edge cases that require a `DEBT-NNNN` entry?
8. **Security Implications**: Are there unvalidated inputs, permission leaks, or blast-radius risks?
9. **Runtime Implications**: Does this introduce blocking calls, unhandled errors, or resource leaks?
10. **Future Extensibility**: Will this implementation lock future waves into an un-derived pattern?

---

## 3. Issue Severity Classification

Every issue discovered during review MUST be classified under one of four severities:

* **BLOCKER**: A violation of constitutional law, broken test, broken invariant, or un-derived architecture. Implementation CANNOT be merged until resolved or converted into a ratified Improvement Proposal.
* **MAJOR**: Architectural drift, performance flaw, or missing test case. Must be resolved before task closure.
* **MINOR**: Non-functional cleanup, formatting, or docstring alignment.
* **OBSERVATION**: Helpful context or suggestion for future design waves.

---

## 4. Resolution Protocol

If the review reveals that **constitutional or architectural changes are necessary**:

1. **DO NOT** modify the implementation directly to add new un-derived architecture.
2. Produce an **Improvement Proposal** (`proposals/PAEOS-IP-NNNN.md`) following CER-2.
3. Halt implementation until Founder ratification (CER-5).

---

## 5. Artifact Format

Save findings in `reviews/tasks/<task_id>_review.md` using the template below:

```markdown
# Constitutional Implementation Review: [<TASK_ID>]

**Date**: <YYYY-MM-DD>
**Task**: <TASK_ID>
**Reviewer Role**: Auditor / Builder Self-Adversarial

## Summary of Findings

- **BLOCKER**: <Count>
- **MAJOR**: <Count>
- **MINOR**: <Count>
- **OBSERVATION**: <Count>

## Evaluation Checklist

### 1. Constitutional Compliance
[Status / Details]

### 2. Architectural Drift
[Status / Details]

### 3. Duplication of Mechanisms
[Status / Details]

### 4. Bypassing Mechanisms
[Status / Details]

### 5. Simpler Implementation Possible
[Status / Details]

### 6. Better Derivation
[Status / Details]

### 7. Hidden Technical Debt
[Status / Details]

### 8. Security Implications
[Status / Details]

### 9. Runtime Implications
[Status / Details]

### 10. Future Extensibility
[Status / Details]

## Action Items & Proposals
- [ ] Item 1
- [ ] Item 2
```
