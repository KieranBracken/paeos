# Canaries — the detector calibration corpus (PAEOS-7 §5.3)

A **canary** is a deliberately-planted **known-bad artifact**. It exists to be *caught*: if a
detector (the Verification Court, the Adversary, or a gate) fails to catch a canary, the detector
is **miscalibrated** — a *miss* — and that is an alarm (the FR-2/FR-3 tripwire, PAEOS-7 §5.3).
Calibration = periodically submitting the canaries and confirming every one is still caught.

Canaries are **Z0**: immutable, versioned, and part of the constitution. They are authored by the
Builder + Doc and ratified by the founder (they change the system's safety calibration).

## Format

One JSON file per canary, named `CANARY-NNNN.json` (zero-padded, monotonic):

```json
{
  "id": "CANARY-0001",
  "category": "<defect class, e.g. forged-evidence | illegal-transition | stale-replay | power-fusion>",
  "description": "<what is wrong with this artifact, in one line>",
  "expected": "CAUGHT",
  "detection_signature": "<how a correct detector should recognise it>",
  "artifact": { "<the known-bad artifact, shape depends on category>": "..." }
}
```

- **`expected`** is `CAUGHT` — a correct detector must catch it. (`passed = caught == CAUGHT`.)
- **`detection_signature`** documents the mechanism that should fire, so a miss points at the
  exact detector to fix.
- **`artifact`** is the bad payload the detector is run against; its shape is category-specific.

## Harness

`kernel/canary.py` loads canaries (`load_canaries`) and submits each to an injected **detector**
(`run_canary` / `run_calibration`), recording a `CanaryResult` (catch/miss). In Phase 0 the
detector is supplied by the caller/test; in Phase 1 the detector *is* the Court running the
artifact end-to-end. The harness itself is detector-agnostic — it only records the result.

## Seeds

- `CANARY-0001.json` — **forged-evidence** (T2). Deterministic evidence claiming a result its
  `reproducible_command` does not produce; a correct detector re-runs the command (the kernel's
  `verify_deterministic`) and catches the mismatch.
