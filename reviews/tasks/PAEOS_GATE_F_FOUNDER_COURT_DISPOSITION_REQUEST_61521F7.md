# Founder/Court L16 Disposition Request — Gate F Bootstrap

Status: **PENDING FOUNDER/Court DECISION**  
Recovery branch: `codex/control-plane-recovery-s1-clean-recovered`  
Implementation candidate: `61521f7429462a4e015feb285cb20a5b39c78294`

## Evidence offered for disposition

- Bootstrap evidence manifest: `operations/PAEOS_GATE_F_BOOTSTRAP_EVIDENCE_61521F7.json`
  - SHA-256: `24cdbe28005a14b12125dab2c6a274c5f893be7858f114954d37cc26e2828328`
- Independent L13 reproduction: **28/28 passed**, exit 0; raw log hashes are recorded in
  `reviews/tasks/PAEOS_GATE_F_L13_REPRODUCTION_61521F7.md`.
- Independent physical L14/L17 audit: `L14_STATUS: PASS`, qualified; Google
  `gemini-3.6-flash` / Gemini family versus GLM builder, A-08 `PASS`, one attempt, no fallback.
  Bound report SHA-256: `5261730a1cf4acf127d58116317dc358591bdf6197a36d951f43b93dfaeaccbb`.
  Canonical receipt SHA-256: `afe02a7540b7fd72d3f6da95c8a0c7a72069e7d89715500b48061e65d7abc3c6`.
- Gate F focused verification: **28/28 passed**; synthetic no-promotion canaries: **3/3 passed**.
- No protected ref, main/trunk, merge, push, credential, or production mutation occurred.

## Explicit residual conditions

The disposition must carry these facts rather than silently treating them as green:

- `DEBT-0060` and research item `RB-0027` remain OPEN.
- Repository-wide Ruff has **557 findings** and Pyright has **120 errors**.
- The loaded non-gateway run is **1,152/1,154**, with two pre-existing Cline timeout assertion
  failures; the five corresponding isolated cases pass 5/5.
- Live route probes, clean supervisor rotation, and forced quota-stop evidence are not yet present.

## Requested decision

If the Founder accepts this bounded pre-bootstrap evidence, supply a candidate-bound L16 record
with `Disposition: COURT_SEALED`, the exact candidate and manifest hash above, and explicit
authorization for **only** the one-time isolated bootstrap integration. Task 7 promotion canaries,
protected refs, main/trunk mutation, merge, push, and SAKG resumption must remain prohibited until
their own evidence and dispositions are complete. A `COURT_REMANDED` decision with precise
amendments is equally valid and will be recorded without optimizing for zero remands.

No disposition is implied by this request; Codex does not self-ratify.
