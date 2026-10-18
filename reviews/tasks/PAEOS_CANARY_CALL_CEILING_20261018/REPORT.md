# Pre-forward qualification call ceiling — 2026-10-18

The supervised Builder qualification path now constructs its broker with a one-call ceiling. The broker reserves that call under its existing lock before invoking upstream; concurrent attempts cannot pass the ceiling, and failed/ambiguous upstream calls still consume it. Normal tasks retain the existing 32-call ceiling. Caller request-body fields cannot increase the parent-selected limit.

This is an offline source checkpoint, not an installed fix or qualification. The existing stable authorization claim is still unbound to the disclosure grant. The full classification/frame/closure boundary and review findings remain open.

## Verification

196 combined focused tests passed, including 13 new ceiling/binding cases. Synthetic loopback tests demonstrate sequential rejection, simultaneous rejection while the first request is in flight, and consumption on upstream timeout. No real provider or host credentials were used. Lint, formatting, compilation and changed-source whitespace checks passed. The full suite was rerun once for this changed package and failed during collection with the same 22 errors.

The earlier fresh Security Review covers source commit `ab7c47d72b6c5b0dabbfce8cd5ad8a7d70b89a91`, not these later bytes. Its immutable report remains unchanged; a trailing blank-line whitespace warning in that captured report is recorded rather than silently rewriting it. No additional model review was requested.

ALLOWED_NOW: complete the next bounded offline disclosure/frame/claim package using the existing supervisor and trusted authority design. Owner: bootstrap coordinator. No new authority ledger is needed for the single supervised canary.

HELD: installation, qualification, Chat 1 dispatch and P3. Wake after trusted exact disclosure authorization, complete frame and readable-closure enforcement, receipt/provenance fixes and review of the final exact candidate, followed by fresh host/stage preflight.

AUTHORITY_OR_IMPLEMENTATION_GAP: a pure v1 FREE/exact-artifact policy is not a Codex subscription/derivative permit. Enrolled authority or a separately exact approved one-use canary packet is still required; the old Google L14 authorization and a client signature do not provide it. Independently recoverable encryption-key custody is also unproven. D0258 ownership/dependencies and all original findings remain intact.
