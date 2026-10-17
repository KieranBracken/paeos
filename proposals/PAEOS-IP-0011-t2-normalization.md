# PAEOS-IP-0011 — T2 Evidence-Result Normalization Protocol (stdout trailing whitespace)

Status: **RATIFIED BY FOUNDER** (2026-08-04) · Filed: 2026-08-04 · Channel: CER-2
Level: **kernel-surface** (amends the T2 deterministic-reproduction gate, `kernel/evidence.py`;
needs §14.5 ceremony + founder — the change is already implemented as `_normalized_result`, this
proposal formalizes the contract it must satisfy). Source: **DEBT-0020**; discovered by the Phase-3
M2/M3 live concurrent runs (CER-1).

## 1. Observation

The T2 gate (`verify_deterministic` in `kernel/evidence.py`) is PAEOS's anti-forgery monitor: the
kernel independently **re-runs** an evidence's `reproducible_command` and requires the fresh result
to equal the agent-reported `result`. Live autonomous runs surfaced a systematic false remand: an
agent that reports `stdout: "PASS"` for a command whose shell output is `"PASS\n"` reproduced the
work *perfectly*, yet a byte-exact comparison remanded it. The seal/no-seal outcome was decided by
whether the agent happened to include a trailing newline — an artifact of `print`, not of the claim.

## 2. Current behaviour

Before the M3 fix, `verify_deterministic` compared `fresh != evidence.result` on the whole result
dict, byte-exact on `stdout`. The M3 fix (commit `9705e8c`) added `_normalized_result`, which
compares `stdout` **modulo trailing whitespace** (`str.rstrip()`), leaving `exit_code` and all
non-trailing `stdout` content compared exactly. That code shipped **without a ratified IP** — the
formal-specification drift against `PAEOS-4` §T2 is exactly what **DEBT-0020** records.

## 3. Proposed improvement (the normalization contract)

Formalize the comparison the T2 gate performs. Two results are **equivalent under T2** iff:

1. **`exit_code`** compares **exactly** (`fresh.exit_code == claimed.exit_code`). No tolerance.
2. **`stdout`** compares equal **after stripping trailing whitespace from both sides**
   (`fresh.stdout.rstrip() == claimed.stdout.rstrip()`). Only the maximal *trailing* run of
   whitespace (`\n`, `\r`, `\t`, spaces) is ignored; leading and interior bytes compare exactly.
3. Any other key present in a result compares **exactly** (the normalization touches `stdout` only).
4. A non-mapping result compares exactly (defensive; results are `{exit_code, stdout}` in practice).

**Boundary conditions (the anti-forgery envelope, stated precisely):**

- Tolerated: `"PASS"` ≡ `"PASS\n"` ≡ `"PASS\n\n  "` (trailing whitespace only).
- **Rejected (still a mismatch):** `"PASS"` vs `"pass"`, `"PASS"` vs `"PASS extra"`, `"PASS"` vs
  `" PASS"` (leading), `"a\nb"` vs `"a b"` (interior). A command doing *different work* differs in
  `exit_code` or in non-trailing content, so it is still caught.

## 4. Justification / first-principles derivation

- **PAEOS-0**: "generation cheap, verification scarce" — the gate must reject *forgery*, not punish
  cosmetically-different-but-identical output. Trailing whitespace carries no evidentiary content;
  requiring byte-exactness on it manufactures false negatives without adding any anti-forgery power.
- **T2 is preserved, provably.** Forgery = claiming a result the command does not produce. Since
  `exit_code` and all non-trailing `stdout` bytes are still exact, any output that materially
  differs (content, length modulo trailing whitespace, or exit status) still remands. The tolerated
  set is exactly the equivalence class `{s + w : w ∈ trailing-whitespace*}`, which contains no two
  strings that differ in evidentiary content.
- Mirrors the existing determinism discipline (`Determinism.DETERMINISTIC` already assumes a stable
  command); this only says the *serialization* of stdout is compared up to its insignificant tail.

## 5. Risks

- **Whitespace-significant output.** A (rare) claim whose correctness depends on a trailing blank
  line would no longer be discriminated. Mitigation: such a claim should assert the property in the
  command itself (`... | wc -l`), not rely on trailing bytes; interior/leading whitespace is still
  exact. Judged negligible against the concrete, recurring false-remand it removes.
- **Scope creep** into interior/leading normalization later. Guarded: this IP fixes the contract at
  **trailing-only**; any widening is a separate IP with its own anti-forgery proof.

## 6. Backwards compatibility

- **Strictly more permissive**, monotonically: every result pair that matched before still matches
  (byte-equal ⇒ equal after rstrip). Only previously-false remands become passes. No stored
  artifact, ledger row, or prior seal changes meaning; `verify_chain` is unaffected (the ledger
  records events, not this comparison). Conformance suites C1–C8 unaffected.

## 7. Constitutional impact

- **Kernel-surface**: amends `PAEOS-4` §T2 (deterministic evidence reproduction). Needs the §14.5
  amendment ceremony + founder ratification (F2 HARD-LOOP). The implementation (`_normalized_result`
  + `verify_deterministic`) and tests already exist (M3); ratifying this IP **closes DEBT-0020** by
  giving that code a specified contract. Add a one-line note to the §T2 clause citing IP-0011.
- No change to authority, roles, lifecycle, or any other invariant.

## 8. Recommendation

**Ratify.** Adopt the §3 contract as the definition of T2 result-equivalence, annotate `PAEOS-4`
§T2 with a pointer to IP-0011, and mark **DEBT-0020 resolved**. The kernel code is unchanged by
ratification (it already implements the contract); this proposal supplies the missing formal
specification and anti-forgery proof (§4) the drift audit required. This recommends; it changes no
law until the founder ratifies.
