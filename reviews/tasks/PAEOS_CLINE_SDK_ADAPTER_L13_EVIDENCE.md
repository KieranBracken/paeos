# PAEOS Cline SDK Admission Adapter — Independent L13 Reproduction

**Date:** 2026-08-30
**Candidate:** `adf76c61972554f71f2c863b3113f07d19dd1a52` (`adf76c6`)
**Checkout:** `/private/tmp/paeos-cline-sdk-l13-adf76c6` (detached, clean)
**Role:** independent verifier; no builder prose consumed as evidence

## Reproduction boundary

The candidate was checked from a fresh detached worktree at the exact Task 8 commit. The checkout
reported no uncommitted paths and no diff. No credentials, provider calls, profile contents, or
live admission probes were used.

## Exact empirical results

| Command / scope | Exit | Result | Raw stdout SHA-256 | Raw stderr SHA-256 |
|---|---:|---|---|---|
| `pytest --collect-only -q` | 0 | **817 collected** | `c74c4f3954132244d40cff83f2d8c598bd4ebc6bcfdd055e07b11ab670291a25` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `pytest tests/runtime/test_cline_sdk_adversarial.py tests/runtime/test_cline_sdk_mutations.py` | 0 | **46 passed; 0 failed; 0 skipped; 0 xfailed; 0 xpassed** | `759f08c05b885e3fde867f06a176c1be071793ca607c6c4b2c64ae8269cabbff` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `pytest` in restricted sandbox | 1 | **813 passed, 4 errors**; all 4 are loopback bind `PermissionError` in `tests/model_router/test_gateway_server.py` | `8faf3361db96b4d2d14f82c1302078bde5aee5501e6edea788893488eb3f2e0b` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `pytest tests/model_router/test_gateway_server.py` with loopback permission | 0 | **4 passed; 0 failed** | `64881b85155f91ae975308351fc3f0654cccab5567c2d0ada11cc50002456d26` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| targeted Ruff (Task 7–8 files) | 0 | **All checks passed** | `82b3e6a6c090a57601d22943bd23fca9218d1031dbe5a7b754092f9a156b4f18` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| targeted Pyright (Task 8 files) | 0 | **0 errors, 0 warnings, 0 informations** | `6d88a1b220adb7a3d62092b6e38431f0b3fe8babe9864fab90e5849766260332` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| repository-wide `ruff check .` | 1 | **658 findings** | `ed993c221589aa233390a36aec603c1ad26097c772f83ed8142dc2c9e5f188e4` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| repository-wide `pyright` | 1 | **74 errors, 0 warnings, 0 informations** | `b9bba26616af38a3c5997ceb3a035f666d55d711408cc1872ee911e7e4c037a4` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `node --check runtime/integrations/cline_sdk_host.mjs` | 0 | syntax valid | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |

The restricted full run has no skips, xfails, or xpasses. Its four errors are environmental socket
denials, not assertion failures; the same four tests pass when loopback binding is explicitly
allowed. This does not erase the restricted-run errors.

## Static-check boundary

The required repository-wide commands were also run independently. `ruff check .` exited nonzero
with **658 reported findings** and `pyright` exited nonzero with **74 diagnostics** across the
existing repository. The Task 7–8 files are clean under targeted checks above. These unrelated
baseline findings were not mass-formatted or opportunistically repaired during this recovery
checkpoint.

## L13 disposition

**CONDITIONAL / NOT ELIGIBLE FOR GATE A CLOSURE.** The new adversarial and mutation evidence is
non-vacuous and independently reproducible, but the repository-wide static gate is not green and
the restricted full suite contains four environment errors. No admission, Court seal, debt
repayment, or lifecycle advancement is claimed.

Worker accounting remains **Admitted: 0 | Rejected: 1 | Remediated: 0**. Court accounting remains
**Sealed: 0 | Remanded: 0 | Remediated: 0**.
