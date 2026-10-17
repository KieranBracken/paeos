# PAEOS-IP-0016 — Standing Calibration for Gate C Z0 Canaries

Status: **DRAFT — IMPLEMENTATION CHECKPOINT** · Filed: 2026-09-01 · Channel: CER-2
Level: **operational detector coverage** (no lifecycle, authority, or Z0 schema change)
Source: Gate C post-ratification verification; the standing calibration tripwire missed
CANARY-0003 through CANARY-0009 after their Founder ratification.

## 1. Observation

`runtime.calibration.court_detector()` handled the original forged-evidence and vacuous-evidence
categories only. After the Founder ratified the Gate C Z0 catalog, the standing `calibrate` command
loaded nine `CAUGHT`-expected canaries but returned misses for the seven new control-plane
categories. The fail-closed behavior correctly blocked execution, but the detector coverage lagged
the ratified corpus.

## 2. Current behaviour

Unknown canary categories return `False`, producing a calibration miss. This remains the required
fail-safe default. The detector now additionally exercises the existing typed safety boundaries
for instruction fidelity, architecture escape, raw-evidence separation, restart, privacy,
self-ratification, and prompt injection. It matches invariant-bearing artifact shape and values,
not canary IDs or model-authored prose.

## 3. Proposed improvement

Maintain one explicit, tested detector predicate for each ratified Z0 category. Every new
`CAUGHT`-expected category must add a positive calibration case and a safe-control negative case
before it is installed in `constitution/canaries/`. Keep unknown-category behavior fail-closed.

## 4. Justification

This keeps the standing FR-2/FR-3 tripwire meaningful as Z0 evolves, prevents a ratified canary
from becoming an accidental permanent alarm, and preserves the separation between model-authored
data and locally trusted protocol checks. It reinforces CER-1, A-09, and the no-zero-remand rule.

## 5. Risks

- Overly broad predicates could flag legitimate control traffic; safe-control tests constrain each
  category boundary.
- A future canary category may still be unexercisable until its detector is implemented; the
  fail-closed miss is intentional in that case.
- Detector predicates are calibration proxies, not substitutes for end-to-end Court evidence.

## 6. Backwards compatibility

Existing CANARY-0001/0002 behavior and unknown-category fail-safe semantics are unchanged. The
extension only turns the already-ratified Gate C categories from calibration misses into exercised
checks; it does not rewrite historical evidence or ledgers.

## 7. Constitutional impact

None. The catalog remains Founder-ratified Z0; this proposal adds no state, authority, lifecycle
stage, or canary schema field. It is an operational implementation of existing Z0 detection
signatures and remains subject to independent L14/L17 review.

## 8. Recommendation

Accept as an operational implementation checkpoint. Keep the proposal draft unless a future change
would alter Z0 semantics or constitutional authority; such a change would require the normal
Founder-controlled amendment ceremony.
