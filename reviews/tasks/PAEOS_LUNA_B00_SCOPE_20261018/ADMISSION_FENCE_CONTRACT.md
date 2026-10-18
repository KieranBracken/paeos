# Admission and send-fence owner contract

Status: **proposed interface; no existing implementation or owner approval is evidenced**. This is a B00 design packet, not authority to create or alter canonical admission state.

## Gap and ownership

The current candidate has profile/probe predicates and a signed disclosure-policy parser, but no durable primitive that orders current admission/revocation against the exact network owner claiming a send. `RouterStateDB` is health and routing state; it is not the parent admission ledger. The owner must be the existing mission-admission authority that owns current admission and revocation state. Chat3 is the proposed routing destination because it owns authenticated mission-admission work; the completion overseer must confirm the actual authority owner before assigning implementation. A Manager read-only trace is corroboration, not owner approval.

Required operations, already proposed by the saved guide:

```text
acquire_send_lease(admission_ref, expected_epoch, logical_job_id, frame_digest)
finish_send_lease(lease_id, observed_outcome_ref)
```

These must be methods of the existing admission authority/store or an adapter that uses its actual canonical transaction and revocation state. Do not create a parallel authority database, infer authority from a worker-supplied profile, or change Chat1-owned kernel ledger/capability APIs.

## Semantics

`acquire_send_lease` is callable only by the trusted network-owning transport, after it has built the complete outbound frame and immediately before starting the one network attempt. In one durable transaction/linearization point, the authority must:

1. Resolve `admission_ref` to an enrolled, current, non-revoked admission from the canonical owner store and require exact `expected_epoch`.
2. Bind the current task/goal/run/session/stage/role, approved workspace/scope, destination/route and logical operation. `frame_digest` is computed over the actual bytes that the transport will send; a label or digest supplied only by the worker is not evidence.
3. Reject expired, stale, mismatched, duplicate, conflicting, revoked, already-claimed or unresolved logical operations. A caller must query an existing operation; it cannot receive a second send claim by changing a request UUID.
4. Persist one opaque `lease_id`, the complete binding and its state before control reaches code that can write to the socket. The caller cannot mint or extend a lease. The lease has an owner-defined bounded start window and no automatic reset/replay on expiry.

`finish_send_lease` is callable only by the same trusted transport boundary. It records an attributable outcome reference or the explicit `UNKNOWN` state, preserves immutable request identity, and rejects conflicting/duplicate settlement. It cannot turn a timeout, missing response or worker assertion into success.

Revocation and lease acquisition must serialize on the same canonical state/transaction:

| Winner at the canonical linearization point | Required behavior |
|---|---|
| Revocation commits first | Lease acquisition refuses; the transport performs zero socket writes. |
| Send claim commits first | Exactly that logical attempt remains claimed/in-flight. Revocation blocks later claims but cannot erase or replay this one; its eventual outcome is recorded or remains `UNKNOWN`. |

If the authority cannot make this ordering atomic, it must refuse the send. A local epoch copied with a restored database is not an independent freshness anchor. Reconciliation must use an independently current owner reference; expiry, restart or a new chat does not release an unresolved claim.

## Discriminating race and crash test

Use two real processes/connections against a temporary instance of the existing authority's storage and synthetic admissions; use a fake network sink that records only a counter and the synthetic frame digest. Do not use a provider, host key, real policy, runtime database or HOME state.

1. Race `revoke(admission_ref, expected_epoch)` against `acquire_send_lease(...)` from a barrier. Assert exactly one serialized outcome: revoke-first means acquisition is denied and sink writes are zero; claim-first means there is exactly one lease and at most one sink start, with revocation preventing all later claims.
2. Repeat with stale epoch, wrong task/run/session/workspace/route, changed frame digest, same logical ID with a new request UUID, revoked admission and unknown admission. Every case denies before sink use.
3. Kill the claimant before commit, after lease commit but before sink call, and after sink call but before `finish_send_lease`. Reopen through a fresh process. Pre-commit leaves no lease and no sink write; post-commit states remain non-replayable; post-sink/pre-finish is `UNKNOWN` and still non-replayable.
4. Attempt duplicate and conflicting `finish_send_lease` calls. Exact duplicate settlement is idempotent only if the canonical owner contract permits it; conflicting settlement fails closed. Confirm the authority has one source of truth across both connections.

The test is evidence for this interface only. It cannot approve a new authority owner, production policy, provider route, installation or qualification. The current B01 RouterStateDB tests remain synthetic; B01 cannot claim an atomic admission/send fence until the actual owner contract and source-bound implementation pass these controls.

## Required owner response before B01 source writes

Return the exact canonical source/storage owner, the existing revoke operation, the send linearization point, the restart/UNKNOWN rule, and whether this interface fits its current authority. If the primitive is absent, the authority owner must approve a bounded implementation scope within its own subsystem before anyone writes it. Root keeps B01 source changes held until that response is received and hash-bound. Chat1 remains sole owner of DEBT-0258 integration.
