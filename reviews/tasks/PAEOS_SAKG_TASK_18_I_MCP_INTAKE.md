# SAKG Task 18 — `[I-MCP]` Canonical Intake

Source: item 17 of `ops/backlogs/sakg-1-intakes.json`.

**Objective:** Implement the read-only `sakg` MCP server surface. Expose
`tradeoff_precedents` only; deny unknown and mutating methods by default; structurally provide no
mutating method; tag every response with `provenance=sakg`, `trust=untrusted`, and
`tier ∈ {SUMMARY, INDEX}`.

## Deliverables and acceptance

- `sakg/mcp_server.py`
- `tests/mcp/test_sakg_server.py`
- `tests/mcp/test_sakg_server_readonly.py`
- `tests/mcp/test_sakg_server_tags_untrusted.py`
- Focused tests:
  - `uv run pytest tests/mcp/test_sakg_server.py -q`
  - `uv run pytest tests/mcp/test_sakg_server_readonly.py -q`
  - `uv run pytest tests/mcp/test_sakg_server_tags_untrusted.py -q`
  - `uv run pyright sakg/`

Execution is queued for a fresh isolated SoftLoop state root. No Task 18 implementation or seal is
claimed by this intake.
