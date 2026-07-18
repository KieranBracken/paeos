# Wave 0 — Spec Clarification Register (Candidate Incidents)

Per PAEOS-4 closing clause: any ambiguity discovered during implementation is a defect in
the spec and enters as `Goal(kind=incident)`. The Chief Implementation Architect resolved
the following ambiguities to unblock Wave 0. Each resolution is BINDING for Wave 0 workers
and MUST be converted to an incident goal at G-RUN so the amendments formalize them.

| ID | Ambiguity in PAEOS-4 | Binding resolution for Wave 0 |
|----|----------------------|-------------------------------|
| SC-01 | §2 `content: bytes` — JSON/JCS cannot carry raw bytes; encoding unpinned | Tagged union: `{"b64": "<base64url, unpadded>"}` inline or `{"ref": "sha256:<hex>"}` blob ref |
| SC-02 | Hash string representation unpinned | `"sha256:" + 64 lowercase hex chars` everywhere a HASH appears in JSON |
| SC-03 | §2.3/§12 signature algorithm unpinned (SHA-256/JCS/ULID pinned; signing not) | **Ed25519** over `SHA-256(JCS(evidence body sans signature))`; new pinned constant, requires kernel-spec amendment |
| SC-04 | Timestamp precision unpinned | RFC3339 UTC, exactly millisecond precision, `Z` suffix: `YYYY-MM-DDTHH:MM:SS.sssZ` |
| SC-05 | §2.5 `ClauseRef` format undefined | Parent `spec.delta` MUST tag clauses inline as `[c1]`, `[c2]`…; `serving_clause = "<parent-ulid>#c<n>"` |
| SC-06 | §2.7 `TriggerExpr` grammar undefined | JSON predicate AST: `{"all":[…]} {"any":[…]} {"not":…} {"eq":[path,val]} {"in":[path,[…]]} {"media_in_links":[mt]}`; paths restricted to `goal.kind, goal.classification.v, goal.classification.r, goal.workload, role.stance, role.domain` |
| SC-07 | §2.5 `PolicyDelta` structure undefined | `{target_policy_id, expected_prev: HASH, operation: create\|revise\|tombstone, body: <full replacement body>}` — full replacement, no patching (append-only friendly) |
| SC-08 | §2.7 `ExternalScar` referenced, never schema'd | Artifact with `media_type: application/x-paeos-scar+json`, body `{source, date, description, failure_mode, hazard_class: reversible\|irreversible}` |
| SC-09 | K10 `CAP` value (genesis parameter) unset | Provisional `CAP = 12000` tokens (13 constitution policies must fit); AMENDABLE |
| SC-10 | Fixture identity — ULIDs are time-random; fixtures need determinism | Pinned-ULID namespace for genesis/fixture objects (allocation table in COORDINATION.md); generated ULIDs only for post-genesis runtime objects |
| SC-11 | §7 (v,r) grid is 3×3 = 9 cells; PAEOS-3 mandates only 4 genesis protocols | 9→4 mapping table pinned in G-ROLES package |
| SC-12 | Golden-byte provenance — C1 goldens computed with which JCS? | Goldens MUST be produced with an independent published RFC 8785 implementation, never with I-CONST code (K3 decorrelation; a self-confirmed golden is theater) |

Disposition: at G-RUN, each row becomes one `Goal(kind=incident)` citing this file; the
resulting amendments either ratify the resolution into the kernel spec or replace it.
No Wave 0 worker may deviate from these resolutions or add new ones — a new ambiguity
found by a worker HALTS that task and is reported, not resolved locally.
