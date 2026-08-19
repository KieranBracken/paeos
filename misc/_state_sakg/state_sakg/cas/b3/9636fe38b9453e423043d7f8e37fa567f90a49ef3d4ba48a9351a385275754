# CER-1 Architectural Review: is `FileCourtEvidencePool` the primitive, and MCP merely a transport?

**Date**: 2026-07-31 · **Trigger**: founder CER-1 review before R5.1 · **Verdict**: invariant already
held in dependency direction; **one gap closed** (the abstraction was anonymous — now named).

## The question

Is `FileCourtEvidencePool` the *true architectural primitive* and the MCP `CourtServer` merely one
*transport*? If so, define the stable interface both satisfy; the runtime must depend only on the
evidence-source abstraction, never on MCP. Prove it, or propose the minimum amendment.

## Findings (proven empirically)

1. **`FileCourtEvidencePool` is NOT the primitive.** The primitive is the **abstraction**
   `run_id → tuple[Evidence, …]`. `FileCourtEvidencePool` (durable/cross-process), `CourtEvidencePool`
   (in-memory), and a future MCP-backed source are all *transports/implementations* of it. Elevating
   any one to "the primitive" would be the category error.

2. **The runtime already depends only on the abstraction, never on MCP.** Proven:
   - `grep -rn "import mcp" runtime/` → **zero** — no runtime module imports MCP.
   - `SoftLoop.run` took `evidence_source(run_id) → tuple[Evidence, …]` and called it — a bare
     structural dependency, no pool class, no MCP.
   - Both pools already expose the identical shape (`evidence_for(run_id)`).
   - `mcp/servers.py` does not reference the pools — MCP is a *separate, unconnected* transport.

   So the dependency direction the founder wants was **already correct**: runtime ⟶ abstraction;
   MCP would sit *behind* it, never the reverse.

3. **The gap: the abstraction was anonymous.** It was an inline `Callable[[str], tuple[Evidence,…]]`
   — a real structural dependency, but with **no named, declared interface**. So "the stable
   interface both satisfy" was implicit and unenforced; a future MCP source's conformance was a
   convention, not a checked contract.

## Minimum amendment (implemented)

Name the abstraction and type the runtime against it — nothing more:

- **`EvidenceSource`** (a `typing.Protocol` in `runtime/orchestrator`): the single method
  `evidence_for(run_id: str) -> tuple[Evidence, ...]`. This is the **read** side the runtime needs.
- `SoftLoop.run(evidence_source: EvidenceSource | None)` now types against the Protocol and calls
  `evidence_source.evidence_for(run_id)`.
- `CourtEvidencePool` and `FileCourtEvidencePool` satisfy `EvidenceSource` **structurally** — verified
  by pyright (0 errors). A future MCP-backed source implements the same method; the runtime imports it
  through the Protocol, never `mcp`.

The **write** side (`submit(run_id, evidence)`) is deliberately *not* in `EvidenceSource` — the
runtime only reads; submission belongs to the transport/submitter. Keeping the read interface minimal
is what lets any transport (file, in-memory, MCP) back it.

## Enforcement

- `pyright` (strict on `kernel/`, checked everywhere) verifies both pools satisfy `EvidenceSource`.
- A standing check re-proves the boundary: `grep -rn "import mcp" runtime/` must stay empty — the
  runtime may never import MCP. (Candidate CI assertion for R5.1.)

## Consequence for R5.1

R5.1 is now unambiguous and small in surface: build an **MCP-backed `EvidenceSource`** (a thin
`CourtServer` that writes submissions into a `FileCourtEvidencePool`, whose `evidence_for` the loop
already consumes). The runtime does not change; only a new transport is added behind `EvidenceSource`.
This is the proof that the architecture is right: adding MCP touches **no runtime code**.
