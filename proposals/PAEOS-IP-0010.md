# PAEOS-IP-0010 — Architectural Invariants as a first-class, CI-executed registry

Status: **AWAITING FOUNDER** · Filed: 2026-07-31 (re-filed 2026-08-01) · Channel: CER-2
Level: **operational / execution-architecture** (adds an artifact + CI step; no kernel amendment).
Supersedes: none. Renumbering note: originally filed as IP-0008; renumbered to **IP-0010** after the
number was re-used for the ratified *Universal WorkerTransport Architecture* proposal.
Source: the CER-1 EvidenceSource review + the Phase-3 architectural review
(`reviews/phase3_architectural_review.md`), which added AI-010/AI-011.

## 1. Observation

Architectural truth in PAEOS is currently *prose*, scattered across reviews / proposals / code
comments / CI / CER discussions: runtime⊥MCP (`reviews/architecture/evidence-source-cer1.md`), the
memory-authority trilogy (IP-0005), one-committer (B2.G), F1/F2/F3 (CI gates), constitution-has-no-
write-API (§3.7), and now Port Independence + Least-Privilege Interface (Phase-3 review). These are the
same *kind* of thing — a checkable property the architecture must always satisfy — with no shared
form, no shared home, and inconsistent enforcement (some CI-checked, most convention).

## 2. Proposed improvement

A first-class `architecture/invariants.yaml` (+ a thin executor `ops/ci/invariants.py`) where each
invariant carries a **machine-runnable verifier**, so CI *executes* architectural truth every commit:

```yaml
AI-001: { name: Runtime Transport Independence, rule: the CORE runtime imports no vendor SDK,
          basis: [reviews/architecture/evidence-source-cer1.md, R5.3],
          verify: { kind: grep-absent, pattern: "import mcp|from mcp", paths: [runtime/], exclude: [runtime/transports/] } }
AI-002: { name: Single Constitutional Writer, rule: only the kernel commits L3 memory at Stage 17,
          basis: [IP-0005, IP-0006, B2.G], verify: { kind: grep-absent, pattern: "propose_scar", paths: [runtime/orchestrator/] } }
AI-003: { name: Read-only Evidence Interface, rule: the runtime depends on EvidenceSource (read), never a write facet,
          basis: [reviews/architecture/evidence-source-cer1.md], verify: { kind: pyright } }
AI-004: { name: Seal requires adversary PASS, basis: [IP-0007, B2.K],
          verify: { kind: test, target: tests/runtime/test_soft_loop.py::test_adversary_block_remands_the_seal } }
AI-005: { name: Evidence must be probative, basis: [B2.O, CANARY-0002],
          verify: { kind: test, target: tests/runtime/test_verification.py::test_vacuous_commands_flags_non_discriminating } }
AI-006: { name: Kernel LOC budget, rule: kernel LOC <= 20000, basis: [F1], verify: { kind: loc-budget, paths: [kernel/], max: 20000 } }
AI-007: { name: TCB HARD-LOOP, basis: [F2], verify: { kind: script, run: ops/ci/tcb_diff.py } }
AI-008: { name: No committed keys, basis: [F3], verify: { kind: supply-chain } }
AI-009: { name: Constitution read-only, rule: no agent write API to Z0; ledger.append unexposed,
          basis: ["PAEOS-7 §3.7"], verify: { kind: grep-absent, pattern: "def append", paths: [runtime/transports/mcp/servers.py] } }
# added by the Phase-3 architectural review:
AI-010: { name: Port Independence, rule: the core depends only on ports (Protocols); adapters/vendors are leaves under runtime/transports/,
          basis: [phase3_architectural_review.md, R5.1-R5.3],
          verify: { kind: grep-absent, pattern: "from runtime.transports|import subprocess", paths: [runtime/orchestrator/, runtime/transport.py] } }
AI-011: { name: Least-Privilege Interface, rule: the core depends on the minimal read-only facet of a port (EvidenceSource, not WorkerTransport),
          basis: [phase3_architectural_review.md], verify: { kind: pyright } }
```

Verifier `kind`s start small (`grep-absent`, `pyright`, `test`, `loc-budget`, `script`,
`supply-chain`) and grow only as invariants demand; F1/F2/F3 are **absorbed** as AI-006/007/008.

## 3. Justification / first-principles derivation

Architecture becomes a *testable property*, not a hope — CER-1 (falsify continuously) applied to
*structure*. AI-010/AI-011 are the Phase-3 compression finding: the core is a **policy kernel over
ports**, depending only on the minimal facet of each. A canonical, executable home ends the scatter;
the founder expects 20–50 more invariants over coming phases.

## 4. Falsification attempts

- *"Over-formalisation."* Guarded by "no invariant without a runnable verifier" (mirrors "no scar
  without a detection signature"); prose-only ones stay in reviews with `verify: {kind: manual}`.
- *"AI-010 is just AI-001."* No — AI-001 bans a *specific* vendor (MCP); AI-010 is the *general* law
  (no adapter/vendor import in the core, any transport). AI-001 becomes an instance of AI-010.
- *"It becomes a second constitution."* No — it is the *executable form* of already-derived truth,
  downstream of the kernel, like a conformance suite for structure.

## 5. Architectural impact / dependencies

Adds `architecture/invariants.yaml` + `ops/ci/invariants.py` + one CI step; absorbs F1/F2/F3. Depends
on the AI-001..011 findings (all already implemented). **Operational**, not a kernel amendment.

## 6. Recommendation

**Ratify** the registry as an operational artifact; seed it with AI-001..011 (AI-001 becomes an
instance of AI-010), absorb F1/F2/F3, and add the `runtime/transports/` exclusion R5.3 earned.
Implement after the current transport work. This recommends; it changes nothing until ratified.
