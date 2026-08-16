ws = "/var/folders/b0/hb9_mxhn4nz09tzctglbjq6w0000gp/T/paeos-t-d99529ee3516-bridge-t122arwe"

# 1. orchestrator
path = f"{ws}/runtime/orchestrator/__init__.py"
content = open(path).read()
content = content.replace(
    "for stage in (StageId.IDEATE, StageId.DESIGN, StageId.PLAN):",
    "for stage in (StageId.IDEATE, StageId.RESEARCH, StageId.DESIGN, StageId.PLAN):",
)
content = content.replace(
    "# --- Planner: IDEATE then DESIGN then PLAN (matched scars injected, FR-6) ---",
    "# --- Planner: IDEATE then RESEARCH then DESIGN then PLAN (matched scars injected, FR-6) ---",
)
open(path, "w").write(content)

# 2. agents
path = f"{ws}/runtime/agents/__init__.py"
content = open(path).read()
_RESEARCH = """_RESEARCH = RoleSpec(
    stage=StageId.RESEARCH,
    role=Role.PLANNER,
    objective=(
        "Conduct frontier research on the ideated candidates. Analyze the codebase, dependencies, "
        "and relevant documentation to evaluate feasibility, architectural fit, and constraints. "
        "Produce a structured ResearchDossier (saved to the research/ directory) synthesizing "
        "the findings to inform the DESIGN stage."
    ),
    write_scopes=("research/",),
)"""
if "_RESEARCH =" not in content:
    content = content.replace("_DESIGN = RoleSpec(", _RESEARCH + "\n\n_DESIGN = RoleSpec(")
    content = content.replace(
        "    StageId.IDEATE: _IDEATE,",
        "    StageId.IDEATE: _IDEATE,\n    StageId.RESEARCH: _RESEARCH,",
    )
open(path, "w").write(content)

# 3. context compiler
path = f"{ws}/runtime/context_compiler.py"
content = open(path).read()
content = content.replace(
    "- IDEATE writes an IdeationSet",
    "- IDEATE writes an IdeationSet\n- RESEARCH writes a ResearchDossier",
)
content = content.replace(
    "DESIGN needs the IdeationSet.",
    "RESEARCH needs the IdeationSet. DESIGN needs the ResearchDossier.",
)
open(path, "w").write(content)

# 4. test_soft_loop
path = f"{ws}/tests/runtime/test_soft_loop.py"
content = open(path).read()
content = content.replace(
    "[StageId.RE_DERIVE, StageId.IDEATE, StageId.DESIGN, StageId.PLAN, StageId.IMPLEMENT, StageId.ADVERSARIAL_REVIEW]",
    "[StageId.RE_DERIVE, StageId.IDEATE, StageId.RESEARCH, StageId.DESIGN, StageId.PLAN, StageId.IMPLEMENT, StageId.ADVERSARIAL_REVIEW]",
)
content = content.replace(
    "[StageId.IDEATE, StageId.DESIGN, StageId.PLAN, StageId.IMPLEMENT, StageId.ADVERSARIAL_REVIEW]",
    "[StageId.IDEATE, StageId.RESEARCH, StageId.DESIGN, StageId.PLAN, StageId.IMPLEMENT, StageId.ADVERSARIAL_REVIEW]",
)
content = content.replace(
    "[StageId.DESIGN, StageId.PLAN, StageId.IMPLEMENT, StageId.ADVERSARIAL_REVIEW]",
    "[StageId.RESEARCH, StageId.DESIGN, StageId.PLAN, StageId.IMPLEMENT, StageId.ADVERSARIAL_REVIEW]",
)
content = content.replace(
    "plan_idx = seq.index(StageId.PLAN)",
    "plan_idx = seq.index(StageId.PLAN)\n    research_idx = seq.index(StageId.RESEARCH)",
)
content = content.replace(
    "assert re_derive_idx < ideate_idx < design_idx < plan_idx < impl_idx < adv_idx",
    "assert re_derive_idx < ideate_idx < research_idx < design_idx < plan_idx < impl_idx < adv_idx",
)
content = content.replace(
    "StageId.RE_DERIVE, StageId.IDEATE, StageId.DESIGN, StageId.PLAN, StageId.IMPLEMENT, StageId.ADVERSARIAL_REVIEW",
    "StageId.RE_DERIVE, StageId.IDEATE, StageId.RESEARCH, StageId.DESIGN, StageId.PLAN, StageId.IMPLEMENT, StageId.ADVERSARIAL_REVIEW",
)
open(path, "w").write(content)
