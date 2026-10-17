# constitution/ — Trust Zone 0 (IMMUTABLE)

The sealed constitutional layer (PAEOS-8 §1). At runtime this directory is **read-only**;
its only legal writer is `kernel/amendment.py` (PAEOS-7 §7.4).

**B0.0 status:** directory skeleton only. Population is a later task:
- `PAEOS-0..6.md` — copied read-only from the source corpus (task **B0.3**, the constitution
  accessor). *(Note: the source corpus currently lives across `derivation/`, `spec/`, and
  `reviews/`; consolidating it into `constitution/PAEOS-0..6.md` is a genesis/B0.3 concern,
  not B0.0.)*
- `canaries/` — known-bad artifacts (PAEOS-7.5 A-1), authored per task **B0.14**.
- `classifier_rules/` — soft/hard blast-radius rules (PAEOS-7.5 A-1/A-2), used by
  `kernel/classifier.py` (task **B0.11**).

Everything under this directory is TCB and amend-only; the CI TCB-diff gate (§8 F2) blocks any
change here from merging without a human ratifier + Adversary review.
