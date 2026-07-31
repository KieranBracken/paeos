# PAEOS-IP-0008 — Architectural Invariants as a first-class, CI-executed registry

Status: **AWAITING FOUNDER** · Filed: 2026-07-31 · Channel: CER-2
Source finding: founder observation after the CER-1 `EvidenceSource` review — the project is now
routinely *discovering and proving* architectural laws (runtime⊥MCP, single committer, read-only
evidence interface, …), but they live scattered across reviews / proposals / code comments / CI /
CER discussions. They deserve a **canonical, executable home**. This proposal recommends one; it does
not build it (per the founder's sequencing: file the proposal, do not interrupt R5.1 to implement it).

## 1. Observation

Architectural truth in PAEOS is currently *prose*: `reviews/architecture/evidence-source-cer1.md`
proves runtime⊥MCP; IP-0005 states the memory-authority trilogy; B2.G removes the SoftLoop's scar
write; F1/F2/F3 are CI gates; §3.7 says the constitution has no agent write API. These are the same
*kind* of thing — a checkable property the architecture must always satisfy — but they have no shared
form, no shared home, and inconsistent enforcement (some CI-checked, most convention).

## 2. Proposed improvement

A first-class artifact **`architecture/invariants.yaml`** (+ a thin CI executor `ops/ci/invariants.py`)
where each invariant is a record with a **machine-runnable verifier**, so CI *executes architectural
truth* every commit rather than trusting prose:

```yaml
AI-001:
  name: Runtime Transport Independence
  rule: the runtime must not import MCP (transports live behind EvidenceSource)
  basis: [reviews/architecture/evidence-source-cer1.md, IP-0008]
  verify: { kind: grep-absent, pattern: "import mcp|from mcp", paths: [runtime/] }

AI-002:
  name: Single Constitutional Writer
  rule: only the kernel commits institutional memory (L3 scars) at Stage 17
  basis: [IP-0005, IP-0006, B2.G]
  verify: { kind: grep-absent, pattern: "propose_scar", paths: [runtime/orchestrator/] }

AI-003:
  name: Read-only Evidence Interface
  rule: the runtime depends only on EvidenceSource; the interface exposes read (evidence_for), never submit
  basis: [reviews/architecture/evidence-source-cer1.md]
  verify: { kind: pyright }        # the Protocol + strict typing already enforce conformance

AI-004:
  name: Seal requires adversary PASS
  rule: no goal seals over a blocking adversarial dissent (FR-3)
  basis: [IP-0007, B2.K]
  verify: { kind: test, target: tests/runtime/test_soft_loop.py::test_adversary_block_remands_the_seal }

AI-005:
  name: Evidence must be probative
  rule: evidence whose result is identical with and without the change cannot seal (vacuous)
  basis: [B2.O, CANARY-0002]
  verify: { kind: test, target: tests/runtime/test_verification.py::test_vacuous_commands_flags_non_discriminating }

AI-006: { name: Kernel LOC budget,      rule: kernel LOC <= 20000,                 basis: [F1], verify: { kind: loc-budget, paths: [kernel/], max: 20000 } }
AI-007: { name: TCB HARD-LOOP,          rule: kernel/ or constitution/ diffs route to HARD-LOOP, basis: [F2], verify: { kind: script, run: ops/ci/tcb_diff.py } }
AI-008: { name: No committed keys,      rule: signing keys never committed; lockfile present,    basis: [F3], verify: { kind: supply-chain } }
AI-009: { name: Constitution read-only, rule: no agent write API to Z0; ledger.append unexposed,  basis: ["PAEOS-7 §3.7"], verify: { kind: grep-absent, pattern: "def append", paths: [mcp/] } }
```

Verifier `kind`s start small (`grep-absent`, `pyright`, `test`, `loc-budget`, `script`,
`supply-chain`) and grow only as invariants demand. The existing F1/F2/F3 CI steps are **absorbed** as
AI-006/007/008 — one registry, one executor, no special cases.

## 3. Justification

- **Architecture becomes a testable property, not a hope** — the founder's own framing: instead of
  "runtime shouldn't depend on MCP," *prove it every commit*. This is CER-1 (falsify continuously)
  applied to *structure*, not just behaviour.
- **A canonical home** ends the scatter (reviews/proposals/comments/CI). New invariants (the founder
  expects 20–50 more over coming phases) have one place to land, each with a verifier.
- **It is not another constitution.** It is the *executable form* of already-derived architectural
  truth — downstream of the kernel/lifecycle, like a conformance suite for structure.

## 4. Risks / compatibility

- Over-formalisation: keep the schema minimal; an invariant enters only with a runnable verifier
  (mirrors "no scar without a detection signature"). Prose-only "invariants" stay in reviews until
  they earn a verifier.
- Some invariants are not cheaply machine-checkable (e.g. "agents hold no ambient authority"); those
  remain documented with a `verify: {kind: manual}` marker rather than a false green.

## 5. Constitutional impact

- **Operational/execution-architecture**, not a kernel amendment. Adds `architecture/invariants.yaml`
  + `ops/ci/invariants.py` + a CI step; absorbs F1/F2/F3. Needs founder ratification as an operational
  artifact (CER-2/CER-5). No PAEOS-4 change.

## 6. Companion observation — the Constitutional Evolution Loop deserves a name

The founder noted a distinct feedback loop now running:

```
specification → implementation → CER (falsify) → proposal → architecture refinement → implementation
```

This governs **constitutional evolution** and is *not* the 19-stage **goal-execution** lifecycle (which
governs a single goal). They are related but distinct processes — this loop is how PAEOS discovers,
proves, and formalises its own architectural laws (this very proposal is an iteration of it). It
warrants its own named treatment (working name: **the Amendment Loop** / L-track), likely a short
companion spec. Filed here as an observation; recommend a follow-on proposal to name and specify it.

## 7. Recommendation

**Ratify** the registry as an operational artifact and schedule its (small) implementation **after
R5.1** — seed it with AI-001..009 above, absorb F1/F2/F3, and add the standing `grep "import mcp"
runtime/` gate the CER-1 review earned. Separately, **open a follow-on proposal to name and specify
the Constitutional Evolution Loop.** This recommends; it changes nothing until ratified.
