# DEBT-0249 production run r-779c4b75: L07 quota exhaustion

Verified 2026-10-15T17:23:18.207372+00:00. Goal `g-59677d6a4ac1`. Original run and state roots are retained unchanged. This archive preserves the selected run evidence and 903-file source manifest/hash verification; it does not copy the 903 source files. `mcp-config.json` and `seal.key` are excluded.

## Outcome

The runtime receipt records exit code 2; stdout records `REMANDED` with `MITIGATION worker failed: FAILED`. L03 RE_DERIVE, L04 IDEATE, L05 RESEARCH, and L06 TRADEOFF have `COMPLETE` ledger receipts. L07 MITIGATION failed and has no runtime-stage receipt. The last available L07 ordinary review attempt (C) failed with Google HTTP 429 `QUOTA_EXHAUSTED`; attempts A and B failed first with HTTP 503 `PROVIDER_UNAVAILABLE`. No review produced a response.

Runtime empirical counts: **Sealed: 0 | Remanded: 1 | Remediated: 0.** Court: **not reached** (Court counts not applicable).

The runner PID recorded in `RUN.pid.json` is `5617`; `ps` at verification time returned no process row. This is local process evidence only. No provider-call liveness evidence was available.

`PRAGMA integrity_check` returned `ok`. All 14 ledger rows form a valid dense production chain ending at `86e590cc344950d0e99df4d0f68b626821283195e87f01c66d01aeb0365cedc4`; all 11 CAS names match their content hashes. The run receipt source-manifest hash is `11e1d761e8f8789f183020d3a172b6c5a2a1c28c225fcdd0930d2d6ebf8ac48e`; all 903 declared source hashes match the run source tree.
