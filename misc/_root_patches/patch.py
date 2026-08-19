path = "/var/folders/b0/hb9_mxhn4nz09tzctglbjq6w0000gp/T/paeos-t-39f62f436e46-bridge-igabjyim/runtime/orchestrator/__init__.py"
content = open(path).read()

# Replace the planner stages
content = content.replace(
    "for stage in (StageId.IDEATE, StageId.DESIGN, StageId.PLAN):",
    "for stage in (StageId.IDEATE, StageId.RESEARCH, StageId.DESIGN, StageId.PLAN):",
)

# Update the comment
content = content.replace(
    "# --- Planner: IDEATE then DESIGN then PLAN (matched scars injected, FR-6) ---",
    "# --- Planner: IDEATE then RESEARCH then DESIGN then PLAN (matched scars injected, FR-6) ---",
)

open(path, "w").write(content)
