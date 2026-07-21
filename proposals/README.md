# PAEOS Improvement Proposals

The formal channel for CER-2 (Constitutional Execution Rule 2, Engineering Lifecycle v1.1).
**No implementation may silently improve the constitution.** Every discovered improvement to
PAEOS — the kernel, lifecycle, authority, invariants, or any constitutional law — is written
here as a proposal, and left for the **founder** to ratify or reject.

## What a proposal is (and is not)

A proposal is a **recommendation**, not a change. In kernel terms it is a *draft
amendment-goal awaiting founder ratification* (K7 / §14.5). Writing a proposal changes
nothing; implementation continues regardless of whether it is later accepted. This is the
separation of powers (CER-5): **the runtime may recommend; it may never legislate.**

## Naming

`proposals/PAEOS-IP-NNNN.md`, zero-padded, monotonic (PAEOS-IP-0001, PAEOS-IP-0002, …).

## Required fields (every proposal)

1. **Observation** — what was noticed.
2. **Current behaviour** — what PAEOS does today.
3. **Proposed improvement** — the change, precisely.
4. **Justification** — why it is better (which invariant/axiom it serves).
5. **Risks** — what could go wrong.
6. **Backwards compatibility** — effect on existing artifacts/stores/conformance.
7. **Constitutional impact** — which documents/§§ it would amend; whether kernel-surface
   (needs §14.5 ceremony + founder) or operational.
8. **Recommendation** — ratify / reject / defer, with the smallest amendment.

## Lifecycle of a proposal

`drafted (here)` → routed to the founder decision queue (K7) → **founder ratifies** (becomes
a constitutional amendment, applied via the normal amendment lifecycle A-06) **or rejects**
(recorded, closed). A proposal MUST NOT be applied by any agent; only a founder-ratified
amendment may change constitutional law.

## Index

- `PAEOS-IP-0001.md` — Capability-based skill loading (CAP-1). Status: **awaiting founder
  ratification** (source finding: `reviews/7-skills-as-capabilities.md`; also excluded from
  PAEOS-4 v1.1 pending ratification per §16).
