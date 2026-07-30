# PAEOS-IP-0004 — Scar-ownership: who writes the stage-17 (MEMORY_UPDATE) scar?

Status: **AWAITING FOUNDER** · Filed: 2026-07-30 · Channel: CER-2
Source finding: Task **B2.F** (Evolution Layer, stages 15–18, PAEOS-7 §7 / §8 Ph2). Building the
Evolution Layer surfaced a **conflict between two ratified components** over who owns the stage-17
"failure → scar" write. Resolving it would change **ratified behaviour** (the B1.F SoftLoop inline
scar), so per the constitutional preamble + CER-6 this is a **halt-and-surface**: the proposal
recommends; **nothing is implemented**, and B2.F ships on the currently-ratified behaviour only.
Implementation of any option below requires separate founder approval.

## 1. Observation

Two ratified components both perform the stage-17 (`MEMORY_UPDATE`) action "a court remand becomes
a scar" (FR-6, §7.1), with **different signatures** and **incompatible recurrence semantics**:

- **B1.F / B1-SOFTLOOP** — `SoftLoop.run` writes an **inline** scar on court remand
  (`runtime/orchestrator/__init__.py`), signature `{stage:VERIFY, kind:court-remand}` — coarse, no
  goal-specific tags. Directly asserted by `tests/runtime/test_soft_loop.py:133` and exercised by
  `tests/runtime/test_selfhost.py`.
- **B2.F** — the `EvolutionLayer` writes a **post-run** scar, signature
  `parse_signature(goal_signature) | {stage:VERIFY, kind:court-remand}` — precise, goal-tagged — and
  additionally emits an **IMPROVE_RUNTIME** amendment proposal on a *TCB-implicated recurrence*
  (a failure whose guard already existed yet did not hold; §7.4 / A-3 cumulative drift).

## 2. Current behaviour (ratified — B2.F does not change it)

`SoftLoop.run`, on `VerdictOutcome.REMAND`, calls `self._scars.propose_scar(ScarDraft(signature=
frozenset({"stage:VERIFY", "kind:court-remand"}), …))` and returns `REMANDED`. The scar store is
shared across a `SelfHostRunner` backlog, so this coarse scar persists for the rest of the run set.
The `EvolutionLayer` (B2.F) is delivered **standalone** — fully tested, with its closed loop into
the B2.E amendment gate demonstrated — but is **not wired into** `SoftLoop`/`SelfHostRunner`,
precisely to avoid changing this ratified behaviour.

## 3. The conflict

If the Evolution Layer runs *after* the SoftLoop over the **same** shared store, the SoftLoop's
coarse inline scar `{stage:VERIFY, kind:court-remand}` is a **subset of** every remand's evolution
signature. So the Evolution Layer's recurrence check —
`match_scars(goal_signature + failure_tags)` — returns non-empty on the **first** failure, and
falsely emits an IMPROVE_RUNTIME amendment proposal for a first-time defect. The two components
cannot both own the stage-17 write without corrupting recurrence detection. This is not a bug in
either component in isolation; it is an **unallocated responsibility**: the corpus never says *which
layer owns MEMORY_UPDATE*. §7.1 assigns "learning from failed implementations" to the self-improvement
machinery (stages 15–18); §4.3/§5.3 give the Court/loop the duty to *detect and remand*. Whether the
remand-to-scar write belongs to the **loop** (immediate guard) or the **Evolution Layer** (stage 17)
is genuinely ambiguous in PAEOS-7.

## 4. Architectural options

- **Option A — Evolution Layer owns stage 17 (recommended).** Remove the inline scar from
  `SoftLoop.run`; the `EvolutionLayer` becomes the single writer of remand/halt scars, wired as a
  post-run pass in the self-host driver. One owner, precise (goal-tagged) scars, correct recurrence.
  *Cost:* changes ratified B1.F behaviour; updates `test_soft_loop.py` and `test_selfhost.py`.
- **Option B — SoftLoop keeps the coarse scar; Evolution Layer adds only proposals + skills.** The
  Evolution Layer stops writing scars and consumes the loop's scars for recurrence/proposal logic.
  *Cost:* recurrence must distinguish "the loop's own just-written scar" from a genuine prior scar —
  requires a provenance/run-id tag on scars (a new mechanism), and scars stay coarse.
- **Option C — Two-tier scars by design.** Bless both writes: a coarse *immediate* guard (loop) and
  a precise *retrospective* scar (Evolution Layer), with recurrence keyed only on precise scars.
  *Cost:* deliberate redundancy; recurrence logic must filter by tier (needs a `tier`/`kind` marker);
  two scars per remand accrete.
- **Option D — Status quo (do nothing).** Evolution Layer stays standalone (never wired into the
  loop). *Cost:* the self-improvement loop never actually closes during self-hosting — the layer is
  "built but not running."

## 5. Recommended resolution

**Option A.** The Evolution Layer is the constitutionally-named home of stages 15–18; MEMORY_UPDATE
(stage 17) is *its* stage. The loop's job is to **detect and remand** (§4.3/§5.3), not to author
memory. Concentrating the stage-17 write in the Evolution Layer gives one owner, precise scars, and
correct recurrence — and it makes the loop's inline scar what it always was: a B1.F expedient placed
before stages 15–18 existed. Option B invents a provenance mechanism to work around a misplaced
write; Option C blesses redundancy; Option D leaves the loop open.

## 6. Constitutional derivation

- **§7 / §8 Ph2 component 1** places retrospective→memory→proposal (stages 15–18) in the **Evolution
  Layer**. Stage 17 = `MEMORY_UPDATE`. The write belongs there.
- **§4.3 / §5.3** assign the Court/loop the duty to reproduce, detect, and **remand** — not to write
  learning. Separation of concerns: *detection* (loop) vs *learning* (Evolution Layer).
- **FR-6** ("no rule without a scar") is satisfied either way; the question is *ownership*, and the
  architecture already names the owner (the Evolution Layer).
- **A-2 / precision doctrine** (`runtime/memory`): scars should be *precise, never firing on
  unrelated goals*. The coarse `{stage:VERIFY, kind:court-remand}` scar violates this in spirit
  (fires on any VERIFY remand); the Evolution Layer's goal-tagged signature honours it.
- **CER-5 / §7.4**: none of this lets the runtime self-apply anything — the Evolution Layer only
  *proposes*; amendments still halt at the human gate. This proposal changes *where a scar is
  written*, not *who ratifies*.

## 7. Implementation impact (if Option A is later approved — NOT done here)

- `runtime/orchestrator/__init__.py`: delete the inline `propose_scar` block in `SoftLoop.run`
  (keep the `REMANDED` return); the loop no longer writes scars.
- `runtime/selfhost.py`: run the `EvolutionLayer` as a post-run pass over each `(outcome, intake)`,
  accumulating scars (shared store) and surfacing IMPROVE_RUNTIME proposals; report them from the
  CLI `self-host` command.
- Tests: `tests/runtime/test_soft_loop.py` (the direct inline-scar assertion) and
  `tests/runtime/test_selfhost.py` (the run-writes-a-scar assertion) move from asserting the loop's
  coarse scar to asserting the Evolution Layer's precise scar. No kernel change; F2-SOFT throughout.
- Scope: this is a behavioural change to **ratified** B1.F/B2.B components and must run as its own
  task under a dedicated Constitutional Review — **not** folded into B2.F.

## 8. Recommendation

Ratify **Option A** as a **separate** follow-on task (proposed id **B2.G — stage-17 consolidation**),
executed under its own review. Until then, **B2.F ships standalone on ratified behaviour**, and the
Evolution Layer is not wired into the loop. This proposal recommends; it changes nothing until
ratified. **No ratified behaviour was modified in B2.F.**
