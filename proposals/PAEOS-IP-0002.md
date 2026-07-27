# PAEOS-IP-0002 — Define `EvidenceRef` (used but undefined in PAEOS-7.6)

Status: **RATIFIED BY FOUNDER** (2026-07-27) · Filed: 2026-07-27 · Channel: CER-2
Resolution: `EvidenceRef = Hash` added to `spec/PAEOS-7.6` §3; `CapabilityToken` type placed in
`kernel/types.py` (B0.4), broker behaviour stays B0.8. `TransitionRequest` completed in B0.4.
Source finding: Task **B0.4** implementation (core runtime types, PAEOS-7.6 §3–4). This
proposal is the halt-and-surface required by the constitutional preamble ("default to
derivation, not invention; if invention is genuinely required, HALT and produce an
Improvement Proposal") and CER-6. It recommends; it changes nothing until ratified.

## 1. Observation

`TransitionRequest` (PAEOS-7.6 §4) and `TaskResult` (§5) both carry a field
`evidence: EvidenceRef[]`. **`EvidenceRef` is never defined** — not in §3 (Core types), not
in §6 (Evidence contract), nor anywhere else in `spec/`. §6 defines `Evidence` (a struct
whose `hash` "IS its id"), but not `EvidenceRef`.

## 2. Current behaviour

Implementation of B0.4 stopped short of `TransitionRequest`. All other §3–4 types were
transcribed verbatim (`StageId`×21, `Role`, `WeightClass`, `Outcome`, `ArtifactRef`,
`Claim`, `ValidationClaim`, `TransitionResult`) and shipped. `TransitionRequest` cannot be
completed without deciding `EvidenceRef`'s shape, and the spec gives a **conflicting
precedent**: it defines `ArtifactRef = {hash: Hash, type: string}` as a *struct* rather than
a bare `Hash`, so `EvidenceRef` could plausibly be either a bare `Hash` or an analogous
struct. Choosing without ratification would be invention (CER-6 violation).

## 3. Proposed improvement

Add to **PAEOS-7.6 §3 (Core types)**:

```
EvidenceRef = Hash        // content address of an Evidence (§6); an Evidence's hash IS its id
```

i.e. define `EvidenceRef` as a **bare `Hash`**, not a struct. Then `TransitionRequest.evidence`
and `TaskResult.evidence` are `Hash[]`, resolvable against the CAS to full `Evidence` records.

Secondary (to let B0.4's follow-up complete `TransitionRequest` in one step): confirm that the
`TransitionRequest.authority: CapabilityToken` **type** (§7, fully specified) is defined in
`kernel/types.py` (B0.4), with the *capability broker behaviour* remaining B0.8. This is the
only acyclic placement — B0.8 depends on B0.4, and `TransitionRequest` (B0.4) needs the type.

## 4. Justification

`EvidenceRef = Hash` is the minimal definition consistent with everything 7.6 already says:
- §6 `Evidence.hash` "IS its id" — evidence is content-addressed, so a *reference* to one is
  its hash.
- Every other evidence reference in 7.6 is already a bare `Hash`: `Claim.evidence_refs: Hash[]`,
  `ValidationClaim.produced_against: Hash`, `Evidence.artifact_hash: Hash`.
- `ArtifactRef` is a struct because an artifact needs a `type` discriminator to be interpreted;
  an `EvidenceRef` needs none — the `kind` lives *inside* the `Evidence` (§6). So the ArtifactRef
  precedent does not carry over.

This serves K1 (evidence-gated) and SI-4 (artifact binding) without adding an abstraction:
the reference is the checksum, exactly as the CAS (B0.2) and ledger (B0.1) already work.

## 5. Risks

- If a future need arises to carry evidence *type* at the reference site (before resolving the
  full `Evidence`), a bare `Hash` would need widening to a struct — a breaking change. Mitigation:
  the `kind` is already inside `Evidence`; no gate rule in §6 inspects a ref without resolving it.
- Minimal risk of divergence if some other module independently assumes a struct — mitigated by
  pinning the definition in §3 now.

## 6. Backwards compatibility

No existing artifacts or stores reference `EvidenceRef` yet (B0.4 is the first type task, and
it deliberately omitted `TransitionRequest`). Zero migration. `Claim.evidence_refs` and all
other hash references are already `Hash`, so this *aligns* them under one name rather than
changing any.

## 7. Constitutional impact

Amends **PAEOS-7.6 §3** (a runtime interface-contract clarification: adds a missing type
alias; introduces no new mechanism, authority, or invariant). This is a **contract-doc
clarification**, akin to the SC-series and PAEOS-8.1 — not a kernel-surface change, so it does
**not** require the §14.5 kernel-amendment ceremony. Founder ratification per CER-5 suffices.

## 8. Recommendation

**Ratify** `EvidenceRef = Hash` (§3) and confirm the `CapabilityToken` type placement (§4.2).
On ratification, B0.4's follow-up adds `TransitionRequest` to `kernel/types.py` verbatim and
closes the task. **Smallest amendment:** one line in PAEOS-7.6 §3.
