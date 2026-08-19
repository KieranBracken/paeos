path = "/var/folders/b0/hb9_mxhn4nz09tzctglbjq6w0000gp/T/paeos-t-39f62f436e46-bridge-igabjyim/runtime/agents/__init__.py"
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
    # Insert before _DESIGN
    content = content.replace("_DESIGN = RoleSpec(", _RESEARCH + "\n\n_DESIGN = RoleSpec(")
    # Register in ROLE_SPECS
    content = content.replace(
        "    StageId.IDEATE: _IDEATE,",
        "    StageId.IDEATE: _IDEATE,\n    StageId.RESEARCH: _RESEARCH,",
    )

open(path, "w").write(content)
