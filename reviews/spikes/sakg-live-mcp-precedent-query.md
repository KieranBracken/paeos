# SAKG Live MCP Precedent Query Validation Spike

- **Task:** SAKG-2 Task 26 `[I-LIVE-MCP-SPIKE]`
- **Date:** 2026-09-04
- **Scope:** SAEOS-1 §3.2, §3.3, and §5.3
- **Local spike result:** PASS on the deterministic candidate `sakg.db` fixture
- **Court disposition:** Not claimed; this report is empirical implementation evidence only

## Finding

The in-process MCP surface now returns outcome-joined precedents from a live SQLite
`GraphStore` using the canonical relations emitted by Tasks 22 and 25. Each result contains a
three-step `why` traversal from the matched TradeOff axes through the resolved Decision to its
verified Outcome. The same call remains read-only, advisory, deterministic, and bounded by
`max_nodes` and `max_tokens`.

The pre-reconciliation production database exposed the integration gap directly: it contained
631 nodes, including 48 historical TradeOffs and 48 Decisions, but no Outcome nodes; none of the
historical TradeOffs carried query axes. Its Task 22 links used `tradeoff/resolves`, while the
older query recognizer accepted only `resolves_to`; Task 25 emitted `causal/outcome` edges and
candidate Outcome envelopes with `facets.state.value=VERIFIED`, while the recognizer accepted
only `realized_as` edges and `status=realized` nodes. A live MCP probe consequently returned an
empty result without crashing.

## Architectural reconciliation

The repaired query boundary preserves each producer's canonical representation:

- SAEOS-1 §3.2 / Task 22 `tradeoff/resolves` is accepted alongside the legacy
  `resolves_to` and `resolves_to_decision` spellings.
- Task 25 `causal/outcome` is accepted alongside `realized_as` spellings. The canonical
  `outcome` spelling is accepted only on the causal edge family.
- An Outcome is complete when it is either `status=realized`, or when it is an append-only
  `status=candidate` snapshot carrying `facets.state.value=VERIFIED`. OBSERVED, FALSIFIED,
  malformed, and unverified candidate snapshots remain excluded.
- Axis extraction walks the known `payload`, `facets`, `coordinates`, `data`, `properties`, and
  `tradeoff` containers. This covers deserialized SQLite payload axes, nested
  `facets.tradeoff.dimensions`, and the earlier direct `axes` forms without scanning unrelated
  graph fields.

Empty subjects/axis lists and well-formed but unresolvable axes return an empty advisory result.
Malformed non-empty axis requests still fail closed through `TradeoffPrecedentError`.

## Live execution

The automated probe constructs a temporary candidate `sakg.db` exclusively through the public
append-only APIs. It appends three canonical TradeOff nodes with the dimensions `latency`,
`reliability`, and `maintainability`; three Decisions joined by `tradeoff/resolves`; and three
VERIFIED candidate Outcomes emitted by `OutcomeObserver` and joined by `causal/outcome`. The
resulting live graph contains 9 nodes and 6 edges. No mock, raw SQL insertion, network model, or
mutation of the repository's source database is used.

The executed MCP parameters were:

```json
{
  "subject": "PAEOS runtime architecture",
  "axes": ["latency", "reliability"],
  "max_nodes": 10,
  "max_tokens": 4000
}
```

The query returned three precedents. The first was:

```json
{
  "decision_id": "sakg://paeos-history/Decision/00000000000000000000000001",
  "score": 0.9,
  "why": [
    "TradeOff axes matched: latency,reliability",
    "TradeOff resolves_to Decision",
    "Decision realized_as Outcome"
  ],
  "outcome": {
    "id": "sakg://paeos-history/Outcome/6436C2WKG9ASA3D2FVN11VNX0X",
    "status": "candidate",
    "state": "VERIFIED",
    "summary": "Historical decision 1 remained reliable under live verification."
  }
}
```

This is an outcome join, not an inferred shortcut: the result requires an explicit matching
TradeOff, an explicit resolving edge to the returned Decision, an explicit causal edge from that
Decision to the returned Outcome, and a realized or VERIFIED completion marker.

## Budgets and latency

The MCP server estimates tokens as `ceil(len(canonical_result_json) / 4)` and drops complete
results rather than truncating structures. The empirical three-result response consumed an
estimated 297 result tokens. With `max_nodes=1`, one result was retained and two were reported as
omitted. With `max_tokens=99`, one 99-token result was retained, two were omitted, and
`truncated=true`; retained consumption never exceeded the caller's ceiling.

After one warm-up call, 50 in-process MCP calls produced these wall-clock measurements:

- minimum: 0.282 ms
- median: 0.305 ms
- p95: 0.420 ms
- maximum: 0.447 ms

The maximum observed latency was below the Task 26 threshold of 100 ms. This measures local MCP
dispatch and query execution after the server has snapshotted the nine-node fixture; it does not
claim network transport latency.

## Compliance evidence

- **SAEOS-1 §3.3 — hard budget:** complete records are retained only while both token and node
  ceilings permit them; overflow is counted in `omitted` and signalled by `truncated`.
- **SAEOS-1 §3.3 — mandatory traversal path:** every returned item has all three non-empty `why`
  steps covering axis match, TradeOff-to-Decision resolution, and Decision-to-Outcome
  realization.
- **SAEOS-1 §5.3 — read-only MCP:** `build_sakg_mcp_server` snapshots the graph and exposes only
  `tradeoff_precedents`; the probe performs no MCP mutation or promotion.
- **SAEOS-1 §5.3 — graceful degradation:** empty and unreachable queries return `results=[]`
  without an exception or process failure.

Focused RED evidence before the repair was `4 failed`: live result/path, node/token budgets,
empty-query degradation, and latency-with-result all failed against the old boundary. After the
repair and explicit payload-axis coverage was added,
`uv run pytest tests/mcp/test_live_mcp_query.py -v` returned `7 passed`.

Final local verification after the report was authored:

- `uv run pytest tests/mcp/ tests/sakg/ tests/kae/ -v` — 144 passed in 1.66 seconds, 0 failed,
  0 warnings.
- `uv run ruff check tests/mcp/ sakg/ tests/sakg/` — all checks passed.
- `uv run pyright tests/mcp/ sakg/ tests/sakg/` — 0 errors, 0 warnings, 0 informations.
- `runtime.ast_linter.check_ast()` over the three changed Python files — 0 violations.
