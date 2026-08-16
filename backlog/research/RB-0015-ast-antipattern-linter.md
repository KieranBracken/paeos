# AST-Based Anti-Pattern Linters & Swallowed Exception Enforcement
## Research Backlog Item — RB-0015 (v0.1)

**Status:** Pre-Implementation / Research Backlog  
**Priority:** High  
**Domain:** Court Verification / AST Static Analysis / Error Handling Quality  
**Related Systems:** `runtime/verification.py`, `kernel/sandbox.py`, `ruff`, Python `ast` module  
**Research ID:** RB-0015 / RB-ARCH-VERIFY-004  

---

# 1. Research Thesis

When LLMs write error handling logic, they demonstrate a pervasive habit of writing "lazy fallbacks" to prevent code execution from crashing. The most common manifestations are:
1. Bare `except:` blocks catching all exceptions including `KeyboardInterrupt` and `SystemExit`.
2. `except Exception: pass` (silent error swallowing).
3. `except Exception: return None` or `return {}` (silent null fallback without logging).

In an autonomous engineering system, swallowed exceptions are catastrophic: they mask underlying bugs, cause downstream state corruption, and prevent the friction detector (`RB-0008`) from logging debt.

**Thesis:** By implementing a custom **AST (Abstract Syntax Tree) Anti-Pattern Visitor** inside the Court verification engine (`runtime/verification.py`), PAEOS can perform static code structure inspection on every generated file before compilation. Any code containing swallowed exceptions, bare excepts, or un-logged fallback returns is **statically rejected at the AST level** with zero reliance on LLM self-review.

---

# 2. Key Problem Statement

1. **Silent Exception Swallowing**: LLMs frequently wrap uncertain code in `try...except Exception: pass` to make unit tests pass without fixing the underlying bug.
2. **Loss of Friction Detection**: If an exception is swallowed silently, `record_friction()` is never called, preventing the runtime from detecting structural debt.
3. **Downstream Corruption**: Returning dummy defaults (`0`, `""`, `None`) on unexpected exceptions corrupts state machines and ledger records.

---

# 3. Proposed Machine-Checkable Solution

### 3.1 AST Anti-Pattern Visitor (`PaeosAstLinter`)
Develop an AST visitor using Python's built-in `ast` module that scans all changed files (`changed_paths`) during Court verification.

```python
import ast

class ExceptionSwallowingVisitor(ast.NodeVisitor):
    def __init__(self):
        self.violations = []

    def visit_ExceptHandler(self, node: ast.ExceptHandler):
        # Rule 1: Bare except (except:)
        if node.type is None:
            self.violations.append((node.lineno, "Bare 'except:' is strictly forbidden."))

        # Rule 2: Exception swallowing (body contains only 'pass' or 'return None' without logging)
        if len(node.body) == 1:
            first_stmt = node.body[0]
            if isinstance(first_stmt, ast.Pass):
                self.violations.append((node.lineno, "Silent 'except Exception: pass' is forbidden."))
            elif isinstance(first_stmt, ast.Return) and (first_stmt.value is None or isinstance(first_stmt.value, ast.Constant) and first_stmt.value.value is None):
                self.violations.append((node.lineno, "Un-logged 'except Exception: return None' is forbidden."))
        
        self.generic_visit(node)
```

### 3.2 Court Enforcement Gate
Add `PaeosAstLinter` as a mandatory pre-verification gate in `runtime/verification.py`. 
If any file in `changed_paths` contains a registered AST anti-pattern, the Court aborts verification immediately and returns:
`RunStatus.REMANDED — AST Violation in runtime/selfhost.py:L112: Silent 'except Exception: pass' is forbidden.`

### 3.3 Strict Rule Configuration
Enforce the following non-negotiable AST rules across all PAEOS repositories:
* **PAEOS-AST-01**: No bare `except:`. Must specify exception type (`except (ValueError, KeyError):`).
* **PAEOS-AST-02**: No `pass` inside an exception handler without explicit `logger.exception()` or friction recording.
* **PAEOS-AST-03**: No wildcard `except Exception:` unless re-raising (`raise`) or converting to `FrictionRecord`.

---

# 4. Research Questions

* **RQ-1**: Can `ruff` or custom `flake8` plugins be configured to enforce `PAEOS-AST-01..03` during local development as well as during Court verification?
* **RQ-2**: How do we handle legitimate top-level event loops (such as task cleanup threads) where catching `Exception` is required to prevent daemon crashes?
* **RQ-3**: Can the linter automatically generate a debt item when an un-logged exception pattern is detected?

---

# 5. Success Criteria & Machine-Checkable Acceptance

1. **Zero Swallowed Errors**: 0 occurrences of `except Exception: pass` or bare `except:` across `kernel/`, `runtime/`, `ops/`, and `tests/`.
2. **Static AST Court Rejection**: Submitting a pull request or intake containing a silent `try/except` block fails Court verification with code `1` in $< 0.1$ seconds.
3. **Auditable Exception Handling**: 100% of exception handlers across the codebase explicitly log errors, record friction, or re-raise domain-specific exceptions.
