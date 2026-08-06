# Autonomous Technical Leadership Protocol

Authority: `backlog/research/RB-0008-autonomous-technical-leadership.md` & `operations/ENGINEERING_LIFECYCLE.md`
Status: **RATIFIED OPERATIONAL PROTOCOL (2026-08-06)**

---

# 1. Purpose & Scope

This protocol governs long-running autonomous executions of PAEOS (e.g. 8–10 hour self-improving runs).

The goal of this protocol is to allow PAEOS to:
1. Drive target ecosystem construction (e.g. SAKG Slices S1–S6).
2. Continuously observe physical friction, failure modes, and structural gaps.
3. Automatically record and classify gaps as Research Notes (`RB-XXXX`), Proposals (`IP-XXXX`), Debt (`DEBT-XXXX`), or Intake code repairs.
4. Calculate Leverage & ROI to determine whether to fix a substrate flaw immediately or queue it.
5. Interrupt the Founder **only** when a constitutional rule strictly requires human ratification.

---

# 2. Classification Rules for Discovered Friction

When an autonomous run encounters friction or a structural gap, it MUST classify the finding according to the matrix below:

| Structural Condition | Action & Output Path | Example |
| --- | --- | --- |
| **Unexplored Research Domain** | File `backlog/research/RB-XXXX.md` | Missing search algorithm or knowledge source. |
| **Constitutional Invariant / Governance Shift** | File `proposals/PAEOS-IP-XXXX.md` | Budget allocation change or new invariant. |
| **Implementation Compromise / Tech Debt** | File `ledger/debt/DEBT-XXXX.md` | Fixed write scope coupling or temp file leak. |
| **In-Scope Task Bug / Test Failure** | Remand intake & attempt self-repair | Builder code bug failing pytest. |

---

# 3. Leverage & ROI Calculation Protocol

Before pausing an active mission to fix a discovered substrate flaw, PAEOS calculates **Substrate Leverage**:

$$\text{Leverage} = \frac{\text{Future Tokens Saved across Ecosystem}}{\text{Tokens Required to Implement Fix}}$$

- **Rule 1 (Immediate Execution)**: If $\text{Leverage} \ge 5.0$, queue the fix into the immediate wave and execute.
- **Rule 2 (Deferred Execution)**: If $\text{Leverage} < 5.0$, record the item in `ledger/debt/` or `backlog/research/` and continue the active mission.

---

# 4. Constitutional Interrupt Criteria

PAEOS MUST interrupt the Founder and pause autonomous execution **only** under the following conditions:

1. **Constitutional Invariant Breach (`AI-001`..`AI-012`)**: An invariant cannot be satisfied.
2. **Un-delegated Founder Action Required (`CER-1` / `A4`)**: Hard structural choice with irreversible cost.
3. **Global Economic Exhaustion**: Global budget ceiling reached after mid-run elevation attempts.
