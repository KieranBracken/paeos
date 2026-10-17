#!/usr/bin/env bash
set -euo pipefail

CANDIDATE_DIR="/private/tmp/concept-os-candidate"
PROMPT_FILE="/Users/bob/GitHub/paeos/ops/backlogs/prompt-concept-os-task02.txt"
OUTPUT_FILE="/private/tmp/codex-task02-last-message.txt"

echo "[$(date -u +"%Y-%m-%dT%H:%M:%SZ")] Launching Codex (GPT-5.6 Luna @ Extra High reasoning) for Task 02..."

codex exec \
  --dangerously-bypass-approvals-and-sandbox \
  -m gpt-5.6-luna \
  -c model_reasoning_effort="xhigh" \
  -C "${CANDIDATE_DIR}" \
  -o "${OUTPUT_FILE}" \
  < "${PROMPT_FILE}"
