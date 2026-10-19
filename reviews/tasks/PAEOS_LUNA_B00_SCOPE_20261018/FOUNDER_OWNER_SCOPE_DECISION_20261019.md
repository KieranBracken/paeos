# Founder decision packet: admission owner and send-fence scope

**Decision ID:** `OWNER_SCOPE_B00_20261019`
**Status:** `FOUNDER_DECISION_REQUIRED`
**Type:** governance and implementation-scope proposal; not an appointment, PAEOS admission, or implementation authorization
**Prepared from:** recovery branch `codex/p1-bound-source-recovery-20261018` at `1a7b8b03afd53c58ee0606e3a37381f56b1b1430`; pinned B00 source candidate `082a59ce163d15fc0d40141c1c6cc74e7522d063`.

## Decision requested

PAEOS has no evidenced official technical owner for canonical mission-admission currentness, revocation, and the boundary between a permitted send claim and actual transmission. The architect was assigned architecture and coordination, but that combined role has not closed the source-ownership gap. The Founder is asked to establish one accountable technical owner while keeping coordination separate.

**Recommendation:** appoint a distinct **Admission Boundary Owner** for this bounded lane. Keep the architect in the coordination role. Nominate **Chat 3 — Authenticated Mission Admission** as the first assignee because its remit and B00 source trace are closest to the problem, but only after its current S0 candidate is frozen and completed or explicitly handed off. The nomination is not an appointment and does not transfer or reuse the S0 task's authority. The Founder may name another existing worker instead. No new chat is created by this proposal.

The appointment creates accountability to identify and implement within the real canonical subsystem; it does not declare Chat 3, the Policy Router, RouterStateDB, or any current file to be the authority source. It does not grant unilateral disclosure, key, production, or qualification authority.

## Evidence basis

The B00 source-bound check verified 9 bound checkpoint artifacts, 20 source preimages, and 49 egress-inventory pins. It found no evidenced canonical owner or durable API/state for admission currentness and revocation, no revoke operation, no atomic send claim, and no durable restart/`UNKNOWN` reconciliation. Five inventoried Cline/Codex paths remain reachable or manually callable. The original Security Review and disposition remain unchanged.

The inspected `runtime/worker_admission.py` and `runtime/supervisors/admission.py` validate probe receipts or compare profiles; they do not establish a durable currentness lease. `runtime/autonomy/authority.py` contains authority classification rules but no persisted send fence. `paeos/model_router/state.py` owns router health/quota state and is not an enrolled admission authority. The bootstrap guide's `acquire_send_lease` and `finish_send_lease` names are proposed semantics, not APIs proven to exist.

The source-bound result and exact limits are preserved in `REPORT.md`, `FENCE_FINDINGS.json`, and `EGRESS_INVENTORY.json` in this task directory. This packet makes no test, code, runtime, provider, Court, or PAEOS lifecycle claim.

## Alternatives

| Choice | Consequence | Assessment |
|---|---|---|
| Keep the architect as both technical owner and coordinator | Preserves the current assignment but repeats the same accountability/coordination arrangement that did not resolve ownership. | Not recommended. |
| Appoint a distinct Admission Boundary Owner; architect coordinates | Gives one role responsibility for the canonical source map, fence contract, and bounded implementation. Chat 3 is the nominated existing worker after a safe handoff; Founder can choose another. | Recommended. |
| Founder acts as the technical owner | Gives direct control but makes each source and integration detail a manual Founder bottleneck. | Use only if no suitable existing technical worker can accept the assignment. |

## Proposed owner remit

The owner is accountable for one boundary: establish which existing subsystem owns the current mission admission, prove its source of truth, and integrate a durable authorization/currentness check with the actual outbound-send owner. The owner may propose concrete API names only after tracing the existing consumers and transaction boundary.

The implementation contract must bind, at minimum, the authenticated mission/root and task identity; run, stage and role; exact scope and workspace; current admission reference and epoch; logical operation identity; complete prompt/frame digest and accessible-input closure; destination/route; and the observed provider/model identity when the route's contract supplies it. Worker-authored labels, prompt text, caller-selected key paths, or a local profile hash cannot establish classification, currentness, or disclosure permission.

Classification and destination permission remain separate trust inputs. The owner must consume their verified decision at the send boundary; it must not accept a worker-supplied label, key, verifier, policy path, or callback as authority. This assignment does not make the owner the policy-classification authority. If no trusted policy authority exists to provide that decision, disclosure stays denied and the missing policy owner is returned as a separate Founder decision.

Revocation and the final send claim must serialize through one enforced authoritative transaction or shared fence at the network-owning boundary, with the durable claim committed before socket write. If revocation wins, transmission cannot begin. If the send claim wins, only the bound network owner may begin that one transmission; later revocation cannot erase bytes already emitted. A separate check followed by an unrelated send transaction is insufficient. A crash or lost response after reservation/claim must remain unresolved and non-replayable until authoritative reconciliation. The owner must test the real cross-process storage and recovery behavior; elapsed lease time or a new chat/task ID cannot clear an uncertain effect.

The owner must also close the five specific paths in `EGRESS_INVENTORY.json`: bound-Cline compatibility, Cline SDK admission probe, Cline diagnostic method, direct Codex task script, and legacy Codex CLI invoker. For each, provide a synthetic negative proving denial before prompt access/signing/process/socket/network effects, or prove the path unavailable in the target runtime with a test. ChatBridge remains excluded as a transport; this scope permits inspection or deny-only containment where needed, never dispatch through it.

## Boundaries and explicit exclusions

This proposed scope is default-deny and synthetic/provider-free. It does not authorize positive egress, external provider calls, private-key creation or use, Founder enrollment, installation, production activation, Builder qualification, Court adjudication, debt integration, or P3. It does not modify Chat 1's exclusive DEBT-0258/kernel scope or any original review finding. It does not authorize a new authority service, parallel ledger, or using RouterStateDB as canonical mission authority. If the source map shows that a new authority store or broader constitutional change is required, implementation stops and returns a separate Founder design decision.

The 20% quota reserve is waived for this week only. No paid route or privacy-policy relaxation is included. Independent review must use a fresh, eligible free route from a different model family; if none is available, review remains held. Review, Court adjudication, and qualification remain separate.

## Execution gates if approved

1. The appointed owner safely completes or hands off its existing candidate, then acknowledges this exact scope. The architect coordinates sequencing and reports state; it does not self-authorize source changes.
2. Before source edits, the owner returns a source-bound ownership map naming the actual canonical store/API, code owner, revocation transaction, send linearization point, and crash/`UNKNOWN` reconciliation contract. If no existing subsystem can own this without new authority, stop and ask the Founder; do not improvise one.
3. Start one fresh PAEOS task with authentic admission, exact source scope and isolated workspace, ChatBridge excluded, and physical worker-start/returned-evidence receipts. The B00 evidence task and this Codex conversation are not substitutes. If the configured PAEOS entrypoint cannot produce those receipts, stop with that implementation gap rather than editing outside the admitted workspace.
4. Freeze the exact mutable manifest, then produce a candidate in the existing owner subsystem plus only the inventoried deny-only paths that the owner proves are in scope. Run focused positive-control, denial, bypass, cross-process race, crash/restart, and `UNKNOWN` tests with synthetic data and network/provider access disabled. A positive-control test may validate a synthetic authorization decision; it must not transmit to a provider.
5. Capture immutable candidate bytes, request one fresh independent review of that exact candidate, preserve findings unchanged, resolve within this scope, and push an explicit sanitized manifest with remote SHA readback. No installation or qualification follows from this package.

## Downstream ownership remains unchanged

Chat 1 remains the sole DEBT-0258 integrator. DEBT-0249 may continue only work already covered by its own current admission. DEBT-0260 remains behind DEBT-0258 qualification; DEBT-0117 remains behind DEBT-0258 and DEBT-0260. No debt worker wakes under this owner-scope decision. P3 remains held until every required pre-P3 gate has sealed evidence.

## Founder disposition

Choose one:

- [ ] **Approve recommendation:** appoint Chat 3 as Admission Boundary Owner after its current S0 candidate is safely completed or handed off; keep the architect as coordinator; authorize only the bounded, conditional, default-deny scope above.
- [ ] **Choose another existing technical owner:** name the role/chat and keep the same bounded scope and exclusions.
- [ ] **Keep the gate held:** do not appoint an owner yet.

Approval covers ownership and this conditional candidate scope only. If the owner proves that no existing canonical subsystem can satisfy the contract, or if PAEOS cannot produce authentic admission/start evidence, stop and return the precise new decision required. It does not authorize positive egress, installation, qualification, Court action, debt activation, or P3.
