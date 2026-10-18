# Explicit runtime selection recovery checkpoint

Base: `aad38df810538874d6a749779705e1290fb5c0fb`.

`build_scheduler` now rejects missing, unknown and unsupported standalone `bound-cline` selection before state creation, signing-key access or transport composition. The CLI requires an explicit selector and rejects missing/invalid selectors before reading the backlog. Existing explicitly selected routes remain selectable, subject to their separate denials and qualifications. No route was enabled or invoked. Claude is no longer the implicit fallback. This does not remove the separately configured Claude adapter.

Frozen source/test scope: `ops/autonomous_run.py` and `tests/ops/test_explicit_runtime_selection.py`. Bounded offline repair under the human-approved corrected plan, resumed on 18 October. No PAEOS admission is claimed.

Verification:
- Baseline: 11 failed, 17 passed. Failures demonstrate state/key access before rejection and backlog reads before missing/invalid selector rejection.
- Final: 28 passed in 1.31s. Includes 18 selection cases and 10 actual offline scheduler/resource/readiness regressions.
- Candidate imports fenced to this recovery tree; network denied, host home contents denied except interpreter/dependencies, writes restricted to temporary scratch. Test identities are synthetic only.
- Test lint/format, changed validator formatting, in-memory compilation and git diff checks pass. Full-file import sorting I001 and formatting debt reproduce on the unchanged base and are not claimed clean. Raw pytest failure output retains its original trailing whitespace; that evidence is excluded from the source whitespace acceptance check.
- One integrated full-suite invocation through uv with offline/no-sync and isolated candidate imports: exit2, seven collection errors in3.47s. Exact failures preserved in full-suite.stdout.txt. Earlier22 collection errors remain historical evidence, not a current pass.
- No provider call, host-key read, installation, Builder qualification, formal review, Court action or debt integration.

ALLOWED_NOW: Root checkpoints this tested offline package; source-bound receipt-producer/trust-root investigation may continue. The completion overseer coordinates the next bounded eligible package.
HELD: positive egress, activation, qualification, Chat1 DEBT-0258 admission and dependent debts/P3; wake requires boundary repairs, exact candidate review, applicable trusted authority, valid qualification and fresh admission.
AUTHORITY_OR_IMPLEMENTATION_GAP: trusted positive disclosure/enrollment, authenticated response production, attributable observed model evidence and task admission remain unresolved. USB key custody is separate and is not authority evidence.
