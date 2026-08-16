# Worker Package: G-ROOT — Root Goal Authoring (FOUNDER TASK)

## Purpose
Author the root Goal "PAEOS is self-hosting" and set its appetite budget. This is an A4
act: no agent may perform it. The package reduces founder effort to filling a template
and making two genuine judgments (appetite, constraints).

## Forcing kernel clause
K4 §10.2 (root budgets founder-set) · K4 §13.3 (evidence spec) · K4 §14.1 (founder ABI) · PAEOS-3 SVK-8.

## Dependencies
F-SCHEMA (goal shape). Executed via `cli author` once I-CLI exists, or as a G-RUN input file before that.

## Owned files
```
genesis/root-goal.json
```

## Template (fill the ⟨⟩ slots; everything else is fixed)
```json
{
  "id": "<ULID …G01 from allocation table>",
  "type": "goal", "version": 1, "prev": null,
  "kind": "work",
  "spec": {
    "delta": "[c1] The PAEOS kernel implementation passes conformance C1-C8 on the null
              and reference adapters. [c2] A change to PAEOS itself traverses
              declared→integrated under agent execution. [c3] One incident→amendment
              cycle completes through provisional. [c4] Founder writes during the
              ratification window are confined to the five ABI verbs.",
    "evidence_spec": [ K4 §13.3 criterion, transcribed verbatim as EvidenceReq entries —
                       classes: execution (C-suite runs), external (founder ratification
                       decision) ],
    "constraints": [ ⟨refs to constitution K01–K11⟩, ⟨founder additions, if any⟩ ]
  },
  "parent": null, "serving_clause": null,
  "budget": { "allocated": { "tokens": ⟨appetite⟩, "exec_seconds": ⟨⟩,
              "verification_passes": ⟨⟩, "decisions": ⟨how many escalations you will fund⟩,
              "wall_clock_s": ⟨⟩ } },
  "status": "declared", "assignee_class": "agent", "workload": null
}
```

## Founder judgment points (the only two)
1. **Appetite** (K4 §10.2): the budget is a bound, not an estimate. Guidance: `decisions`
   is your own attention — set it low (≤ 12) and let exhaustion incidents tell you if the
   system escalates too much. That signal is the point.
2. **Additional constraints**: anything you want binding on ALL implementation work
   (e.g., language choice, licensing). Add now or accept escalations later.

## Invariants
Delta clauses tagged per SC-05 (children will cite `…G01#c1` etc.) · evidence_spec is
K4 §13.3 verbatim — editing it redefines self-hosting and is a constitutional change.

## Acceptance tests
Schema-valid vs F-SCHEMA · evidence_spec verbatim-matches §13.3 · budget vector complete,
all dimensions > 0.

## Conformance / downstream
This goal is the parent of every Wave 1+ node registered post-handoff; M-RATIFY is its
verification event.

## Commit boundaries
1 commit, founder-authored: `genesis: root goal (G-ROOT)`.

## Forbidden modifications
None apply to the founder (H2, parchment clause) — but note: post-G-RUN, edits to this
file outside `cli author` are auto-incidents by design.

## Review checklist (self-review, or ask Fable to adversarially interrogate per A-15)
- [ ] Root-goal ceremony performed: has an adversarial pass challenged the delta's
      clauses for gaps? (A-15 — recommended before commit)
- [ ] Appetite is a genuine bound you accept the system halting at
- [ ] Constraints are complete — silence here = escalations later
