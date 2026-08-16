path = "/var/folders/b0/hb9_mxhn4nz09tzctglbjq6w0000gp/T/paeos-t-39f62f436e46-bridge-igabjyim/runtime/context_compiler.py"
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
