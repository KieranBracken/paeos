"""One-shot generator for operations/archive/PAEOS_19_LAYER_LIFECYCLE_EXTRACTION_v1.md.

Forensic, disk-to-disk: embeds byte-exact slices of the two sources. No interpretation.
Run: .venv/bin/python operations/_gen_freeze_v1.py

AUTHORITY NOTE (2026-08-19): the output is a DERIVED RESTATEMENT of the canonical sources.
operations/ENGINEERING_LIFECYCLE.md (v1.3) is the canonical L01-L19 baseline; the output
document carries NO independent authority. It was historically named "Canonical 19-Layer
Freeze"; that name implied primacy and was retired. Do NOT regenerate over the archived
provenance header (it is added manually after generation). See PAEOS_HALLUCINATION_CHECKER_NOTEBOOK.md Entry 146.
"""
import hashlib
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LC = ROOT / "operations/ENGINEERING_LIFECYCLE.md"
YM = ROOT / "operations/WORKFLOW_STATE_MACHINE.yaml"

lc_text = LC.read_text()
ym_text = YM.read_text()
lc_lines = lc_text.splitlines()
ym_lines = ym_text.splitlines()
lc_hash = hashlib.sha256(lc_text.encode()).hexdigest()
ym_hash = hashlib.sha256(ym_text.encode()).hexdigest()

LC_HEAD = re.compile(r"^(#{2,4})\s+(L(0?[1-9]|1[0-9]))\b(.*)$")
YM_HEAD = re.compile(r"^  (L(0?[1-9]|1[0-9])):\s*$")

layer_heads = [
    (i, m.group(2))
    for i, ln in enumerate(lc_lines)
    if (m := LC_HEAD.match(ln))
]
state_heads = [
    (i, m.group(1))
    for i, ln in enumerate(ym_lines)
    if (m := YM_HEAD.match(ln))
]


def lc_section(idx: int) -> str:
    s = layer_heads[idx][0]
    e = layer_heads[idx + 1][0] if idx + 1 < len(layer_heads) else len(lc_lines)
    return "\n".join(lc_lines[s:e]).rstrip()


def ym_section(idx: int) -> str:
    s = state_heads[idx][0]
    e = state_heads[idx + 1][0] if idx + 1 < len(state_heads) else len(ym_lines)
    return "\n".join(ym_lines[s:e]).rstrip()


parts: list[str] = []
p = parts.append

p("# PAEOS 19-Layer Lifecycle Extraction (ARCHIVED / DERIVED — generated; provenance header added manually)")
p("")
p("**Nature of this document:** forensic extraction ONLY. No interpretation, no amendment")
p("proposals, no reconciliation of conflicts, no inference from implementation behavior.")
p("Where authoritative sources conflict, this document records")
p("`CANONICAL CONFLICT — REQUIRES RESOLUTION` and takes no side.")
p("")
p("## Frozen corpus (source_precedence / source_hash)")
p("")
p("| Precedence | Source | SHA-256 | Status recorded in source |")
p("|---|---|---|---|")
p(f"| 1 | operations/ENGINEERING_LIFECYCLE.md | `{lc_hash}` | FROZEN v1.0 (2026-07-20); CER rules v1.2 founder-ratified 2026-07-27 |")
p(f"| 2 | operations/WORKFLOW_STATE_MACHINE.yaml | `{ym_hash}` | v1.1, frozen: true, founder-ratified 2026-07-21 |")
p("")
p("Extraction date: 2026-08-19. Extractor: mechanical script (disk-to-disk, byte-exact slices);")
p("every layer section and YAML state block below is a verbatim slice of the hashed source.")
p("")
p("## Canonical layer sequence (in source order)")
p("")
p("L01 Intake · L02 Triage · L03 First-Principles Re-Derivation · L04 Ambitious Ideation ·")
p("L05 Frontier Research · L06 Trade-off Analysis · L07 Trade-off Mitigation · L08 System Design ·")
p("L09 Multi-Perspective Critique · L10 Adversarial Review · L11 Formal Planning ·")
p("L12 Branch Implementation · L13 Verification · L14 Independent Audit ·")
p("L15 Documentation & Ledger · L16 Promotion Decision ·")
p("L17 Retrospective + Constitutional Review · L18 Knowledge Extraction · L19 Constitutional Evolution")
p("")
p("---")
p("")
p("# Part A — Prose corpus, verbatim (ENGINEERING_LIFECYCLE.md)")
p("")
for idx, (lineno, lid) in enumerate(layer_heads):
    p(f"## {lid} (source line {lineno + 1})")
    p("")
    p("```markdown")
    p(lc_section(idx))
    p("```")
    p("")

pre_end = state_heads[0][0] if state_heads else len(ym_lines)
p("---")
p("")
p("# Part B — Machine-executable companion, verbatim (WORKFLOW_STATE_MACHINE.yaml)")
p("")
p("## B.0 Top-level rules (ceremony depth / discharge machinery), verbatim")
p("")
p("```yaml")
p("\n".join(ym_lines[:pre_end]).rstrip())
p("```")
p("")
for idx, (lineno, sid) in enumerate(state_heads):
    p(f"## B.{idx + 1} — YAML state `{sid}` (source line {lineno + 1})")
    p("")
    p("```yaml")
    p(ym_section(idx))
    p("```")
    p("")

p("---")
p("")
p("# Part C — Conflict register (recorded, NOT resolved)")
p("")
p("This Freeze does not adjudicate. Step 2 (conformance map) and Step 3 (founder decisions)")
p("own interpretation. Flags only:")
p("")
p("1. **C-01 — Prose vs YAML divergences:** any semantic difference between a Part A layer")
p("   section and its Part B state block is `CANONICAL CONFLICT — REQUIRES RESOLUTION`.")
p("2. **C-02 — Secondary-source numbering:** documents outside this corpus (backlog/research")
p('   reconstructions; IPs describing VERIFY as "stage 11", adversarial review as "stage 12",')
p('   seal as "stage 14", evolution as "15–19") use numbering inconsistent with the frozen')
p("   corpus. Lowest authority, excluded by design; no resolution offered here.")
p("3. **C-03 — Ceremony-depth legality questions** (who assigns depth, what discharge evidence")
p("   suffices, whether substantive L07 requires substantive L06): the frozen corpus states the")
p("   rules; applying them to historical runs is a Step 2/3 function, not a Freeze function.")
p("")
p("---")
p("End of Freeze v1.0.")

dest = ROOT / "operations/archive/PAEOS_19_LAYER_LIFECYCLE_EXTRACTION_v1.md"
dest.write_text("\n".join(parts) + "\n", encoding="utf-8")
print("written:", dest, dest.stat().st_size, "bytes")
print("layers:", len(layer_heads), "| yaml states:", len(state_heads))
sizes = [len(lc_section(i)) for i in range(len(layer_heads))]
print("prose section sizes (min/avg/max):", min(sizes), sum(sizes) // len(sizes), max(sizes))
