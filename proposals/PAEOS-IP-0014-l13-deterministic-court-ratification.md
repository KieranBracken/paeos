# PAEOS-IP-0014 — Ratify the Deterministic Verification Court as Canonical L13 Implementation

Status: **AWAITING FOUNDER RATIFICATION** · Filed: 2026-08-19 · Channel: CER-2 (candidate amendment for L19)
Level: **operational / lifecycle-doctrine clarification** (recommends blessing the existing deterministic Court as the canonical L13 verification mechanism; adds no state)

Source: Source-hierarchy reconciliation (Engineering Lifecycle v1.3 is the canonical L01–L19 baseline) + Two-Axis Conformance Map v1 reclassification. See `PAEOS_HALLUCINATION_CHECKER_NOTEBOOK.md` Entry 146.

## 1. Observation

The canonical Engineering Lifecycle (operations/ENGINEERING_LIFECYCLE.md, v1.3) specifies **L13 — Verification** as:
> "Auditor/Runtime (mechanical) + Adversary"; "acceptance criteria satisfied by **live, signed, independent** evidence (A-09)"; "**mechanical evidence is self-approving via EXEC signature**" (EL L163–170).

The runtime implements this with a **deterministic Court** (`runtime/verification.py`, orchestrator §court) that re-executes commands itself, binds evidence to `(artifact_hash, env_hash)`, applies a vacuity gate, and renders a verdict the kernel re-runs (spec/PAEOS-9 §3.8 L-H "the Court").

A prior document treated the L13 prose-vs-YAML divergence (YAML `WORKFLOW_STATE_MACHINE.yaml` L13 lists role `builder`, `recommended_model: sonnet`) as an open CANONICAL CONFLICT (C-01a) pending founder adjudication.

## 2. Current behaviour

- L13 is implemented by the deterministic Court.
- The WSM YAML (a derived machine-executable form of the EL) lists a builder-run/sonnet verification, diverging from the EL prose.
- Because the WSM is a *derived form* and the EL prose already mandates mechanical, self-approving verification (A-09), the Court is a faithful implementation of the **EL prose**, not a conflict with it.

## 3. Proposed improvement

1. **Resolve C-01a mechanically**: Engineering Lifecycle prose wins over the derived WSM YAML (no founder adjudication needed — the EL already defines L13 as mechanical/self-approving).
2. **Ratify via L19**: formally bless the deterministic Court as the **canonical L13 verification implementation** (it is stricter than the prose, and matches A-09's "independent" evidence requirement). This makes L13 conformance unambiguous for future audits.
3. No new state, no ordering change, no kernel-invariant change (CER v1.1 "governs every state; add no state").

## 4. Justification

- Resolves a documented `CANONICAL_CONFLICT` in the conformance record without legislative invention.
- Determines L13 conformance (currently flagged CONFORMANT but "not resolved here" pending C-01a).
- Reinforces CER-1 (verification/determinism) and the EL's A-09/self-approving-except-independent evidence requirement.

## 5. Risks

- Formalizing "the Court" as canonical could be read as hardening a specific implementation; mitigated by wording it as the *deterministic re-execution mechanism* (the Court), which the EL prose already requires, not a vendor or algorithm beyond the prose.
- If a future ratified amendment changes L13's authority semantics, this ratification would be superseded by that amendment.

## 6. Backwards compatibility

- No change to runtime behavior: the Court is already implemented and tested (`tests/runtime/test_arch_verifier.py`, `test_ast_and_vacuous_verification.py`, `test_cas_properties.py`).
- Only changes the *documented authority* of an existing mechanism.

## 7. Constitutional impact

- Amends the interpreted meaning of Engineering Lifecycle L13 (and the derived WSM L13) via an L19-style ratification; does not rewrite either founding file.
- Removes C-01a from the "founder adjudication" queue by showing it is mechanically resolved by the EL hierarchy.

## 8. Recommendation

**Ratify** the deterministic Court as canonical L13, and record C-01a as resolved-by-hierarchy (Engineering Lifecycle wins over the derived WSM). If you prefer not to ratify, the implementation is unchanged and the EL prose remains authoritative by default; only C-01a would then remain labeled "unratified candidate."

## 9. Status

Drafted as a non-canonical amendment candidate (2026-08-19). Not applied; awaiting founder ratification.
