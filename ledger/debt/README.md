# Architectural Debt Ledger

The persistence channel for CER-3 (Constitutional Execution Rule 3, Engineering Lifecycle
v1.1). **Whenever an implementation deliberately chooses a non-ideal solution, it is recorded
here.** Architectural debt MUST NOT exist only inside conversation history — PAEOS-0 axiom A2
(artifacts durable, context ephemeral) and the Sentium buried-decisions scar make this
non-negotiable: undocumented compromises are exactly the failure PAEOS exists to prevent.

## What a debt entry is

A deliberate, evidenced compromise plus its repayment plan. In kernel terms it is a recorded
compromise / open incident (K7) — a debt is *open* until repaid or explicitly written off.
Recording debt is not a failure; **hiding** it is.

## Naming

`ledger/debt/DEBT-NNNN.md`, zero-padded, monotonic.

## Required fields (every entry)

1. **Compromise** — the non-ideal choice made.
2. **Reason** — why it was necessary now.
3. **Ideal solution** — what should be done instead.
4. **Repayment conditions** — the evidence/trigger that makes repayment due.
5. **Priority** — low / medium / high / blocking-before-X.
6. **Estimated impact** — cost of leaving it unpaid.

## Distinction from Proposals

A **Proposal** (`proposals/`) recommends improving PAEOS itself (the constitution). A **Debt
entry** records a compromise in an *implementation* against the current constitution. A debt
whose ideal solution requires a constitutional change SHOULD also file a Proposal and link it.

## Index

- `DEBT-0001.md` — Provisional genesis parameters set without tournament evidence.
