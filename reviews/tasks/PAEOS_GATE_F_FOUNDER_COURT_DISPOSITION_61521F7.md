# Founder/Court Disposition — Gate F Bootstrap Integration

- **Disposition:** `COURT_SEALED`
- **Candidate:** `61521f7429462a4e015feb285cb20a5b39c78294`
- **Gate:** F — Canary Bootstrap & Dormant Promotion
- **Bootstrap evidence manifest:** `operations/PAEOS_GATE_F_BOOTSTRAP_EVIDENCE_61521F7.json`
- **Manifest SHA-256:** `24cdbe28005a14b12125dab2c6a274c5f893be7858f114954d37cc26e2828328`
- **L13 reproduction:** 28/28 focused tests passed, exit 0
- **L14/L17 audit:** qualified Gemini `gemini-3.6-flash` / family `gemini`, A-08 PASS versus
  GLM builder; report SHA-256 `5261730a1cf4acf127d58116317dc358591bdf6197a36d951f43b93dfaeaccbb`;
  canonical receipt SHA-256 `afe02a7540b7fd72d3f6da95c8a0c7a72069e7d89715500b48061e65d7abc3c6`

## Founder/Court decision

The Founder/Court accepts the bounded Gate F pre-bootstrap evidence and authorizes **one-time
isolated bootstrap integration** for this exact candidate and manifest. `DEBT-0060` and `RB-0027`
remain explicitly **OPEN**. Repository-wide static debt, the two loaded Cline timeout assertions,
and the missing live route/rotation/quota window remain visible residual conditions; they are not
silently waived or counted as green.

This disposition authorizes no promotion canary, protected-ref update, main/trunk mutation, merge,
push, credential operation, production dispatch, or SAKG resumption. Those actions require their
own candidate-bound evidence and dispositions. Codex records this external authority and does not
extend it.
