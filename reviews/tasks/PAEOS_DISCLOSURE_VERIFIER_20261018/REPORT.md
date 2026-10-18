# Dormant disclosure verifier checkpoint — 2026-10-18

Status: **P1_REMAINS**. A needed prerequisite is implemented; the transport privacy boundary is not fixed or activated.

## Scope and authority

The latest human request to implement the corrected P1–P9 plan authorizes this bounded offline bootstrap construction and synthetic verification. `SCOPE.json` pins the existing inactive disclosure design and the exact two-file source/test manifest. This does not claim PAEOS admission. Chat 1 remains the only DEBT-0258 integrator. No services, queues, host keys, policy authority or phase status were changed.

The existing September intake explicitly permits inactive construction without provisioning the Founder root. Its old P1/PRE-P2 sequencing labels are superseded by current SCO-036/DEBT-0250 dispositions. Those qualified baselines are not restarted here.

## Implemented

`paeos/model_router/disclosure_policy.py` implements immutable parsed policy, exact-route and artifact contracts, deterministic UTF-8 policy bytes, signed-envelope digests and domain-separated Ed25519 verification against independently supplied public verification material. It rejects duplicate/unknown fields, unsafe paths, invalid types/bounds/times/digests/signatures, SECRET or unsupported classes, weakened exclusions/independence safeguards, paid entitlement and known dynamic route selectors. Exact named `:free` variants remain representable. Provider identity comparison is not admission.

The module has no production consumer or host trust-loading path. A parsed manifest is explicitly not an egress permit. There is no signing, key generation, network, policy installation, or authority mutation in production code; test keys are ephemeral synthetic fixtures only.

## Verification

125 new policy cases plus existing privacy and bootstrap regression checks: **183 passed**. Tests check candidate import origin and independently serialize signing preimages. Red controls reproduced the missing implementation and then an overly strict free-variant rejection before correction. Ruff lint/format, compilation and whitespace checks passed.

The full suite was run once from a pinned recovery import environment: **22 collection errors**, exit 2. Exact modules and output hash are in `verification.json`. This is a failed full-suite run, not acceptance. The original review and pre-existing untracked Builder-gate test remain hash-identical.

## Recovery and runtime observations

The public parent checkpoint `6043fd77107dbba7e971fb328f38453144c6adab` was verified against the remote. Dirty-main inventory was captured locally with its digest in `preservation.json`; no dirty-main bytes were selected as implementation dependencies.

Encrypted off-device runtime recovery is not proven. No enrolled encryption recipient/custody evidence was found in the bounded configuration check; the available private backups are still dated October 1/2. Existing snapshot code has a raw SQLite-copy fallback and does not establish a cross-store consistency boundary. No snapshot was created or uploaded.

The live supervisor and launcher exist. Its queue has zero request files and two existing response receipts, so it is not empty. No quiescence, new worker start, or current qualification is inferred from those observations.

## Remaining dependent work and exact gates

- **ALLOWED_NOW — this bootstrap owner:** capture, review and push this source/evidence package; prepare the existing-spec dependent verification/bundle interfaces without live effects. Ordinary engineering returns to PAEOS when the executable boundary is qualified.
- **HELD — activation owner:** installation and the one-use qualification request require complete transport enforcement, current policy/revocation and attempt checks, clean exact-candidate review, enrolled Founder authority, exact approved route/entitlement and current host preflight.
- **AUTHORITY_OR_IMPLEMENTATION_GAP:** v1 permits only FREE, exact-artifact classes. It does not encode subscription-included Codex, standing authorized derivatives, or named limited-retention INTERNAL routes. Those selected choices need an explicit versioned policy amendment; silently accepting them in v1 would broaden authority. No Founder signing key may be generated or enrolled by this patch.
- **Recovery owner:** independently recoverable encryption recipient/custody and a coherent disabled restore remain required before unattended operation. Do not delete old backup trees: unique/unpushed state has not been ruled out.
- **Chat 1 / DEBT-0258:** held for lawful stage-qualified execution and a fresh admitted codec task. DEBT-0260 wakes after DEBT-0258 qualifies; DEBT-0117 wakes after its prerequisites. DEBT-0249 retains only already-admitted eligible scope. P3 stays held.

Review, Court observation, Court adjudication and qualification remain separate. No new Court event occurred in this slice; there is no whole-programme outcome count implied by this record.
