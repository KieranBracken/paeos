# RB-CEREMONY-DEPTH-001 — Deliverable D1: Canonical Ceremony-Depth Doctrine Extraction

Status: **D1 COMPLETE (extraction)** · 2026-08-19 · Research step 2 of the approved R4 sequence
Authority grounding: `operations/ENGINEERING_LIFECYCLE.md` (v1.3) is the canonical L01–L19 baseline;
`operations/WORKFLOW_STATE_MACHINE.yaml` is its derived machine-executable form (prose EL wins on
conflict). No Freeze document is an authority (see `PAEOS_HALLUCINATION_CHECKER_NOTEBOOK.md` Entry 146).

> Purpose: answer RB-CEREMONY-DEPTH-001's "who / when / what / how" from existing canonical
> doctrine, so the L02 ceremony contract can be built by *implementing existing law*, not by
> legislating. Every statement below carries a file:line citation to the canonical source.

---

## 1. Who assigns ceremony depth

- **L02 Triage, Planner (Router).** EL L58–65: L02 purpose is "decide whether this deserves
  engineering effort, and at what ceremony depth"; Required artifacts include
  "**classification (v × r) → ceremony depth**". WSM `ceremony_depth.assigned_at: L02` (WSM L57).
- Disposition is chosen from Keep / Merge / Reject / Dormant / Research / Immediate-Priority
  (EL L61). Approval: Reject/Dormant on founder-authored intent → founder confirmation; else
  automatic (EL L63).

## 2. When it is assigned

- **At L02, immediately after L01 intake**, before any engineering state (EL L58–65; WSM L57).

## 3. The depth classes that exist

- Exactly **two named classes** in the EL:
  - **Trace-A** — "reversible, cheaply verified" (EL L24); the volume case.
  - **Trace-B** — "irreversible / expensive to verify" (EL L27); full ceremony.
- WSM `levels: trace_a / trace_b` (WSM L59–68) matches the EL. (The EL does **not** name a
  Trace-C; any such label in secondary docs is non-canonical.)

## 4. The classification factors (v × r)

- **verifiability × reversibility** is the explicit basis: EL L22 "ceremony depth, assigned at
  L02 from verifiability × reversibility"; WSM `basis: [verifiability, reversibility]` (WSM L58).
- The canonical 2×2 (derivation/PAEOS-0-foundations.md L42–49):
  | | Cheap to verify | Expensive to verify |
  |---|---|---|
  | **Reversible** | Full autonomy, tournament-style | Autonomy + adversarial critique |
  | **Irreversible** | Autonomy + mechanical gate | **The only quadrant requiring founder judgment** |
- Mapping to traces: **Trace-A = reversible AND cheaply verified** (the bottom-left quadrant, EL L24).
  **Trace-B = everything else** (irreversible OR expensive-to-verify — the other three quadrants),
  executed "all 19 states ... in full, with founder Decisions at the gates" (EL L27–28).

## 5. Which layers may be discharged under each class

- **Trace-A auto-discharges:** L03, L04, L05, L06, L07, L08, L09, L10, L11, L17, L18
  (WSM `trace_a.auto_discharge` L62; EL L24–25 "auto-discharges L03–L11 and L17–L18").
- **Trace-A executes in full:** L01, L02, L12, L13, L14, L15, L16 (EL L26 "...L01–L02, L12–L16...
  in full"), plus L19 if triggered (EL L26).
- **Trace-B executes:** all 19 in full with founder Decisions at the gates (EL L27–28).
- WSM L128–129 codifies the L02→L12/→L03 split: `ceremony=trace_a` → L12 (auto-discharge of
  L03..L11); `ceremony=trace_b` → L03.

## 6. Layers that are NEVER dischargeable

From the Trace-A execute-in-full set, these may never be auto-discharged even on the fast path:
**L01 Intake (capture), L02 Triage (the classification itself), L12 Implementation, L13
Verification, L14 Independent Audit, L15 Documentation & Ledger, L16 Promotion Decision, and
L19 Constitutional Evolution (if triggered)** (EL L24–26; WSM L62). L14 executes in full on
Trace-A (Trace-A does not exempt L14 — EL L26 lists L14 in the execute-full set).

## 7. Required discharge evidence

- **Auto-discharge ≠ skip.** Every auto-discharged state MUST emit an evidence stub so every
  transition remains valid (K1: no transition without evidence):
  `{result: auto_pass, reason: trace_a, by: runtime}` (WSM L70–72; EL L29–30 "...it emits the
  evidence stub that keeps every transition valid").

## 8. Escalation / de-escalation / v×r evaluation (genuinely open edge cases — RB design scope)

The above answer RQ-1's structural questions. The following are NOT fully specified in the EL and
remain **known edge cases for the L02 ceremony-contract design step** (do not legislate canonical
law here):

- **How v/r are concretely evaluated** (the EL names the axes and the 2×2 but not a scoring rubric).
  Non-canonical floor that IS canonical: any **TCB/kernel-touching classification is always
  KERNEL_TOUCHING → full path** — an agent cannot triage-inflate onto the fast path
  (`runtime/triage.py`; EL/WSM conservative-by-design). Budget breach halts (K11).
- **Mid-run escalation:** whether/how a run escalates from Trace-A to Trace-B mid-flight; the EL
  states TCB impact forces the full path and HALT rules, but not a general automatic-escalation
  mechanism. The RB negative-test matrix (case E, "implementation discovers TCB impact" → ceremony
  escalates) is a design target, not yet canonical.
- **De-escalation:** generally disallowed (autonomy must never under-classify to save cost — T6
  principle); no canonical de-escalation clause exists. Treat as "not permitted unless a ratified
  amendment says otherwise."
- **Substantive execution replacing a lawful discharge:** the EL forbids *silently skipping*; it
  requires a stub for each auto-discharge. Whether a substantive run of a dischargeable layer may
  *replace* the stub is answered positively by design (substantive output is stronger evidence) but
  the stub-recording discipline must still hold.

## 9. Conflict-resolution authority

- If any document conflicts with this extraction, the Engineering Lifecycle (v1.3) prose wins,
  subject only to a valid ratified amendment (proposals/PAEOS-IP-*, A-series, ratified specs).
  Derived documents (WSM, this extraction, conformance maps, any "Freeze") carry no independent
  authority. See Entry 146.

---

*End of D1. Produced 2026-08-19 from canonical sources; no code changed.*
