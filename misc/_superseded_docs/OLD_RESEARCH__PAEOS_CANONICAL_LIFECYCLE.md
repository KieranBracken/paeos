# PAEOS Canonical Lifecycle Reconstruction

## 1. Executive Summary
PAEOS defines a rigorously structured, 19-layer constitutional engineering lifecycle that serves as the backbone of its operation. It enforces a strict separation between discovering the problem, exploring the solution space, designing the architecture, and eventually implementing it. 

However, there is a fundamental and critical discrepancy between the **Constitutional Documentation** (which mandates the 19 layers) and the **Current Runtime Implementation** (`SoftLoop` in `runtime/orchestrator/__init__.py`), which actively short-circuits the canonical lifecycle down to a sparse 6-step loop. The system enforces transition authority via a capability broker, and transitions require four elements: Authority, Goal, Evidence, and Validation (`TransitionRequest`). 

## 2. Evidence Sources
This reconstruction is derived from an exhaustive audit of the PAEOS repository:
- `spec/PAEOS-9-execution-architecture.md` (Constitutional dataflow and layer specification)
- `operations/ENGINEERING_LIFECYCLE.md` (Explicitly describes layers L01 to L19)
- `kernel/types.py` (Defines the 21 `StageId` constants and the transition value contracts)
- `kernel/lifecycle.py` (Defines the legal forward-edges and the reference monitor `is_legal`)
- `kernel/gates.py` (Defines the `Gate.propose_transition` logic)
- `kernel/state.py` (Defines the epistemic `ReasoningState` and Checkpoint schemas)
- `runtime/orchestrator/__init__.py` (The actual implementation of the soft loop)
- `runtime/context_compiler.py` (Context compilation and epistemic filtering policies)

## 3. Canonical Entrypoint
- **Documented**: The lifecycle begins at `Intake` (L01 - StageId.INTAKE), which consumes a raw problem statement/intent from any source, creating a `Goal(kind=work|incident)` in the `declared` state.
- **Implemented**: `cli/paeos.py` -> `create_goal` generates a goal natively in `StageId.RAW`. Then `SoftLoop.run` (`runtime/orchestrator/__init__.py`) directly starts its autonomous loop loop with `StageId.DESIGN`, effectively bypassing layers L01 through L08 (except a small implicit Triage budget assignment).

## 4. Complete 19-Layer Lifecycle (Documented Spine)
The fully documented canonical execution lifecycle consists of 19 operational layers (L01-L19), supported by two underlying states (RAW, RE_DERIVE):
1. **L01: Intake** (`StageId.INTAKE`)
2. **L02: Triage** (`StageId.TRIAGE`)
3. **L03: First-Principles Re-Derivation** (`StageId.RE_DERIVE`)
4. **L04: Ambitious Ideation** (`StageId.IDEATE`)
5. **L05: Frontier Research** (`StageId.RESEARCH`)
6. **L06: Trade-off Analysis** (`StageId.TRADEOFF`)
7. **L07: Trade-off Mitigation** (`StageId.MITIGATION`)
8. **L08: System Design** (`StageId.DESIGN`)
9. **L09: Multi-Perspective Critique** (`StageId.CRITIQUE`)
10. **L10: Adversarial Review** (`StageId.ADVERSARIAL_REVIEW`)
11. **L11: Formal Planning** (`StageId.PLAN`)
12. **L12: Branch Implementation** (`StageId.IMPLEMENT`)
13. **L13: Verification** (`StageId.VERIFY`)
14. **L14: Independent Audit** (No explicit `StageId` distinct from `ADVERSARIAL_REVIEW` or it's subsumed, actually wait, `StageId` has `ADVERSARIAL_REVIEW` but no separate `AUDIT` stage; it may use `ADVERSARIAL_REVIEW` logic.)
15. **L15: Documentation & Ledger** (`StageId.LEDGER_SYNC`)
16. **L16: Promotion Decision** (`StageId.SEAL`)
17. **L17: Retrospective** (`StageId.RETROSPECT`)
18. **L18: Knowledge Extraction** (`StageId.EVOLVE`) *(Wait, mapping is EVOLVE vs MEMORY_UPDATE)*
19. **L19: Constitutional Evolution** (`StageId.EVOLVE` / `IMPROVE_RUNTIME`)

## 5. Detailed Table for All Layers

| Layer | Canonical Name | Purpose | Entry Condition | Auth/Component | Inputs | Outputs | State Mutations |
|---|---|---|---|---|---|---|---|
| L01 | Intake | Capture idea/bug | Any source | Runtime / Any | Source intent | Declared Goal | -> INTAKE |
| L02 | Triage | Decide scope & ceremony | Declared Goal | Planner (Router) | Goal | DispatchRecord | -> TRIAGE |
| L03 | Re-Derivation | Derive from first principles | L02 Keep/Immediate | Planner+Researcher | L02 Goal | Derivation | -> RE_DERIVE |
| L04 | Ambitious Ideation| Generate idealized solutions | L03 complete | Planner+Builder | Derivation | Candidates | -> IDEATE |
| L05 | Frontier Research | External knowledge pull | Blocked at L03/04/06 | Researcher | Blocked state | Research dossier | -> RESEARCH |
| L06 | Trade-off Analysis| Identify every trade-off | Viable L04 candidates | Planner+Reviewer | Candidates | Trade-off matrix | -> TRADEOFF |
| L07 | Mitigation | Design safeguards for compromises | L06 matrix exists | Planner+Adversary | Matrix | Mitigation cat. | -> MITIGATION |
| L08 | System Design | Produce architecture (no code) | L04 + L07 | Planner | Candidates, Mitigations | Architecture | -> DESIGN |
| L09 | Critique | Multi-perspective design attack | L08 architecture | Reviewer (x7) | Architecture | Finding register | -> CRITIQUE |
| L10 | Adversarial Review| Prove design wrong | L08 + L09 | Court+Adversary | Arch + Findings | Verdict / Ledger | -> ADVERSARIAL_REVIEW |
| L11 | Formal Planning | Freeze implementation scope | L10 RATIFY | Planner | L10 verdict | Impl. contract | -> PLAN |
| L12 | Implementation | Implement approved scope | L11 contract | Builder | Contract, Repo | Commits/Execution | -> IMPLEMENT |
| L13 | Verification | Prove correctness (mechanical) | Executed L12 code | Auditor/Runtime | Execution | Evidence, logs | -> VERIFY |
| L14 | Independent Audit | Fault hunting (decorrelated) | L13 passed | Auditor | Evidence | Audit report | (Implicit via Court) |
| L15 | Doc & Ledger | Sync institutional knowledge | L14 clean | Runtime+Builder | Audit clean | Ledger deltas | -> LEDGER_SYNC |
| L16 | Promotion Decision| Decide artifact fate | L15 complete | Integrator+Founder | Deltas | SEAL or REJECT | -> SEAL |
| L17 | Retrospective | CER-4 Constitutional Review | L16 complete (or fail) | Auditor+Runtime | Task Outcome | Task Review | -> RETROSPECT |
| L18 | Knowledge Extraction| Generalize reusable knowledge | L17 lessons | Auditor (Steward) | Task Review | Skills/Templates | -> MEMORY_UPDATE |
| L19 | Const. Evolution | Update PAEOS itself | L18 or Incident | Court+Founder | Incident/Policy | Recompiled policy | -> EVOLVE |

## 6. Lifecycle Topology / State-Transition Diagram
The execution is structured as a Loop of Loops, gated by the kernel's `is_legal` transitions:
`[RAW] -> [INTAKE] -> [TRIAGE] -> [RE_DERIVE] -> [IDEATE] <-> [RESEARCH] -> [TRADEOFF] -> [MITIGATION] -> [DESIGN] -> [CRITIQUE] -> [ADVERSARIAL_REVIEW] -> [PLAN] -> [IMPLEMENT] -> [VERIFY] -> [ADVERSARIAL_REVIEW] -> [LEDGER_SYNC] -> [SEAL] -> [RETROSPECT] -> [MEMORY_UPDATE] -> [EVOLVE] -> [IMPROVE_RUNTIME] -> [RESTART]`

Failures route internally (via `REMAND`) back to earlier states without advancing the logical frontier, or trigger `QUARANTINE`/`ABORT`.

## 7. Governance Authority Map
- **Kernel (`Gate.propose_transition`)**: Enforces that no state transitions occur without a valid `CapabilityToken`, matching `GoalId`, explicitly verified `EvidenceRef`s, and a matching `ValidationClaim`.
- **CapabilityBroker**: Mints short-lived (TTL-bound) tokens authorizing specific roles (Planner, Builder, Critic, Verifier, Adversary, Doc, Ratifier) to execute specific operations.
- **Court**: Assesses the validity of Evidence claims against the artifact.
- **InformationBarrierManager**: Enforces that the Adversary only receives the sealed bundle, maintaining epistemic decorrelation from the Builder.
- **Founder**: Retains exclusive authority over kernel-surface constitutional changes (L19).

## 8. Agent/Model Invocation Path
`AgentDispatcher.dispatch` -> `AgentRuntime.run_session`.
Models are invoked in a strictly ephemeral manner, sandboxed per session. The `AgentRuntime` receives a `CompiledContext` (with matched scars) and a `budget`. Output artifacts are captured and hashed, leaving the models entirely memoryless between phases. 

## 9. Context Construction Path
Implemented in `runtime/context_compiler.py`.
The Context Compiler constructs deterministic prompts. It takes the `objective`, `context_refs`, `scars`, and `reasoning_state` and filters the `ReasoningState` using a `ContextPolicy` (e.g., `FULL_CONTINUATION`, `MINIMUM_SUFFICIENT`, `BLIND_CONCLUSION`, `DECISION_TARGETED_ADVERSARIAL`). The resulting bundle is hashed to provide deterministic, content-addressable inputs to the Agent SDK.

## 10. Persistence Path
Persistence is enforced via an append-only `Ledger` backed by `SqliteLedgerStore` (in live runs).
State transitions create `Event`s (`goal_created`, `transition_committed`, `checkpoint_created`). 
Large unstructured data (evidence logs, design docs, reasoning state objects) are stored in the `CAS` (Content Addressable Storage), and only their `Hash` is written to the Ledger.

## 11. Failure/Remand/Retry Paths
Failures do not mutate backwards. The system uses a `REMAND` outcome.
If the Court fails to verify evidence (e.g., non-probative/vacuous tests), or the Adversary blocks a seal, `SoftLoop` returns `RunStatus.REMANDED` accompanied by an `ExecutionContext` (L1 Ephemeral Context) containing retry hints and diagnostics. A remanded task can be re-attempted, but the timeline remains append-only.

## 12. Terminal/Sealing Path
`Gate.propose_transition(..., to_state=StageId.SEAL)` triggers the sealing process.
`SealAuthority.seal` binds the `artifact_bundle`, `verdict_ref`, and `adversary_ref` alongside the Goal and Run ID into a `SealRecord` on the ledger. 

## 13. Documentation vs Code Discrepancies
**STATUS: MASSIVE DISCREPANCY DETECTED.**
- **DOCUMENTATION**: `operations/ENGINEERING_LIFECYCLE.md` and `kernel/lifecycle.py` enforce a mandatory 19-step loop (CER-1 to CER-6 rules).
- **IMPLEMENTATION**: `runtime/orchestrator/__init__.py` (`SoftLoop._run_body`) hardcodes a completely reduced fast-path:
  `DESIGN -> PLAN -> IMPLEMENT -> COURT -> REVIEW -> SEAL`.
- It silently ignores `RE_DERIVE`, `IDEATE`, `TRADEOFF`, `MITIGATION`, and all Post-Seal learning loops (`RETROSPECT`, `MEMORY_UPDATE`, `EVOLVE`). 
- **IMPLEMENTATION**: The orchestrator also hardcodes L1/L3 Ephemeral contexts vs Durable scars logic on Remand, rather than routing to the Canonical Retrospective layers to organically author them.

## 14. Existing Continuity/Checkpoint Capabilities
`kernel/state.py` defines `Checkpoint`, which serializes:
- `checkpoint_id`, `goal_id`, `run_id`, `stage`
- `reasoning_state_hash` (CAS pointer to the `ReasoningState` payload)
- `git_revision`, `context_revision`, `active_task`, `invocation_lineage`
`SoftLoop.emit_checkpoint` writes a `checkpoint_created` Event to the Ledger. The `ReasoningState` itself defines semantic components (`Fact`, `Constraint`, `Decision`, `Result`, etc.) and `ContextPolicy` filters these dynamically to govern epistemic isolation.

## 15. Implications for Future RCL Integration
The Reasoning Continuity Layer (RCL) MUST integrate with the *Canonical* 19-layer architecture, not the truncated `SoftLoop`.
Because `ContextCompiler` already natively handles granular epistemic filtering (`ContextPolicy.BLIND_CONCLUSION`, etc.), RCL must leverage the existing `Checkpoint` and `ReasoningState` mechanics rather than reinventing state serialization. RCL will primarily serve to hydrate `ReasoningState` into actionable context for `AgentDispatcher`, allowing the 19 layers to execute persistently.

## 16. Explicit List of Things That Are NOT Currently Proven
1. It is NOT PROVEN that the system can actually execute the L17-L19 (Learning and Evolution) phases autonomously; they are entirely missing from `SoftLoop`.
2. It is NOT PROVEN that a multi-agent debate (e.g., L09 Multi-Perspective Critique) currently functions, as `SoftLoop` invokes isolated Planner and Builder sessions.
3. It is NOT PROVEN that branching workflows (e.g., parallel IDEATE explorations) are supported by the `AgentDispatcher`.
4. It is NOT PROVEN how `StageId.RE_DERIVE` operates in reality as no playbook entry currently maps to it.

## 17. Confidence/Evidence Rating
- **Kernel Types & Governance Topology**: HIGH CONFIDENCE. `kernel/types.py`, `kernel/gates.py`, and `kernel/lifecycle.py` mathematically enforce the transition constraints.
- **Dataflow/Context Assembly**: HIGH CONFIDENCE. `runtime/context_compiler.py` and `kernel/state.py` clearly define the deterministic hashing and epistemic filtering pipeline.
- **Orchestrator Adherence to Constitution**: LOW CONFIDENCE. The `SoftLoop` is provably in violation of the `ENGINEERING_LIFECYCLE.md` constitution, indicating it is an incomplete scaffolding/vertical slice, rather than the final operational pipeline.
