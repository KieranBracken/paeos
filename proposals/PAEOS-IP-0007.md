# PAEOS-IP-0007 — The soft loop seals despite a blocking adversarial dissent (FR-3 is toothless)

Status: **AWAITING FOUNDER** · Filed: 2026-07-30 · Channel: CER-2 (security-critical)
Source finding: the **live R4 self-hosting runs** (contained, founder-authorised). Inspecting what the
live agents actually did — rather than trusting the `SEALED` status — revealed that a run **seals even
when the isolated Adversary returns BLOCK with blocking dissents**. This is a constitutional defect in
a *ratified* component (`SoftLoop`, B1-SOFTLOOP); per CER-5/CER-6 it is surfaced here, not silently
patched. **No code is changed by this proposal.**

## 1. Observation

`runtime/orchestrator/__init__.py` `SoftLoop.run` dispatches the isolated Adversary, charges its
budget, and then **seals unconditionally over `adversary.trace_ref`** — it never inspects the
adversary's result for a blocking dissent:

```python
adversary = self._review.review(...)      # returns a TaskResult (its report is in CAS)
budget.charge(adversary.cost)
# ... no check of the adversary's verdict ...
seal = self._seal.seal(..., adversary_ref=adversary.trace_ref)
return RunOutcome(RunStatus.SEALED, ...)   # seals regardless of what the adversary found
```

In R4 run #4 the live Adversary filed **three blocking dissents** ("there is nothing to attack; the
sealed bundle is unreadable… ❌ BLOCK") and the run **still SEALED** (seal `072803e1…`, a
K3-verifiable chain). The adversary's dissent had **no effect** on the outcome.

## 2. Why this matters (FR-3 / MR / T-series)

FR-3 (Independent Adversarial Review) and the derived Separation of Powers (MR/§5.1) require that an
**independent adversary that fails to break the change is a precondition of the seal** (PAEOS-3.5).
Today the adversary is *run* but its verdict is *ignored*, so:

- A defective or dissented-upon change can reach `SEAL` (defeats FR-3; the §7.5 threat "advance a
  defective goal to SEAL").
- The seal is **cryptographically valid but constitutionally hollow** — `verify_chain` passes, yet the
  seal encodes no adversarial approval.
- This compounds two other live-run gaps (below), but it is the **load-bearing** one: even with real
  context and a real change, a seal that ignores dissent is unsound.

## 3. Current behaviour

The adversary's blocking dissents live only in its report artifact (`review/adversary_report.md`) and
its trace; the loop stores the trace hash in the seal but performs **no adjudication** of it. There is
no machine-readable adversary verdict the loop consumes (the same "no adversary verdict type" gap noted
in the B2.E amendment analysis).

## 4. Proposed improvement (recommended; not implemented)

Make the seal **conditional on the adversary's verdict**:

- **Option A (recommended).** Give the Adversary review a machine-readable verdict
  (`PASS` / `BLOCK` + dissents), the way the Court has `VerdictOutcome`. `SoftLoop.run` **REMANDS** on
  `BLOCK` (writes the run as REMANDED, an L1 note; the Evolution Layer may author a scar) and only
  seals on `PASS`. This mirrors the Court gate and closes FR-3 by construction.
- **Option B.** Parse the adversary's report for a structured dissent marker and remand on any blocking
  dissent. Weaker (text parsing), but no new type.

Both are **F2-SOFT** (`runtime/`), and both change **ratified** B1-SOFTLOOP behaviour, so the fix is a
dedicated task under its own Constitutional Review — proposed **B2.K**.

## 5. Risks / compatibility

- Existing tests script an Adversary that "completes" without a structured verdict; Option A adds a
  verdict to the review harness and updates those tests. No kernel change.
- Interaction with the seal is additive (a new precondition); the seal machinery is unchanged.

## 6. Constitutional impact

- **PAEOS-7 §4.3/§5.3/FR-3** — clarify that the seal requires an adversarial **PASS**, not merely a
  completed review. Execution-architecture clarification + the B2.K implementation.
- No PAEOS-4 amendment: FR-3 already requires it; the loop simply fails to enforce it.

## 7. Recommendation

**Ratify Option A** and schedule **B2.K** (gate the seal on the adversary verdict) as the
**highest-priority** Phase-2-seal task — a seal that ignores a blocking dissent must not stand. This
recommends; it changes nothing until ratified.

---

## Appendix — the two companion gaps the live R4 runs exposed (for the record)

1. **Agent workspaces are not given their context.** Each session runs in an isolated **empty** temp
   workspace; the constitution, prior-stage design/plan artifacts, and (for the adversary) the sealed
   bundle are referenced by hash in the prompt but **not materialised as files**. So the live Planner
   ("working tree is empty… I won't fabricate a plan") and Builder ("no ratified plan to implement
   against") **blocked**, and the Adversary could not read its bundle. Fix (proposed **B2.J**): seed
   each session's workspace with its read-scope artifacts + constitution. F2-SOFT.
2. **Staged evidence.** The court adjudicates pre-declared `echo` evidence, not the agent's real test
   output (the live-evidence-via-court-MCP flow, runbook §5 / B2.B Obs 1). Toward R5.

Together with IP-0007 these are why the R4 pipeline **runs and produces a verifiable seal but the seal
is not yet constitutionally genuine** — Phase 2 is not sealed until B2.J + B2.K land (and, for a
non-staged seal, the live-evidence flow).
