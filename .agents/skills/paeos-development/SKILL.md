---
name: paeos-development
description: Use when editing or expanding the PAEOS architecture. Explains how to properly use the autonomous SoftLoop via the chat-bridge, preventing unauthorized direct modifications.
---

# PAEOS Development & Architecture Skill

When you are asked to implement research backlog items or expand the PAEOS architecture, **DO NOT** edit the repository files directly with your code editing tools. Doing so circumvents the PAEOS SoftLoop (the Verification Court, the Capability Broker, and the state ledger).

Instead, you must drive the PAEOS architecture autonomously using the **Chat-Bridge Runtime**.

## 1. Preparing the Loop
The PAEOS architecture runs as a state machine. You are the orchestrator interacting with it.
To start the PAEOS cycle, you need an intake file (e.g. `ops/backlogs/ade_intake.json`). 
Run the following command in the background (using `IsDaemon: true` or checking status via `manage_task`):
```bash
uv run python ops/autonomous_run.py <intake.json> .state 1 25 chat-bridge
```

## 2. Interacting with the Bridge
When PAEOS reaches a stage that requires LLM generation (IDEATE, DESIGN, BUILD, VERIFY), it will pause and prompt you by writing to `.paeos_state/bridge/current_prompt.md`.

You must:
1. **Read the Prompt**: Check the contents of `.paeos_state/bridge/current_prompt.md` to understand the current `StageId`, `Role`, and sandbox directory.
2. **Execute the Task in the Sandbox**:
   - The loop will provide a temporary workspace directory (e.g., `/var/folders/...`).
   - You must execute your code changes **inside this workspace directory**, not the host repository.
   - You can use your standard code editing tools targeting the absolute paths of the files in the workspace.
3. **Submit Evidence (BUILD/VERIFY stages)**:
   - If the prompt demands it, use the requested MCP tools (e.g. `submit_evidence`) or run tests inside the workspace.
4. **End the Turn**:
   - Write your final response or status to `.paeos_state/bridge/current_output.md`.
   - The `ChatBridgeRuntime` will detect the output and advance the PAEOS state machine to the next step.

## 3. Strict Rules
- **No Direct Root Edits**: Do not use `write_to_file` or `multi_replace_file_content` on the host repository (`/Users/bob/GitHub/paeos/`) for architectural features, unless creating initial intakes or managing backlog logs. All actual code implementations MUST be routed through the bridge sandbox.
- **Discriminative Testing**: When writing test evidence, ensure your commands (e.g., `uv run pytest path/to/test.py`) legitimately pass against your change, but would fail against the baseline. The Verification Court strictly enforces this.
