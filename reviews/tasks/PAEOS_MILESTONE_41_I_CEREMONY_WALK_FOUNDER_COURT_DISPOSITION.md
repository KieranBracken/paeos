# PAEOS Milestone 41 — `[I-CEREMONY-WALK]` / L02-K1 Ceremony Walk

**Disposition:** `COURT_SEALED` (Founder direction)
**Candidate commit:** `fba0a21a664b9e5f8d7f76dfc04e53bcc24a42cd`
**Candidate checkout:** `/private/tmp/paeos-ceremony-walk-worker-001`
**Branch:** `codex/control-plane-recovery-s1-clean-recovered` (isolated candidate checkout)
**Predecessor:** Milestone 40 candidate `a2e3d49bc8cb8a199bf620c9d8ce4ec0f5fe5aac`

## Local SoftLoop evidence

The hermetic run `i-ceremony-walk-trace-a-001` executed under
`/private/tmp/paeos-ceremony-walk-run` and returned `status=SEALED`, `verdict=PASS`, and
Court exit `0`. The local seal hash is
`28ec7e92650a19c94026ec6d0bb8c120a0aabae14846795b42633831dd7d099b`; the ledger head is
`9005b5fc253a7826ee6b90fa6e5258875aa7e2fce9b609e757f96238444f1f62`.

The persisted `ceremony_walk` event contains all canonical layers `L01` through `L19` in
order. Trace-A records exactly eleven K1 `layer_discharged` stubs (`L03-L11`, `L17`, `L18`);
Trace-B executes all nineteen layers without discharge stubs. The candidate checkout was
clean after commit and was not promoted into the host checkout or `main`/`trunk`.

## Reproduction and static evidence

- Focused candidate test: `tests/runtime/test_ceremony_walk.py` — **3/3 passed**, exit `0`.
- Ceremony/SoftLoop regression set — **32/32 passed**, exit `0`.
- Full `tests/runtime` — exit `0`, progress reached `100%`.
- Ruff over `runtime/` and `tests/runtime/` — exit `0`, no findings.
- Focused Pyright — exit `0`, no errors or warnings.
- Full runtime Pyright — exit `1` solely for the inherited unresolved `mcp.server` import at
  `runtime/transports/mcp/court_server.py:21`; this is disclosed, not relabeled as clean.

The external report states **9/9** tests; that count is not reproduced by the committed M41
test file (which has three tests), so the exact local counts above are the authoritative
reproduction record.

## Candidate-bound physical L14/L17 pair

- Evidence bundle: `/private/tmp/paeos-ceremony-walk-m41-bundle.json`
  - SHA-256: `03ade6736c3789fbbe1fb4b9769d5bb11e0c217b715479156f7f4e29ae861905`
- Audit ID: `m41-ceremony-walk-fba0a21-nvidia-001`
- Auditor: NVIDIA `meta/llama-3.2-11b-vision-instruct` (family `llama`)
- Builder recorded by the physical receipt: `cline-pass` / `z-ai/glm-5.3-flash` (family `glm`)
- A-08: `PASS` (`llama != glm`), one provider attempt, fallback chain length one
- Report: `/private/tmp/paeos-ceremony-walk-m41-report.md`
  - SHA-256: `6a3b99a57abb74e95238983b445dce3a82f7ce4aecd9933537b67d3f5f22566f`
- Receipt: `/private/tmp/paeos-ceremony-walk-m41-receipt.json`
  - File SHA-256: `ebb766938818621222e6fa513487c9e71b6461d7fce7a35944233d9698e76f7c`
  - Canonical receipt SHA-256: `495574fec06bd14a067e5e70214b70e0f570633aa53b4d2eb18a7ef2da94ea8c`
- Mechanical artifact-pair adjudication with the receipt's bound contract returned
  `report_status=PASS`, `a08_verdict=PASS`, and `qualified=True`.

The report's concrete finding (that `ceremony_walk` event fields should receive additional
validation) is retained as an integrity follow-up. The earlier dispatch authorization named
Google Gemini, but the supplied persisted pair identifies NVIDIA Llama; the wrapper invocation
also returned `FileExistsError` after the pair appeared. This provider/authorization divergence
is recorded explicitly and is not treated as a new retry or silently substituted. The evidence
pair itself is candidate- and report-bound and is sealed here at the Founder's direction.

## Disposition and accounting

Window accounting: **`Sealed: 1 | Remanded: 0 | Remediated: 0`**. Strict physical program
progress advances from `28/48` to **`29/48 complete | 19 remaining`**. Milestone 42
`[I-LIFETIME-CONFORMANCE]` is opened in
`reviews/tasks/PAEOS_MILESTONE_42_I_LIFETIME_CONFORMANCE_INTAKE.md`.

No source change was made in the host checkout; no merge, promotion, fallback, retry, or
protected-ref mutation occurred.
