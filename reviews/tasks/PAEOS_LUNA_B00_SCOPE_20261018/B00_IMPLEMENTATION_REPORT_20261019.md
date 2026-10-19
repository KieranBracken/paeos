# B00 provider-free implementation candidate

**Status:** `SYNTHETIC_ONLY_IMPLEMENTATION_CANDIDATE`

**Base:** `b9cd1aa5c88ce29ffadcfb5f4ab5984c569b2276`

**Branch:** `codex/p1-bound-source-recovery-20261018`

## What changed

The candidate adds a compare-and-append operation to the canonical in-memory and SQLite ledger stores. SQLite checks the expected head and inserts the next hash-chain row inside one `BEGIN IMMEDIATE` transaction. Regular appends retry stale cross-connection composition; conditional authorization appends fail and revalidate after any head change.

`runtime/autonomy/admission_send_fence.py` adds provider-free mechanics for resolving current synthetic admission and policy events, checking expiry and epoch/revision, binding task/run/stage/role/workspace/route and exact frame digests, and committing one durable logical-job claim before the sink. A claim is not replayed under another request ID. A timeout records `UNKNOWN`; an unsettled claim survives restart and cannot be released by a new fence instance.

`HostCodexWorkerTransport` accepts the fence only through explicit constructor injection and checks it before reading session data, signing, or writing the local supervisor queue. Its production composition still supplies no fence or trusted admission/policy verifier, so the transport remains default-deny. The synthetic verifier and fake queue/sink tests do not establish production authority or provider egress.

The existing Hypothesis ledger tamper test now writes generated synthetic events in the `TEST` domain, so the production contamination guard cannot make that test fail nondeterministically on generated `MOCK_ID` payloads.

## Verification

- Focused ledger, fence, and trusted-transport suite: **95 passed**.
- Broader runnable suite: **2,155 passed** after excluding eight baseline test files with absent imported modules.
- Unfiltered `uv run pytest`: collection stops with seven `ModuleNotFoundError` errors for absent `contracts.adapters` and `runtime.transport` modules.
- The broader attempt excluding those seven files completed with 2,164 passed and 16 failures because `tests/runtime/test_p1_production_lifecycle.py` imports the absent `tests.runtime.test_luna_adversary_subsumption` helper. The helper is absent from the base commit; excluding that one blocked test file produced the 2,155 passing result above.
- Ruff lint, Ruff format check, in-memory compilation of all eight changed Python files, and `git diff --check`: passed.
- Scoped high-confidence secret-pattern scan: no matches. `gitleaks`, `detect-secrets`, and `trufflehog` executables were unavailable.
- The original Security Review file remains byte-identical to SHA-256 `9fc4cfd01d4727e307949f10dfb2650e3e644af35db64a666727a3f0e6d93afa`.

## Current disposition

**ALLOWED_NOW:** preserve this provider-free candidate and continue source-bound owner reconciliation.

**HELD:** production fence composition, real admission or policy issuance, positive provider egress, PAEOS worker start, installation, qualification, Court action, debt activation, and P3.

**AUTHORITY_OR_IMPLEMENTATION_GAP:** no production admission/currentness and disclosure-policy producer/verifier is integrated with the actual outbound owner, and no production composition injects the fence. The saved reviewer-lane record still requires a separately authorized independent non-GPT review channel; no route satisfying the free, privacy-eligible, different-family constraints was demonstrated. No review was submitted or accepted.

**Exact Founder-only eventual effect:** private Founder policy-key creation/enrollment and signed-policy activation belong to the human ceremony after a complete tested and reviewed package (`docs/superpowers/plans/2026-10-18-luna-guide/bootstrap.md:101,109-118`; `docs/superpowers/plans/2026-10-18-luna-guide/operations.md:91-93`). The existing owner-scope packet, `FOUNDER_OWNER_SCOPE_DECISION_20261019.md`, is still marked `FOUNDER_DECISION_REQUIRED` and is a proposal, not an appointment or source approval. No key, enrollment, signature, installation, or activation occurred.

No PAEOS run/task/stage/worker receipt, provider call, admission, review acceptance, qualification, Court disposition, or debt lifecycle event is claimed. The original review findings and prior scope manifests remain unchanged. Exact preimages, postimages, commands, and dispositions are in `B00_IMPLEMENTATION_SCOPE_20261019.json`, `B00_IMPLEMENTATION_LOG_SCOPE_20261019.json`, and `B00_IMPLEMENTATION_EVIDENCE_20261019.json`.
