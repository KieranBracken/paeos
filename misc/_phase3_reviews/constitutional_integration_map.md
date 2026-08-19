# Constitutional Integration Map — IP-0009 & IP-0010

**Date**: 2026-08-01 · **Mode**: integration review — **no document edits, no code** · **Author
role**: Auditor (recommends; does not legislate — CER-5).

Purpose: now that IP-0009 (Constitutional Evolution Loop) and IP-0010 (Architectural Invariants
registry) are ratified, determine **where each will eventually land** in the corpus — not to edit
anything, but to place them deliberately (governance is now outrunning implementation, by design).

---

## IP-0009 — Name the Constitutional Evolution Loop

| Question | Answer |
|---|---|
| **Kind** | **Governance** (a *process*, not a mechanism or an invariant). |
| **Law verb** | **Names** an already-existing pattern. It changes no law and clarifies none — it gives a canonical name + phases to the loop that FR-2 + §7.4 + CER-1..6 already produce. |
| **Sequencing impact** | **None on code.** Descriptive. It improves *how future proposals are processed and reviewed* (helps decide what to place vs. implement), but blocks nothing. |

**Where it lands (in eventual priority order):**

1. **NEW `methodology/CONSTITUTIONAL-EVOLUTION-LOOP.md`** — the primary home: a one-page companion
   spec (phases a–f: Implement → Falsify → Surface → Ratify → Refine → Re-enter), mirroring the
   existing `methodology/PAEOS-CONSTITUTIONAL-ENGINEERING-LIFECYCLE.md` (the 12-stage lifecycle). This
   is where the *second lifecycle* is defined.
2. **`operations/ENGINEERING_LIFECYCLE.md`** — cross-link: it currently defines the 19-state
   **goal-execution** lifecycle + CER-1..6. Add a short section distinguishing the **two lifecycles**
   (goal execution vs constitutional evolution) and pointing to (1). The CER rules are the Evolution
   Loop's *engine*, so they belong beside it.
3. **`methodology/PAEOS-CONSTITUTIONAL-ENGINEERING-LIFECYCLE.md`** — a one-line note that its
   "falsify the constitution" cross-cutting principle *is* the Evolution Loop, named.
4. **PAEOS-7 §7.4** (amendment path) + **§7 (self-improvement)** — a pointer that the §7.4 hard-loop is
   the *Ratify* phase of the Evolution Loop; the loop is the cross-goal control system §7.4 sits inside.

**Not touched:** PAEOS-4 (kernel), PAEOS-0/1 (frozen foundations) — IP-0009 introduces no invariant.

> **Forward pointer (your "constitutional compiler")**: IP-0009's loop, viewed as a *pipeline*
> (observations → proposals[IR] → ratified law), **is** a constitutional compiler — implementation is
> its front-end (observations), CER-1 its type-checker (falsification), proposals its IR, ratification
> its code-gen (law). A future IP could specify that compiler (how an observation *becomes* an
> amendment: the grammar, the passes, the failure modes). **Not filed today** (per your direction);
> noted here as the natural successor once the Evolution Loop is documented.

---

## IP-0010 — Architectural Invariants as a CI-executed registry

| Question | Answer |
|---|---|
| **Kind** | **CI** (primary) + **architectural** (the invariants themselves). It is the *executable form* of architecture. |
| **Law verb** | **Clarifies + makes executable** already-derived law for AI-001..009 (each traces to an existing FR/proposal/gate). AI-010 (Port Independence) + AI-011 (Least-Privilege Interface) **formalise** the narrow-waist principle PAEOS-7 §2 already states — a formalisation, not new law. |
| **Sequencing impact** | **Yes.** Building it is an implementation task (`architecture/invariants.yaml` + `ops/ci/invariants.py` + a CI step). It is the natural *stabiliser* — it regression-proofs everything Phase 3 built. |

**Where it lands:**

1. **NEW `architecture/invariants.yaml`** — the registry (AI-001..011, each with a runnable verifier).
2. **NEW `ops/ci/invariants.py`** — the executor (dispatches `grep-absent` / `pyright` / `test` /
   `loc-budget` / `script` / `supply-chain`).
3. **`.github/workflows/ci.yml`** — one new step runs the executor; **F1/F2/F3 steps are absorbed** as
   AI-006/007/008 (and their existing scripts, e.g. `ops/ci/tcb_diff.py`, become verifiers the registry
   invokes) — one registry, one gate, no special cases.
4. **PAEOS-8 §8** (the F1/F2/F3 gate table) — a note that the gates are now entries in the registry.
5. **PAEOS-7 §2** (narrow-waist Protocols / "build the constitution, buy the plumbing") — a cross-link:
   AI-010 Port Independence is the *checked* form of that principle.
6. Each invariant **cites its basis** back into the corpus (AI-002→IP-0005/B2.G, AI-004→IP-0007/B2.K,
   AI-005→B2.O, AI-001/010→`reviews/architecture/evidence-source-cer1.md`), so the registry is a
   two-way index between law and its enforcement.

**Not touched:** PAEOS-4 (no kernel amendment) — the invariants are downstream conformance, like the
adapter conformance suite C1–C8.

---

## Summary table

| | IP-0009 (Evolution Loop) | IP-0010 (Invariants registry) |
|---|---|---|
| Classification | Governance | CI + architectural |
| Law verb | **Names** an existing process | **Clarifies + executes** (AI-010/011 formalise) |
| Primary home | `methodology/CONSTITUTIONAL-EVOLUTION-LOOP.md` (new) | `architecture/invariants.yaml` + `ops/ci/invariants.py` (new) |
| Cross-links | `operations/ENGINEERING_LIFECYCLE.md`, PAEOS-7 §7.4 | `.github/workflows/ci.yml`, PAEOS-8 §8, PAEOS-7 §2 |
| Touches PAEOS-4? | No | No |
| Sequencing impact | None (descriptive) | Yes (a build task; the stabiliser) |

---

## Recommended next Phase-3 task (given the newly ratified architecture)

**Implement IP-0010 — the Architectural Invariants registry — seeded with AI-001..011, and wire it
into CI (absorbing F1/F2/F3).** Rationale:

- It **stabilises the foundation** you named: it converts a month of hard-won architectural discoveries
  (port independence, single committer, adversary-PASS seal, probative evidence, read-only evidence,
  lifetime ownership) from prose into **CI-enforced properties** — so none can silently regress as
  Phase-3 features (scheduler, governor, concurrency) land on top.
- The **immediate regression guard** it earns is **AI-010 Port Independence** — the very invariant the
  WorkerTransport trilogy proved (`grep "import mcp" runtime/` excluding `transports/`). Encoding it now
  locks in the R5 payoff.
- It is **low-risk and self-contained** (a YAML + a small executor + one CI step; F2-SOFT), and it is
  the direct implementation of a just-ratified proposal — the cleanest possible re-entry to
  implementation after this governance checkpoint.

Ride-along (cheap, optional, from the Phase-3 review's *improvements*): the two smudges — rename
`WorkerTransport` → an evidence-typed transport name + keep `AgentRuntime` as execution; and relocate
the core-owned ports (`CourtBackend`/`ScarBackend`/`EvidenceSource`) out of the adapter module into a
`runtime/ports.py`. Both are pure refactors that make AI-010/AI-011 cleaner to verify — natural to do
*with* IP-0010, not before it.

Deferred (higher-risk / feature work, after the foundation is enforced): the live fully-autonomous run
(deployment), the continuous `RESTART` scheduler, the economic governor, multi-goal concurrency.
