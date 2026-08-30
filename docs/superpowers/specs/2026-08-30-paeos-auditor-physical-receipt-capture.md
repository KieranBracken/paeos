# PAEOS Task 9A — Physical Auditor Receipt Capture

**Status:** Founder-authorized isolated recovery task; no Gate A closure claim.

## Purpose

The existing model router records provider/model/family observations but does not produce an
invocation-bound artifact proving which physical model performed a Layer 14 audit. This task adds
the smallest provider-neutral receipt seam needed to unblock a future L14 review without exposing
credentials or changing worker admission, Court, or lifecycle authority.

## Boundary

- The router remains the sole policy authority for provider selection, health, quota, fallback, and
  retry behavior.
- The receipt capture layer consumes one completed `RouterResponse`; it does not select providers,
  retry, or fall back independently.
- A receipt is eligible only when the completed response proves exactly one provider attempt and no
  fallback candidate.
- Actual provider/model/family facts come from the completed transport response. Logical aliases,
  configured catalog family, chat labels, and manually supplied model names cannot qualify.
- Candidate SHA, evidence-bundle SHA, and a SHA-256 hash of the exact audit request are bound into
  the receipt. The request must explicitly name the candidate and evidence hash.
- Receipt payloads contain identifiers, hashes, counts, and disposition only. Prompt text,
  response text, credentials, headers, and raw provider bodies are never persisted.
- A-08 is re-evaluated from the physical builder and auditor families. Unknown or same-family
  results fail closed.
- Receipt persistence is create-only, canonical JSON, mode `0600`, and fsync-backed. Existing
  artifacts cannot be overwritten.

## Required receipt fields

The canonical schema `paeos.auditor-physical-receipt/1` contains:

- audit, session, candidate, evidence, and request-scope identities;
- builder provider/model/family;
- configured and actual auditor provider/model/family;
- one-attempt/fallback telemetry and a transport identity;
- non-secret request, response, and transcript hashes;
- captured timestamp, A-08 verdict, and the receipt hash.

## Explicit non-goals

This task does not run a live provider call, repair the repository-wide Ruff/Pyright baseline,
change Cline admission, close Gate A, execute Task 10, alter Gate B–G, or promote any branch.

## Unblock sequence after implementation

1. Run focused and mutation tests for the receipt contract.
2. Run one approved non-GLM audit through the PAEOS router and persist its machine-captured
   receipt against the exact Task 8 candidate.
3. Re-run the independent L13 matrix and reconcile static/environment findings.
4. Re-run L14. Only a physically proven non-GLM receipt plus a green/dispositioned L13 can release
   Task 10's three fresh Cline SDK probes.
