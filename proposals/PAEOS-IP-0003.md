# PAEOS-IP-0003 — Pin the StageId legal-edge table: weight-class semantics + failure-edge scope

Status: **AWAITING FOUNDER RATIFICATION** · Filed: 2026-07-27 · Channel: CER-2
Source finding: Task **B0.5** (Lifecycle legal-edge table & `is_legal`, PAEOS-8 §10). Halt per
the constitutional preamble + CER-6: `is_legal(from, to, weight_class)` cannot be implemented
faithfully because the corpus (a) does not enumerate the fast-path `StageId` edges and (b)
**contradicts itself** on whether edges differ by weight class. This proposal recommends; it
changes nothing until ratified. **No `kernel/lifecycle.py` was written.**

## 1. Observation

B0.5 requires `is_legal(from_state, to_state, weight_class) -> bool` — `propose_transition`
step 2 (PAEOS-7.6 §4): "assert edge(from → to) is legal for this goal's WeightClass." The
`StageId` forward topology is clear in PAEOS-7 §4.1, but two things needed by `is_legal` are
not derivable without invention:

**(A) Failure-edge scope.** §4.1's mermaid draws Adjudication→Ideation / Adjudication→
Construction / Adjudication→[*] as chamber-level **REMAND/REJECT** arrows. §4.4 defines these
as **`Outcome`s** (REMAND/REJECT/QUARANTINE/ABORT — the `Outcome` enum), effects of a *failed*
gate, with `TransitionResult.remand_to` chosen **by the kernel**. Their exact `StageId`
endpoints are never enumerated. So: are remand edges part of `is_legal`'s table, or are they
kernel failure-routing outside it?

**(B) Weight-class contradiction.** Three constitutional sources disagree on whether the legal
edges differ by weight class:
- **PAEOS-9 §2.3:** "The pipeline shape is **invariant**; only the *cost* of the front-end
  contracts." Trace-A *auto-discharges* L03–L11/L17–L18 but "auto-discharge ≠ skip" — every
  state still emits a stub, so the **edge set is unchanged**.
- **`WORKFLOW_STATE_MACHINE.yaml` L02:** a direct **`L02 → L12`** transition for `trace_a`
  (i.e. `TRIAGE → IMPLEMENT`), plus §0.4 "re-derivation is **Trace-B only**." Here the **edge
  set differs** by ceremony/weight class.
- **PAEOS-8 §10 B0.5 acceptance:** "fast-path vs full-path edges **differ by weight class**."

## 2. Current behaviour

Nothing implemented for B0.5. The unambiguous **forward `StageId` topology** (derived verbatim
from §4.1, agnostic of the two questions above) is the agreed baseline:

```
RAW → RE_DERIVE                                           # entry ([*] → S0)
RE_DERIVE → INTAKE → TRIAGE                               # Derivation chamber (S0→S1→S2)
TRIAGE → IDEATE                                           # G1 admitted (Derivation→Ideation)
IDEATE → RESEARCH → TRADEOFF → MITIGATION → DESIGN → CRITIQUE   # Ideation (S3→…→S8)
CRITIQUE → PLAN                                           # G2 design ratified (Ideation→Construction)
PLAN → IMPLEMENT                                          # Construction (S9→S10)
IMPLEMENT → VERIFY                                        # G3 (Construction→Adjudication)
VERIFY → ADVERSARIAL_REVIEW → LEDGER_SYNC → SEAL          # Adjudication (S11→…→S14)
SEAL → RETROSPECT                                         # G4 sealed (Adjudication→Evolution)
RETROSPECT → EVOLVE → MEMORY_UPDATE → IMPROVE_RUNTIME → RESTART   # Evolution (S15→…→S19)
RESTART → RE_DERIVE                                       # RE-EXECUTE (Evolution→Derivation, stage 19)
```

This is a total of 20 forward edges over the 21 constants — clean and enumerable. What is *not*
derivable is (A) the failure/remand edges and (B) the weight-class variation.

## 3. Proposed improvement

Two decisions, pinned in PAEOS-7 §4.1 (and mirrored to `WORKFLOW_STATE_MACHINE.yaml`):

**(A) Failure edges are OUT of `is_legal`.** `is_legal(from, to, weight_class)` governs only
**requester-initiated forward edges** (the list in §2). REMAND/REJECT/QUARANTINE/ABORT are
`Outcome`s produced by the kernel's gate-failure routing (§4.4, `propose_transition` step 6),
with `remand_to` set by the kernel — not requested transitions. This matches PAEOS-7.6 §4
(the `Outcome` enum + `TransitionResult.remand_to`) and keeps `is_legal` a pure forward-edge
oracle. *(If instead remand edges must be legal for the requester, their exact `StageId`
endpoints must be enumerated — a larger amendment; not recommended.)*

**(B) Adopt the "edges differ by weight class" reading**, reconciling §2.3:
- `KERNEL_TOUCHING` / `SUBSTANTIAL` (Trace-B): the **full** forward chain in §2, including
  `RAW → RE_DERIVE → INTAKE → TRIAGE`.
- `ROUTINE` (Trace-A): the **same chain plus the compression edge `TRIAGE → IMPLEMENT`** (the
  `StageId` image of YAML `L02 → L12`), and `RE_DERIVE` is not required (`RAW → INTAKE`
  permitted). Auto-discharge stubs still populate the skipped states in the ledger, so §2.3's
  "shape invariant / complete replayable record" holds at the *ledger* level while `is_legal`
  admits the compressing edge at the *transition* level.

Net: `is_legal` returns `True` for a superset of edges under `ROUTINE` (adds `TRIAGE →
IMPLEMENT`, `RAW → INTAKE`) versus `KERNEL_TOUCHING`. That is the "fast-path vs full-path edges
differ by weight class" the acceptance requires.

## 4. Justification

- (A) keeps `is_legal` minimal and matches the wire contract (§4 `Outcome`/`remand_to`);
  failure routing is a *kernel* responsibility, not an edge the requester may ask for.
- (B) is the only reading that satisfies **both** the B0.5 acceptance **and** the YAML (the
  frozen operations doctrine that "governs paeos-runtime"), while preserving §2.3's actual
  guarantee (a *complete, replayable ledger*) — §2.3's "shape invariant" is about ledger
  completeness, not about the reference monitor refusing the compression edge. This is also the
  "primary economic control" (§13.8): the fast path must be a *cheaper edge*, not merely cheaper
  bookkeeping.

## 5. Risks

- (B) widens the ROUTINE edge set; a mis-triaged irreversible goal taking `TRIAGE → IMPLEMENT`
  would skip design/review. Mitigation: ceremony depth is assigned at TRIAGE from `v × r` (kernel
  router); KERNEL_TOUCHING can never be ROUTINE (weight class is set before this edge is offered).
- If the founder instead means §2.3 literally (topology truly invariant), then the B0.5 acceptance
  wording "edges differ" should be **amended** to "ceremony differs," and `is_legal` ignores
  `weight_class` — a valid alternative resolution (see Recommendation).

## 6. Backwards compatibility

No code depends on `is_legal` yet (B0.5 unwritten; B0.6 gates depend on it but are unbuilt).
Zero migration. Whichever reading is ratified is the first implementation.

## 7. Constitutional impact

Amends **PAEOS-7 §4.1** (adds an explicit `StageId` legal-edge table + weight-class rule) and
mirrors to `WORKFLOW_STATE_MACHINE.yaml`. This touches **lifecycle** law → **CER-5 founder
ratification required**; it is operational/lifecycle, not a kernel-invariant (K-series) change,
so it does not need the §14.5 kernel ceremony — founder ratification suffices.

## 8. Recommendation

**Ratify (A) + (B)** as written. Smallest amendment: add the §2 edge list to PAEOS-7 §4.1 as
the canonical table, annotate `TRIAGE → IMPLEMENT` and `RAW → INTAKE` as `ROUTINE`-only, and
state that failure outcomes are kernel-routed (not `is_legal` edges). On ratification I implement
`kernel/lifecycle.py::is_legal` as a direct transcription and verify it over all 21×21 `StageId`
pairs × 3 weight classes.

**Alternative if you mean §2.3 literally:** ratify (A) only, declare the topology weight-class-
invariant, and amend the B0.5 acceptance to "ceremony (not edges) differs by weight class." I
will implement `is_legal` ignoring `weight_class` accordingly. Either way, one founder decision
unblocks a faithful implementation.
