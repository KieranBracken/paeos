path = "/var/folders/b0/hb9_mxhn4nz09tzctglbjq6w0000gp/T/paeos-t-39f62f436e46-bridge-igabjyim/tests/runtime/test_soft_loop.py"
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

open(path, "w").write(content)
