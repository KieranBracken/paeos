path = "/Users/bob/GitHub/paeos/runtime/integrations/chat_bridge.py"
content = open(path).read()
old = "if package.role != Role.BUILDER:"
new = "if package.stage not in (StageId.IMPLEMENT, StageId.RESEARCH, StageId.CRITIQUE, StageId.TRADEOFF):"
if old in content:
    open(path, "w").write(content.replace(old, new))
else:
    print("already patched?")
