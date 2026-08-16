# Mutation Testing & Vacuous Test Prevention via Discriminative Court Verification
## Research Backlog Item — RB-0014 (v0.1)

**Status:** Pre-Implementation / Research Backlog  
**Priority:** Critical  
**Domain:** Court Verification / Test Quality / Mutation Testing  
**Related Systems:** `runtime/verification.py`, `kernel/sandbox.py`, `mutmut`, CANARY-0002  
**Research ID:** RB-0014 / RB-ARCH-VERIFY-003  

---

# 1. Research Thesis

An LLM can write complex `try/except` blocks, custom error handlers, and unit tests—and the test suite will report 100% green PASS. However, if the error handler is deleted or the conditional operator is inverted (e.g. `if x > 0:` changed to `if x <= 0:`), the unit test suite may **still pass**. This is the **Vacuous Test Defect (CANARY-0002)**: tests that confirm file existence or run `echo tests-pass` without actually testing the discriminating power of the code change.

Relying on code coverage metrics (`pytest-cov`) is insufficient because coverage only measures if a line was *executed*, not whether the test *asserted* correct behavior.

**Thesis:** By enforcing **Mutation Testing** (`mutmut` or PAEOS `vacuous_commands` in `runtime/verification.py`), the Court automatically introduces intentional code mutations into the workspace and re-runs the Builder's test suite. If the test suite continues to pass after a mutation (a "Surviving Mutant"), the Court **rejects the seal as non-probative**—guaranteeing that every error handler and boundary condition is verified by a test that fails when broken.

---

# 2. Key Problem Statement

1. **CANARY-0002 (Vacuous Evidence)**: Builder subagents can satisfy test obligations by writing trivial assertions (`assert True`) or non-discriminating tests that pass regardless of whether the bug fix is present.
2. **False Security of Coverage**: 100% line coverage does not prevent swallowed exceptions or broken error handlers if assertions are weak.
3. **Court Acceptance of Un-verified Code**: Without mutation testing, code containing broken fallback handlers can be cryptographically sealed into the repository ledger.

---

# 3. Proposed Machine-Checkable Solution

### 3.1 Discriminative Command Verification (`vacuous_commands`)
Expand `runtime/verification.py`'s `vacuous_commands()` function (B2.O) to automatically test all submitted evidence commands against two workspaces:
1. **With-Change Workspace**: The repo with the Builder's produced artifacts applied.
2. **Baseline/Mutated Workspace**: The repo without the change or with intentional code mutations applied.

```python
# Court verification rule: A command is VACUOUS if it returns the exact same 
# exit_code and stdout when the change is inverted or mutated.
def is_probative(command: str, workspace_with_change: Path, baseline_workspace: Path) -> bool:
    res_with = run_sandboxed(command, cwd=workspace_with_change)
    res_without = run_sandboxed(command, cwd=baseline_workspace)
    
    # Probative condition: Must PASS (exit 0) with change, and FAIL (exit != 0) without change!
    return res_with.exit_code == 0 and res_without.exit_code != 0
```

### 3.2 Automated Mutation Injection (`mutmut` Integration)
For `KERNEL_TOUCHING` intake tasks, run a fast mutation pass (`mutmut run --paths-to-mutate <changed_paths>`) in a sandboxed temporary directory:
* Mutate operators (`>` $\rightarrow$ `>=`, `==` $\rightarrow$ `!=`).
* Mutate booleans (`True` $\rightarrow$ `False`).
* Delete `raise` statements.
* Remove `except` block bodies.

If any mutant survives (unit tests pass), the Court rejects the seal with `DETAIL: Vacuous evidence - 2 surviving mutants in runtime/mitigation.py`.

---

# 4. Research Questions

* **RQ-1**: How can we bound the execution time of mutation testing during autonomous self-host runs so that mutation testing finishes in under 60 seconds?
* **RQ-2**: Can mutation testing be scoped strictly to the diff (`git diff HEAD~1`) rather than the entire file to minimize test iterations?
* **RQ-3**: How do we handle intentional fallback defaults where a mutation (e.g. changing default log level) does not alter return values?

---

# 5. Success Criteria & Machine-Checkable Acceptance

1. **Zero Vacuous Evidence**: Every unit test submitted by a Builder agent MUST fail when its corresponding code edit is reverted or mutated.
2. **Surviving Mutant Gate**: No code is sealed if `mutmut` detects surviving mutants in `kernel/` or `runtime/`.
3. **CANARY-0002 Defeated**: `echo tests-pass` or trivial `assert True` test commands fail Court verification immediately.
