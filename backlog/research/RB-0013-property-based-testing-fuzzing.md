# Property-Based Testing & Adversarial Fuzzing for Edge-Case Omission Prevention
## Research Backlog Item — RB-0013 (v0.1)

**Status:** Pre-Implementation / Research Backlog  
**Priority:** High  
**Domain:** Court Verification / Property-Based Testing / Adversarial Fuzzing  
**Related Systems:** `kernel/ledger.py`, `kernel/cas.py`, `runtime/selfhost.py`, `tests/kernel/`, `Hypothesis`  
**Research ID:** RB-0013 / RB-ARCH-VERIFY-002  

---

# 1. Research Thesis

LLMs demonstrate a strong bias toward authoring "happy-path" unit tests. When instructed to write a test suite for a new module, an LLM typically provides 3 to 5 tests covering static, predictable inputs (e.g. `test_parse_intake_success()`, `test_valid_signature()`). The model naturally misses boundary conditions such as empty strings, malformed UTF-8 byte sequences, negative integers, deeply nested JSON, or unexpected `None` values.

Relying on code reviews (by humans or second LLMs) to spot missing test cases is incomplete and time-consuming.

**Thesis:** By mandating **Property-Based Testing** (`Hypothesis` in Python) as a required Court evidence type (`EvidenceKind.PROPERTY_TEST`), PAEOS forces generated code to be verified against **thousands of machine-generated adversarial inputs** per run. If a property test fails, the framework automatically shrinks the input to the exact minimal reproducing edge case—eliminating edge-case omissions deterministically.

---

# 2. Key Problem Statement

1. **Happy-Path Bias**: Generated unit tests only assert what the LLM remembered to test. Un-tested edge cases pass Court verification silently.
2. **Brittle Parsers**: Parsers (like `parse_backlog` or `_parse_intake`) break at runtime when encountering unexpected JSON schemas (e.g., single dicts vs lists) because hand-written tests only used one format.
3. **Ledger & CAS Stress**: Hash-chain integrity (`kernel/ledger.py`) and content-addressed storage (`kernel/cas.py`) must hold across *all* possible binary payloads, not just sample strings.

---

# 3. Proposed Machine-Checkable Solution

### 3.1 Hypothesis Strategy Integration
Require all core kernel interfaces (`kernel/`) and runtime parsers (`runtime/`) to provide `@given` property tests defined via `Hypothesis`.

```python
from hypothesis import given, strategies as st
from kernel.ledger import compute_row_hash

@given(st.text(), st.text(), st.binary())
def test_row_hash_properties(prev_hash, kind, payload):
    # Invariant 1: Deterministic output for identical inputs
    h1 = compute_row_hash(prev_hash, kind, payload)
    h2 = compute_row_hash(prev_hash, kind, payload)
    assert h1 == h2
    
    # Invariant 2: Hash is always 64-char hex string
    assert len(h1) == 64
    assert all(c in "0123456789abcdef" for c in h1)
```

### 3.2 Automated Input Shrinking
When `Hypothesis` discovers a failing input (e.g. a null byte inside a goal signature), it executes a search algorithm to shrink the input to the simplest possible failing example, logging the exact reproducing payload directly into a friction record (`ledger/debt/DEBT-XXXX.md`).

### 3.3 Property Evidence Obligation in Court
Update `RoleSpec` requirements in `runtime/agents/__init__.py` to demand `EvidenceKind.PROPERTY_TEST` obligations for `KERNEL_TOUCHING` and `SUBSTANTIAL` weight-class intakes. A Builder agent cannot seal a kernel change without submitting passing property test execution traces.

---

# 4. Research Questions

* **RQ-1**: What is the optimal number of examples (`max_examples`) for Court property tests to balance test execution wallclock time against fuzzing depth?
* **RQ-2**: Can LLMs be prompted to write invariant assertions (properties) rather than example-based assertions (`assert x == y`)?
* **RQ-3**: How do we persist `Hypothesis` failure databases across sandboxed Court runs to prevent regression of previously discovered edge cases?

---

# 5. Success Criteria & Machine-Checkable Acceptance

1. **Kernel Property Coverage**: 100% of data types in `kernel/types.py` and `kernel/ledger.py` have bound `Hypothesis` property tests running $\ge 500$ random iterations per verification pass.
2. **Automatic Edge-Case Discovery**: Malformed JSON or boundary payloads crash at test time (in Court) rather than during autonomous self-host execution.
3. **Zero Untested Invariants**: Any attempt by a Builder agent to remove or skip a property test causes the Court evidence verifier to reject the seal.
