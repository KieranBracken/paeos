# PAEOS L14/L17 Capture Disposition — `bdff183`

## Scope

- Candidate: `bdff183accf2a87f78c960f8be75fa54d91d0735`
- Bundle SHA-256: `b6d992aa35d01684a6c4b70344a1d246484676d3ed60b9b62e717c00a8ffda20`
- Audit id: `l14-l17-bdff183-gemini-002`
- Builder: `cline-pass` / `z-ai/glm-5.3-flash` / GLM
- Intended auditor: Google / `gemini-3.6-flash` / Gemini

## Observed transport fact

Router observation `1048` records one successful Gemini AUDIT response (`success=1`, approximately
113,435 ms, 537 prompt tokens, 790 completion tokens). This is provider telemetry only and is not
an L14 verdict.

## Capture result

The receipt-capture process terminated without persisting either expected artifact:

- `/private/tmp/paeos-l14-l17-report-bdff183.md` — absent
- `/private/tmp/paeos-l14-l17-receipt-bdff183.json` — absent

The detached execution boundary retained no stdout/stderr validator or persistence detail. The
exact failure cause is therefore unknown and must not be inferred from the successful provider row.

## Disposition

`BLOCKED_UNQUALIFIABLE` — no candidate-bound physical receipt/report pair exists to validate.

No retry, fallback, second provider request, workaround, code change, promotion, or gate advancement
was performed. Canonical counts remain Worker `0/1/0`, Court `0/0/0`; strict sealed progress remains
`12/48 complete | 36 remaining`.
