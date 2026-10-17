# Independent Court Audit: Concept OS Task 07 — Structurally Read-Only MCP Query Surface

**Date:** 2026-09-05  
**Auditor:** Google Gemini (`gemini-3.7-flash` / Antigravity Forensic Hypervisor)  
**Builder:** OpenAI Codex (`gpt-5.6-luna` @ Extra High `xhigh` reasoning effort)  
**Task ID:** `TASK-07-READ-ONLY-MCP`  
**Candidate Commit:** `66d502f` (branch `codex/concept-os-task-07` in `/private/tmp/concept-os-candidate`)  
**Canonical Merge Commit:** `305dad1`  
**Status:** **SEALED — COURT DISPOSITION: PASS**

---

## 1. Executive Summary & Epistemic Demarcation

Pursuant to the **Strict Auditor Precision & Remand Integrity Rule** (AGENTS.md):
> *"Remands are healthy, essential back-pressure mechanisms that protect constitutional invariants. NEVER optimize for 'zero remands' or use 'zero-remand execution' as an acceptance criterion — doing so incentivizes bypassing safety machinery. Always compute exact empirical statistics and validate that Court remands correctly reject invalid or non-probative artifacts."*

Task 07 implements the structurally read-only MCP query surface for Concept OS in `concept/mcp_server.py` and comprehensive test coverage under `tests/mcp/` according to CEO-1 §11.1 (`spec/CONCEPT_OS_1_ARCHITECTURE.md`).

### Autonomous Review & Remediation Cycle:
During development, the Builder deployed an autonomous peer-review subagent (`01a06f41-2e14-71a0-b751-e7993a5ca657` / Halley) which identified three Important security vulnerabilities in the initial candidate implementation:
1. Client-supplied traversal and search budgets had no server-side finite upper bounds.
2. Malformed nested search budgets raised unhandled `AttributeError` / `ToolError` instead of returning the mandatory exploratory envelope.
3. `disclosure_policy` was forwarded directly from user input, which could allow widening beyond same-namespace isolation.

The Builder remediated all three issues, added test coverage in `tests/mcp/test_concept_server_readonly.py`, `tests/mcp/test_concept_server_graceful.py`, and `tests/mcp/test_concept_server_tools.py`, verified with a second independent subagent (`Curie`), and produced commit `66d502f`.

### Key Invariants Verified:
1. **Exactly Five Read-Only Tools:** Exposes `concept_get`, `concept_search`, `concept_neighborhood`, `concept_path`, and `concept_hypothesis_get`. The tool allow-list is strictly validated on server initialization; any extra or forbidden tool name triggers an immediate initialization panic.
2. **Strict SQLite Read-Only Security:**
   - Opens connection strictly via `file:...uri?mode=ro`.
   - Executes and verifies `PRAGMA query_only = ON`.
   - Zero writer connections, zero outbox emitters, zero mutation capabilities.
   - All mutation tool names (`create`, `append`, `update`, `delete`, `promote`, `validate`, `execute`, `export`) are strictly forbidden and rejected.
3. **Mandatory Advisory Envelope Invariant:**
   Every tool response is wrapped in the standard exploratory candidate envelope:
   ```json
   {
     "authority": "exploratory",
     "trust": "untrusted_candidate",
     "graph_snapshot_hash": "<sha256>",
     "query_hash": "<sha256-or-null>",
     "truncated": false,
     "omitted": 0,
     "results": [...]
   }
   ```
4. **Atomically Pinned Read Transactions:**
   Logical query execution and `graph_snapshot_hash` computation are pinned inside a single read transaction scope (`read_scope`), ensuring that the advertised snapshot hash and retrieved data are strictly co-temporal.
5. **Fail-Closed Budget & Namespace Isolation:**
   Finite upper bounds are enforced for all budgets (`_MAX_TRAVERSAL_BUDGETS`, `_MAX_SEARCH_BUDGETS`). Cross-namespace expansion is strictly disallowed via `same_namespace` policy clamping.

The independent Court conducted a strictly **read-only** audit of candidate commit `66d502f` with zero auditor-side code mutations.

---

## 2. Invariant & Non-Vacuity Verification Matrix

| Invariant / Check | Specification Requirement | Verification Method | Verdict |
|---|---|---|---|
| **A-08 Heterogeneous Audit** | Builder family != Auditor family | Builder: OpenAI Codex Luna (`gpt-5.6-luna`); Auditor: Google Gemini (`gemini-3.7-flash`) | **PASS** |
| **CANARY-0002 Non-Vacuity** | No mock tests, real SQLite store, traversal, and MCP server | 33 MCP tests across 5 suites probe real SQLite connections, read-only pragmas, transaction pinning, envelope contracts, and tool dispatch | **PASS** |
| **CEO-1 §11.1 Five Tools Only** | Exactly 5 read-only tools; mutation tools forbidden | `tests/mcp/test_concept_server.py`, `tests/mcp/test_concept_server_readonly.py` (pass) | **PASS** |
| **SQLite mode=ro & query_only** | Connection is read-only; writes throw `StoreUnavailable` / `OperationalError` | `tests/mcp/test_concept_server_readonly.py` (pass) | **PASS** |
| **Mandatory Envelope** | All tool outputs contain authority="exploratory", trust="untrusted_candidate", hashes | `tests/mcp/test_concept_server_tools.py`, `tests/mcp/test_concept_server_graceful.py` (pass) | **PASS** |
| **Read Transaction Pinning** | Data query and snapshot hash computed in single transaction | `tests/mcp/test_concept_server_readonly.py::test_data_and_snapshot_hash_are_read_in_one_transaction` (pass) | **PASS** |
| **Budget Upper Bounds** | Traversal and search budgets bounded by server ceilings | `tests/mcp/test_concept_server_graceful.py::test_exceeding_budget_ceilings_returns_budget_exceeded_envelope` (pass) | **PASS** |
| **Graceful Degradation** | Missing database, uninitialized schema, missing nodes return typed empty/error envelopes | `tests/mcp/test_concept_server_graceful.py` (pass) | **PASS** |
| **Full Concept & MCP Suite** | All concept and MCP tests pass | `uv run pytest tests/concept/ tests/mcp/ -v` (219/219 pass in 1.69s) | **PASS** |
| **Linter (Ruff)** | Clean imports and code style | `uv run ruff check concept/ tests/mcp/` (0 errors) | **PASS** |
| **Type Checker (Pyright)** | Strict type correctness | `uv run pyright concept/ tests/mcp/` (0 errors, 0 warnings) | **PASS** |
| **AST Linter** | No forbidden AST exception swallowing | `runtime.ast_linter.check_ast` clean across 18 concept & mcp files | **PASS** |

---

## 3. Physical Reproduction & Evidence Summary

```text
============================= test session starts ==============================
platform darwin -- Python 3.13.5, pytest-9.1.1, pluggy-1.6.0
rootdir: /Users/bob/GitHub/paeos
collected 219 items
219 passed in 1.69s
All checks passed!
0 errors, 0 warnings, 0 informations
AST check passed across 18 files (0 violations)
```

---

## 4. Court Disposition & Accounting

- **Task 07 Disposition:** **SEALED — COURT DISPOSITION: PASS**
- **Canonical Accounting:**
  - Cumulative Programme: `Sealed: 7` (Task 01, Task 02, Task 03, Task 04, Task 05, Task 06, Task 07)
  - `Verified_Pending_Revalidation: 0`
  - `Remanded: 0`
  - `Remediated: 4`
- **Next DAG Milestone:** Wave 8 `TASK-08-INTEGRATION-SPIKE` (End-to-end integration spike, benchmark suite, and baseline verification for Concept OS Milestone 1).
