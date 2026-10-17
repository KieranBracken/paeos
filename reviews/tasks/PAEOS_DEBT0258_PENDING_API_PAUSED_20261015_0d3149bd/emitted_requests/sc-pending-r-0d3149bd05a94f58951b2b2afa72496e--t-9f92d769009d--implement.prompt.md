# PAEOS Task: sc-pending-g-1d1ded1c7a684f09812a06bbdcf93930 (sc-pending-r-0d3149bd05a94f58951b2b2afa72496e)
**Stage:** IMPLEMENT | **Role:** BUILDER
**Bound worker session:** codex-agent:/root/pending_builder

## Objective
SOURCE_CONSTRUCTION_ONLY. This is a separate manual bootstrap source package. It is not a production mission, full lifecycle, SEALED result, qualification, or integration. Only the two existing captured files ('runtime/scope_supersession.py', 'tests/runtime/test_scope_supersession.py') are mutable. Preserve their exact frozen preimages. Read .source_construction_scope.json for the full reviewed requirements. Add only the validated read-only pending-state/contract-denial API. Never consume a new supersession, activate or qualify a contract, or issue authority. No pending record means only not invalidated here, never authenticated currentness. Dependencies are read-only. Do not read the harness key or state database, touch canonical source, spawn workers, or self-authorize.
Authority reference: Coordinator instruction for distinct successor SOURCE_CONSTRUCTION_ONLY task after original source construction terminal completion; same two captured component paths, existing preimages. No retry or relabel of previous consumed operation.
Extend only the captured scope_supersession source and its focused tests with a validated read-only pending-state/contract-denial API for later real controller/Court consumers. Verify ledger/CAS receipt state; a valid pending consumption must deny both predecessor and unactivated successor; reject malformed or ambiguous state. Do not consume new supersession, activate, qualify, or issue authority. With no pending record, report only not invalidated here, never authenticated currentness. Preserve existing consume behavior and all existing focused tests. Do not import ORCA/contracts or model-router modules. Root will freeze complete API/error/receipt validation requirements before dispatch.
You may run the fixed local test helper before submission to repair ordinary test failures inside scope. Court submission is one-use. Physical evidence: after implementation and local tests, invoke the configured Court boundary adapter:
/Users/bob/GitHub/paeos/.venv/bin/python -B /private/tmp/paeos-pending-contract-api.nfIb3R/harness.py court-submit --state /private/tmp/paeos-pending-contract-api.nfIb3R/state --workspace <EXACT_WORKSPACE_BELOW>
This calls the real Court MCP submit_evidence tool for frozen commands and derives evidence physically; do not write the pool yourself. If it fails, stop and report to the coordinator without publishing completion.
On success invoke:
/Users/bob/GitHub/paeos/.venv/bin/python -B /private/tmp/paeos-pending-contract-api.nfIb3R/harness.py complete --state /private/tmp/paeos-pending-contract-api.nfIb3R/state --workspace <EXACT_WORKSPACE_BELOW>
Only this completion adapter publishes the response after complete source/CAS and dependency-integrity checks. Do not publish a response manually. Heterogeneous review is pending; no provider attempts or resets are allowed. Independent verification and heterogeneous review remain mandatory before integration; this package authorizes no integration. Deadline is fixed at 1800 seconds.


## Strict Workspace Binding
Execute all work inside the isolated sandboxed workspace:
`/private/tmp/paeos-pending-contract-api.nfIb3R/state/workspaces/paeos-t-9f92d769009d-bridge-a5vzsgnj`

Do not modify repository files outside the sandbox. The capability is already bound to this
worker session. Do not spawn subagents, invoke skills, change terminals, ratify, promote to
main/trunk, or claim lifecycle advancement.

## Package Prompt
```
SOURCE_CONSTRUCTION_ONLY. This is a separate manual bootstrap source package. It is not a production mission, full lifecycle, SEALED result, qualification, or integration. Only the two existing captured files ('runtime/scope_supersession.py', 'tests/runtime/test_scope_supersession.py') are mutable. Preserve their exact frozen preimages. Read .source_construction_scope.json for the full reviewed requirements. Add only the validated read-only pending-state/contract-denial API. Never consume a new supersession, activate or qualify a contract, or issue authority. No pending record means only not invalidated here, never authenticated currentness. Dependencies are read-only. Do not read the harness key or state database, touch canonical source, spawn workers, or self-authorize.
Authority reference: Coordinator instruction for distinct successor SOURCE_CONSTRUCTION_ONLY task after original source construction terminal completion; same two captured component paths, existing preimages. No retry or relabel of previous consumed operation.
Extend only the captured scope_supersession source and its focused tests with a validated read-only pending-state/contract-denial API for later real controller/Court consumers. Verify ledger/CAS receipt state; a valid pending consumption must deny both predecessor and unactivated successor; reject malformed or ambiguous state. Do not consume new supersession, activate, qualify, or issue authority. With no pending record, report only not invalidated here, never authenticated currentness. Preserve existing consume behavior and all existing focused tests. Do not import ORCA/contracts or model-router modules. Root will freeze complete API/error/receipt validation requirements before dispatch.
You may run the fixed local test helper before submission to repair ordinary test failures inside scope. Court submission is one-use. Physical evidence: after implementation and local tests, invoke the configured Court boundary adapter:
/Users/bob/GitHub/paeos/.venv/bin/python -B /private/tmp/paeos-pending-contract-api.nfIb3R/harness.py court-submit --state /private/tmp/paeos-pending-contract-api.nfIb3R/state --workspace <EXACT_WORKSPACE_BELOW>
This calls the real Court MCP submit_evidence tool for frozen commands and derives evidence physically; do not write the pool yourself. If it fails, stop and report to the coordinator without publishing completion.
On success invoke:
/Users/bob/GitHub/paeos/.venv/bin/python -B /private/tmp/paeos-pending-contract-api.nfIb3R/harness.py complete --state /private/tmp/paeos-pending-contract-api.nfIb3R/state --workspace <EXACT_WORKSPACE_BELOW>
Only this completion adapter publishes the response after complete source/CAS and dependency-integrity checks. Do not publish a response manually. Heterogeneous review is pending; no provider attempts or resets are allowed. Independent verification and heterogeneous review remain mandatory before integration; this package authorizes no integration. Deadline is fixed at 1800 seconds.

```

## Court Evidence for Builder Roles
Submit evidence only through the configured Court MCP boundary using the exact run identifier.
The trusted verifier, not this worker, derives argv, stdout/stderr, exit code, artifact hash,
executable identity, environment identity, and evidence identity. If the Court MCP tool is
unavailable, stop with failure; never write the Court pool or manufacture observations.

When complete, write the full response bytes as strict UTF-8 exactly once to:
`/private/tmp/paeos-pending-contract-api.nfIb3R/state/bridge/responses/sc-pending-r-0d3149bd05a94f58951b2b2afa72496e--t-9f92d769009d--implement.response.md`
