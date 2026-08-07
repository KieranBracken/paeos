# Constitutional Implementation Review: [IP-0010 — Architectural Invariants Registry]

**Date**: 2026-08-01
**Task**: Implement the ratified IP-0010 — architectural laws as a CI-executed registry (Phase 3).
**Reviewer Role**: Auditor / Builder Self-Adversarial

## Summary of Findings

- **BLOCKER**: 0 · **MAJOR**: 0 · **MINOR**: 0 · **OBSERVATION**: 1

Deliverables:
- `architecture/invariants.json` — the registry (**AI-001..AI-011**, each with a runnable verifier).
  JSON, not YAML, to keep the executor **dependency-free** (PyYAML is not installed; adding it for a
  CI gate would violate F3 minimality — CER-6). The `_note` records the choice.
- `ops/ci/invariants.py` — the executor: runs `grep-absent`, `loc-budget`, `test`; **delegates**
  `pyright` / `script` (F2) / `supply-chain` (F3) to the CI steps that already run them. Exit 1 on any
  FAIL.
- `tests/test_invariants.py` — the registry declares AI-001..011; the executor passes on the tree.
- `.github/workflows/ci.yml` — a new step runs the executor every commit.

Evidence: **332 passed** (+2); ruff clean (clean-cache); pyright 0 errors (strict on `kernel/`);
F1 **2644/20000** (unchanged — F2-SOFT, kernel untouched). Executor on the current tree: **all
AI-001..011 PASS or DELEGATED**.

## What this delivers

Architectural truth stops being prose and becomes an **executed property**. The month's discoveries
are now CI-enforced: **AI-001** runtime⊥MCP, **AI-002** single committer (no `propose_scar` in the
loop), **AI-004** adversary-PASS seal, **AI-005** probative evidence, **AI-006** kernel LOC budget,
**AI-009** constitution read-only, and — the R5 payoff locked in — **AI-010 Port Independence** (the
core imports no adapter/vendor) + **AI-011 Least-Privilege Interface**. This is CER-1 (falsify
continuously) applied to *structure*: no invariant can silently regress under the Phase-3 features to
come.

## Evaluation Checklist

### 1. Constitutional Compliance
**PASS.** The registry is the *executable form* of already-derived law (each invariant cites its basis
— IP-0005/0007, B2.G/K/O, F1, PAEOS-7 §3.7, the CER-1 review). It is downstream conformance, like the
adapter suite C1–C8; it changes no kernel invariant.

### 2. Architectural Drift
**PASS.** A data file + a small executor + one CI step. No new authority. The executor is dependency-
free (stdlib `json`/`re`/`subprocess`).

### 3–7. Duplication / Simplicity / Derivation / Debt
**PASS.** No invariant without a runnable verifier (mirrors "no scar without a detection signature").
F1 is *executed* as AI-006; F2/F3 are *delegated* (referenced, not re-run) to avoid duplicating the
merge-base/supply-chain logic — a deliberate, documented v1 boundary.

### 8. Security Implications
**PASS.** This *is* a security control: it makes the T-series structural defenses (vendor isolation,
single committer, adversary gate) into checks that fail the build, not conventions that can erode.

### 9–10. Runtime / Extensibility
**PASS.** New invariants are one JSON entry + (if a new kind) one verifier function. The founder
expects 20–50 more; the registry is their home.

## Adversary / property pass

1. **Executes real checks** — grep-absent (AI-001/002/009/010), loc-budget (AI-006), test
   (AI-004/005) run and PASS on the tree (executor output + meta-test).
2. **Fails closed** — an unknown verifier kind ⇒ FAIL; any grep hit ⇒ FAIL ⇒ exit 1.
3. **AI-010 locks the R5 payoff** — `grep "import mcp" runtime/` excluding `transports/` is now a
   build gate.

## OBSERVATION

1. **F2/F3 are delegated, not yet absorbed.** IP-0010 called to *absorb* F1/F2/F3; v1 absorbs **F1**
   (AI-006, executed) but leaves **F2** (merge-base `tcb_diff`) and **F3** (supply-chain) as their
   existing CI steps, referenced by AI-007/008 as *delegated*. Full absorption (moving the merge-base
   diff + supply-chain logic into the executor) is a clean, low-risk follow-on — the registry already
   names them, so it is wiring, not design.

## Action Items
- [ ] **Founder**: ratify the IP-0010 *implementation* (F2-SOFT) → merge ff-only, remote CI green
      (the new invariants step included), tag `ip-0010`.
- [ ] **Follow-on**: absorb F2/F3 into the executor (AI-007/008 from delegated → executed).
- [ ] **Follow-on** (Phase-3 review improvements): rename `WorkerTransport` (evidence-typed) + relocate
      core ports (`CourtBackend`/`ScarBackend`/`EvidenceSource`) into `runtime/ports.py` — both make
      AI-010/011 cleaner to verify.
