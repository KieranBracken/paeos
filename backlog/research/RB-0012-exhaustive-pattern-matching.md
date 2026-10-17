# Machine-Checkable Exhaustive Pattern Matching & State Machine Completeness Verification
## Research Backlog Item — RB-0012 (v0.1)

**Status:** Pre-Implementation / Research Backlog  
**Priority:** High  
**Domain:** Court Verification / Static Analysis / State Machine Completeness  
**Related Systems:** `kernel/types.py`, `kernel/gates.py`, `runtime/orchestrator/__init__.py`, `pyright`, `mypy`  
**Research ID:** RB-0012 / RB-ARCH-VERIFY-001  

---

# 1. Research Thesis

LLMs (regardless of model family) naturally write incomplete state transition logic when generating control flows. When authoring multi-branch conditional statements (`if/elif/else`), models frequently omit corner-case states such as `TIMED_OUT`, `CANCELLED`, `REMANDED`, or `PARTIAL`. In standard Python execution, an unhandled state falls through silently to a default branch or returns `None`, producing silent semantic corruption rather than an immediate fail-fast error.

Relying on model self-inspection or second-model review to spot omitted conditional branches is probabilistic and unreliable. 

**Thesis:** By representing all domain states as strict, closed Python `Enum`s and tagged unions, and requiring all control flow logic over states to use structural pattern matching (`match/case`) enforced by static type checkers (`pyright` or `mypy --strict`), the Court can **statically reject any commit** where a domain state branch is omitted—turning state completeness into a 100% machine-checkable invariant.

---

# 2. Key Problem Statement

1. **The LLM Blindspot**: LLMs default to "happy-path" state handling. When writing state transitions for complex lifecycles (such as `StageId` or `TaskStatus`), the model implements the 3 primary states and omits 2 edge-case states.
2. **Silent Fall-Through**: Standard Python `if/elif` statements do not enforce exhaustiveness. If a state is missed, execution quietly falls through to the `else` clause or returns `None`, creating un-logged state corruption.
3. **Court Gap**: A unit test written by the same model will only test the states the model remembered to implement, allowing vacuous code with missing state handlers to pass verification.

---

# 3. Proposed Machine-Checkable Solution

### 3.1 Strict Tagged Unions & Closed Enums
All PAEOS lifecycle states, task outcomes, and stage identifiers MUST be defined as closed `Enum` types (e.g., `StageId`, `RunStatus`, `FrictionCategory`) in `kernel/types.py`. Free-form string constants for states are strictly forbidden.

### 3.2 Exhaustive Match Statement Requirement
All state evaluation logic across `runtime/` and `kernel/` MUST use Python 3.10+ `match/case` statements without catch-all wildcards (`case _:`) unless explicitly justified.

```python
# GOOD: Exhaustive pattern matching checked statically by pyright/mypy
match outcome.status:
    case RunStatus.SEALED:
        return handle_sealed(outcome)
    case RunStatus.REMANDED:
        return handle_remanded(outcome)
    case RunStatus.HALTED:
        return handle_halted(outcome)
    # If a new RunStatus enum value is added and missing here, 
    # the static type checker FAILS the build immediately.
```

### 3.3 Static Type Checker Court Gate
Integrate `pyright` or `mypy --strict` with `reportMatchNotExhaustive=true` into the Court verification runner (`runtime/verification.py`). Any pull request or builder commit containing non-exhaustive match blocks over domain enums is immediately rejected before tests even run.

---

# 4. Research Questions

* **RQ-1**: Can custom AST checks enforce that `case _:` catch-all branches require an explicit `# exhaustiveness-bypass: <reason>` annotation to prevent LLMs from bypassing match exhaustiveness?
* **RQ-2**: How can we automatically derive state machine transition matrices (e.g. `is_legal(from_stage, to_stage)`) directly from Enum definitions to guarantee total coverage?
* **RQ-3**: What is the performance overhead of running `pyright` static exhaustiveness checks inside the sandboxed Court runner?

---

# 5. Success Criteria & Machine-Checkable Acceptance

1. **Zero Unhandled States**: Adding a new `Enum` member to `StageId` or `RunStatus` without updating all `match` statements across `kernel/` and `runtime/` causes `pyright` / Court verification to fail with code `1`.
2. **Zero String State Literals**: Static linter rules flag any string literal comparison against state names (e.g. `if status == "SEALED":`) as a hard Court rejection.
3. **Total Transition Matrix**: `kernel/gates.py` transition legality functions are proven total over `StageId \times StageId \times WeightClass`.
