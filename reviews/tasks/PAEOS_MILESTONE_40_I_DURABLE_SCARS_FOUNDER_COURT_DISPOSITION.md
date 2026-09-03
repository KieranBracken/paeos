# PAEOS Milestone 40 — `[I-DURABLE-SCARS]` / RB-0026

**Disposition:** `COURT_SEALED`  
**Candidate commit:** `a2e3d49bc8cb8a199bf620c9d8ce4ec0f5fe5aac`  
**Implementation origin:** `065b42dcba641e789c8df54b35666c0e907cce0b`  
**Branch:** `codex/control-plane-recovery-s1-clean-recovered`  
**Intake:** `ops/backlogs/intake-rb0026-durable-scars.json`  
**Intake SHA-256:** `e8b867d6814fbce12ad9d7f160df156220a91111c36b6d4a2af5f7609eef7cfc`

## Court evidence

The isolated SoftLoop run `rb0026-scar-store-trace-a-002` executed under
`/private/tmp/paeos-scarstore-run` and sealed with status `SEALED`, Court exit `0`, and
seal hash `16d7478df01ba8ad02e93725d96c0586d0cae26e9d44900c33e578dce8ed3086`. Its local
result bundle is `bf5fd2ee0bc0a7c93a1122d712f3346af09a8c69d834ef4948d92be0a6845637`.

The focused `SqliteScarStore` tests passed `5/5` (exit `0`), focused Ruff and Pyright both
passed (exit `0`), and full Ruff passed (exit `0`). The isolated full-Pyright check exited
`1` because that temporary copy omitted the repository `paeos/` package; the host runtime
check retains the pre-existing unresolved `mcp.server` import at
`runtime/transports/mcp/court_server.py:21`. This limitation is disclosed rather than
treated as a clean full-repository type result.

## Independent physical audit

The candidate-bound physical pair was mechanically adjudicated with
`report_status=PASS`, `a08_verdict=PASS`, and `qualified=True`:

- Audit ID: `m40-scarstore-a2e3d49-nvidia-003`
- Evidence bundle: `/private/tmp/paeos-scarstore-m40-l14-l17-bundle.json`
- Evidence bundle SHA-256: `a46d3ff05599bcd7526845c2040b2f7a97551482bcb20eb11aee8f44d210a135`
- Report: `/private/tmp/paeos-scarstore-m40-l14-l17-report.md`
- Report SHA-256: `c32cd6db9866c6362350d246eb7aa8ca3e2521ce665c63eae813be038dce562e`
- Receipt: `/private/tmp/paeos-scarstore-m40-l14-l17-receipt.json`
- Receipt file SHA-256: `c9d5558d461100eadc3528ec597cfcdbb22108a962bfff7ca6a515552df04d9e`
- Canonical receipt SHA-256: `9614961d706a4c8b492701ea7579673df1813f23586280c3752e238ad9157df5`
- Auditor: NVIDIA `meta/llama-3.2-11b-vision-instruct` (`llama`)
- Builder: `cline-pass` / `z-ai/glm-5.3-flash` (`glm`)
- A-08: `PASS` (`llama != glm`); provider attempts `1`; fallback `none`

The report independently notes that corrupted or missing SQLite databases are not handled
explicitly. That is a carried-forward integrity risk and is not silently marked resolved by
this seal. Earlier rejected audit artifacts remain preserved as raw evidence.

## Disposition and accounting

The Founder/Court disposition is **`COURT_SEALED`** for Milestone 40. The window accounting is
`Sealed: 1 | Remanded: 0 | Remediated: 0`; strict physical progress advances from
`27/48` to **`28/48 complete | 20 remaining`**. Milestone 41 `[I-CEREMONY-WALK]` is opened
in `reviews/tasks/PAEOS_MILESTONE_41_I_CEREMONY_WALK_INTAKE.md`.

The candidate manifest records an earlier prompt digest (`2c63d72f...`) while the current
prompt file has a different digest (`b7494f9e...`). The receipt binds the candidate, bundle,
review scope, and report bytes and remains qualified; the prompt-digest discrepancy is
preserved as metadata debt for follow-up rather than hidden. No retry, fallback, source edit,
promotion, merge, or protected-ref mutation was performed for this seal.
