# Wave 0 — Coordination Package

## Pinned-ULID allocation table (SC-10; Crockford base32, 26 chars)
```
Pattern: 01J + 20×"0" + 3-char suffix
Constitution: …K01–…K11, …D01, …D02        Roles: …R01–…R04
Protocols:    …P01–…P04                     Root goal: …G01
Scars:        …S01–…S40 (index.json maps symbolic ids)
Taste seeds:  …T01–…T10                     Fixtures: …F01–…F99
Example: 01J00000000000000000000K01
```
Collisions impossible by suffix discipline; runtime objects use generated ULIDs (never 01J+zeros prefix).

## Assignment & parallelism
All six packages are mutually independent EXCEPT: G-CONST and G-CORPUS share the binding
scar demand table (contract, not sequencing — they can run in parallel against it), and
G-ROOT/G-CORPUS need founder input (appetite; Sentium corpus location). Assign F-SCHEMA
first — it is the critical path (R §13) and three packages consume its merged output for
final validation.

## Review order (Chief Implementation Architect reviews all)
```
1. F-SCHEMA     — everything downstream validates against it; review depth: maximum
2. F-SPI        — frozen surface; review before any adapter thinking begins
3. G-CORPUS     — fabrication risk is the worst defect class; source-check early
4. G-CONST      — mechanical once 1+3 are trusted
5. G-ROLES      — mechanical once 1 is trusted
6. G-ROOT       — founder self-review + A-15 adversarial interrogation (Fable)
```

## Merge order (single integrator per K8 — one person/agent holds the merge lease)
`F-SCHEMA → F-SPI → G-CORPUS → G-CONST → G-ROLES → G-ROOT`
Rationale: shape before consumers; scars before the policies citing them; the root goal
last (it references constitution ULIDs in constraints). No merge before its review; no
partial-package merges (commit boundaries in each package are atomic).

## Integration order (into the eventual G-RUN sequence)
Wave 0 outputs feed genesis commits as: F-SCHEMA→G2 fixtures basis · G-CORPUS→G1 corpus
refs + G7 taste namespace · G-CONST→G4 · G-ROLES→G5 · G-ROOT→G6 · F-SPI→G1 trust-root
context. G-RUN itself is Wave 5 (blocked on I-GEN, I-VAL).

## Constitutional review checklist (applied to EVERY package result)
- [ ] Zero new abstractions: every artifact traces to a K4/R clause or an SC entry
- [ ] Zero unlogged ambiguity resolutions (HALT rule honored; any halt = success, not failure)
- [ ] No spec/** modifications
- [ ] Fixed ULIDs per allocation table
- [ ] Naivety preserved where mandated (protocols, fanout, scheduling)
- [ ] All content either verbatim-from-spec or source-traceable (corpus)
- [ ] Commit boundaries respected (atomic, correctly messaged)

## Expected implementation risks
1. **JCS edge cases** (F-SCHEMA): unicode normalization, number canonicalization,
   key ordering. Mitigation: SC-12 independent-tool rule; goldens are the arbiter.
2. **Fixture combinatorics** (F-SCHEMA): enumeration rule explodes or worker curates by
   taste. Mitigation: the rule is exhaustive-by-construction; lint-coverage is the check.
3. **Scar fabrication** (G-CORPUS): a worker "finds" what the demand table wants.
   Mitigation: source spot-checks in review; vicarious-substitution path removes the
   incentive to invent.
4. **Constitution paraphrase drift** (G-CONST): statements reworded "for clarity".
   Mitigation: verbatim mechanical diff is an acceptance test.
5. **Protocol cleverness** (G-ROLES): retry logic, quality heuristics smuggled in.
   Mitigation: naivety is an explicit acceptance test; reviewer rejects refinement.
6. **CAP overflow** (G-CONST): 13 bodies exceed 12000 tokens. Mitigation: README
   arithmetic committed; if over, HALT — trimming statements is forbidden (candidate
   incident: CAP too small, amend SC-09).

## Likely ambiguity points (pre-resolved — workers cite, never re-decide)
SC-01..SC-12 in SPEC-CLARIFICATIONS.md. Highest-traffic: SC-01 (bytes), SC-05 (clause
tags), SC-06 (TriggerExpr), SC-10 (ULIDs).

## Incidents to watch for (log these the moment they appear)
- A worker HALT on a new ambiguity → incident against PAEOS-4 (the desired signal —
  celebrate, don't suppress)
- Demanded Sentium scar not found in corpus → incident against the G-CONST scar table
  (a rule may lack a real scar: exactly what I7 exists to expose)
- CAP overflow → incident against SC-09
- Any package needing information from another package's *content* (not its contract)
  → incident against the Wave 0 decomposition (read-set overlap: an A-07 seam violation
  in this very backlog)
- F-SPI unable to discharge a §12 sentence into five functions → incident against K4 §12
  (the SPI may not be minimal after all)

## Definition of Wave 0 done
All six packages merged in order · constitutional checklist green on each · SPEC-
CLARIFICATIONS disposition queue ready for G-RUN incident conversion · Wave 1 nodes
(I-CONST, I-STORE, F-VAL, F-COMP, F-ROUTE, F-CONF, F-REFGOAL) unblocked per the backlog DAG.
