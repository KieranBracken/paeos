# Pinned public policy input loader

Base: `8bc28d6feded86672d96816f845e178f99538a74`. Human instruction authorizes continuing signing/disclosure fixes; Root owns this offline candidate.

`disclosure_store.py` loads only a strict public Ed25519 document and a signed policy from descriptor-relative, no-follow, bounded regular-file reads. The independent public-key digest, key ID, canonical policy digest and explicit clock are required before use. It returns the existing immutable policy snapshot. It creates no keys, writes no files and grants no egress. Ancestor replacement stays bound to the already-open directory.

This new tooling format is not an enrollment record. Paths and pins must later come from protected supervisor configuration; a worker selecting them would establish no authority. Enrollment, protected currentness/revocation, rollback resistance, signing isolation, outbound composition and atomic attempt admission remain unimplemented. All existing production disclosure denials remain.

Verification: corrected baseline32failed/148passed; candidate180passed. An initial runner included loopback HTTP tests under complete network denial and recorded33failures plus32missing-module setup errors; those are preserved, then the runner was narrowed to the actual pure/parent dependencies. A lint autofix removed imported fixtures and produced32setup errors; explicit fixture imports corrected it. Final fixture-corrected run:180passed in0.56s. Symlinks, substituted paths/keys, duplicate/private document fields, malformed/oversized/nonregular inputs, signature tampering and expiry reject. No host identity/provider was used.

Full collection during concurrent model test preparation recorded8errors, including the then-missing new parser import; the combined integrated run records7existing collection errors, exit2. No full-suite acceptance. Shared static checks for all7source/test files pass and are stored in the adjacent model-identity package. Original test outputs/findings are preserved unchanged.

ALLOWED_NOW: sanitized recovery checkpoint; further scoped implementation within budget.
HELD: operational enrollment/egress/installation, final aggregate Security Review, qualification/admission and debt workers.
AUTHORITY_OR_IMPLEMENTATION_GAP: protected source of independent pins and policy currentness/revocation, actual frame/closure permission and durable attempt reservation. Founder signing key is not created; backup key remains separate. Chat1 remains D0258 integrator.
