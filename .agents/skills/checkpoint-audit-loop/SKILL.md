---
name: checkpoint-audit-loop
description: Executes the PAEOS Checkpoint Audit Loop across Anthropic quota reset cycles. Trigger when the user mentions "checkpoint audit loop", "quota reset audit", "audit checkpoint", or when an autonomous run encounters a 429 session limit error.
---

# Checkpoint Audit Loop

An autonomous workflow skill that manages long-running PAEOS execution across Anthropic API quota reset windows.

## Workflow Overview

When an autonomous run hits an API 429 quota limit (a **Checkpoint**), this skill executes a 3-step cycle:

```text
 429 Quota Limit (Checkpoint)
             │
             ▼
 ┌──────────────────────────────────────────────────────────────────┐
 │ Step 1: Audit Subagent Execution                                 │
 │ Run constitutional drift audit using the exact audit prompt.     │
 └───────────────────────────────────┬──────────────────────────────┘
                                     │
                                     ▼
 ┌──────────────────────────────────────────────────────────────────┐
 │ Step 2: Record Findings in Debt Ledger                           │
 │ Subagent writes findings to `ledger/debt/DEBT-XXXX.md`.          │
 └───────────────────────────────────┬──────────────────────────────┘
                                     │
                                     ▼
 ┌──────────────────────────────────────────────────────────────────┐
 │ Step 3: Quota Wait & Caffeinated Resume                           │
 │ Schedule run at reset time (e.g. 3:51 AM) with max_runs=1.       │
 └──────────────────────────────────────────────────────────────────┘
```

## Step 1: Audit Subagent Prompt

Invoke a `self` subagent using the following exact prompt:

```text
Given everything implemented since the previous checkpoint, audit for constitutional drift. Assume the implementation is wrong until proven otherwise. Identify duplicated mechanisms, architectural deviations, unnecessary kernel growth, hidden coupling, or implementation that should instead become an Improvement Proposal. add the findings to the debt ledger
```

## Step 2: Recording Findings

The subagent must:
1. Inspect `git log` and `git diff` since the previous checkpoint.
2. Compare implemented code against `constitution/` and `spec/`.
3. Write any identified debt or drift into `ledger/debt/DEBT-XXXX.md`.

## Step 3: Resuming Autonomous Execution

1. Parse the exact quota reset time from the 429 error message (e.g., `resets 3:50am (Europe/London)`).
2. Start `caffeinate -dimu -t 18000` in the background to prevent Mac sleep.
3. Schedule a launch timer for 1 minute after the reset time (e.g., `3:51 AM`).
4. Execute the command:
   ```bash
   PYTHONPATH=. uv run python ops/autonomous_run.py ops/backlogs/sakg-1-intakes.json state_sakg/ 1 1
   ```
5. Schedule a 5-minute recurring check-in (`*/5 * * * *`) to monitor progress until completion.
