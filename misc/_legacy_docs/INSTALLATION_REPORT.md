# PAEOS Development Environment — Installation Report

Date: 2026-07-18 · Engineer: Claude (Fable 5) acting as environment engineer
Policy applied: minimum set, production quality, actively maintained, no overlap, no
external methodology lock-in (PAEOS derives its own).

---

## Installed: 2 items (deliberately)

### 1. Superpowers — v6.1.1
- **Source:** `superpowers@claude-plugins-official` (Anthropic official plugin marketplace; upstream `obra/superpowers`, Jesse Vincent / Prime Radiant)
- **Scope:** user-level plugin, Status: enabled ✔ (verified via `claude plugin list`)
- **Skills installed (14, verified on disk):** brainstorming, dispatching-parallel-agents, executing-plans, finishing-a-development-branch, receiving-code-review, requesting-code-review, subagent-driven-development, systematic-debugging, test-driven-development, using-git-worktrees, using-superpowers, verification-before-completion, writing-plans, writing-skills
- **Maintenance:** v6.1.1 released 2026-07-02 (16 days ago); continuous releases through 2026; listed on Anthropic's official marketplace since Jan 2026; ~190K installs on its flagship skill. The healthiest project in the ecosystem by every signal.
- **Trigger conditions:** skill-specific frontmatter matching (e.g., systematic-debugging fires on bug-hunting language; using-git-worktrees on parallel-work needs); `using-superpowers` meta-skill loads at session start via plugin hook.
- **Why selected:** explicitly mandated; independently, it wins every category it competes in (its debugging and review skills have 10–50× the installs of alternatives and are the reference implementations of the genre).
- **Why it beats alternatives:** addyosmani/agent-skills (debugging, planning — 13–14K installs) and wshobson/agents (debugging-strategies — 10K) duplicate Superpowers coverage at lower depth and adoption; installing any of them would violate the no-overlap rule.
- **Expected PAEOS value, by skill class:**
  - **High:** systematic-debugging (kernel/validator bug hunts), verification-before-completion (evidence-before-claim discipline — philosophically identical to K1), using-git-worktrees + finishing-a-development-branch (Wave 1's five parallel pure-module tracks), dispatching-parallel-agents (backlog wave execution), test-driven-development (fixture-first Sonnet implementation matches F-*→I-* package structure exactly).
  - **Medium:** requesting/receiving-code-review (worker-package review checklists).
  - **Dormant for PAEOS work (see Compatibility):** brainstorming, writing-plans, executing-plans, subagent-driven-development.

### 2. skill-creator — Anthropic official
- **Source:** `anthropics/skills@skill-creator` via `npx skills add` (repo: github.com/anthropics/skills, Anthropic-maintained, 141K+ stars)
- **Scope:** project-level: `.agents/skills/skill-creator/` (universal, readable by Codex/Cursor/Gemini CLI/Antigravity +12 runtimes) with symlink `.claude/skills/skill-creator` for Claude Code. Frontmatter verified valid.
- **Purpose:** create, edit, benchmark, and eval skills; optimize trigger descriptions.
- **Trigger conditions:** requests to create/modify/test/benchmark a skill.
- **Why selected:** PAEOS's userland **is** skills — G-ROLES bodies, genesis protocols, and every post-genesis Steward-authored skill are SKILL-shaped policy artifacts. An Anthropic-official authoring+eval discipline for them is the single highest-leverage install for this project, and its eval/benchmark machinery supports PAEOS's tournament-evolution of skills.
- **Why it beats alternatives:** the only official skill-authoring tool; community equivalents are wrappers around it.
- **Maintenance:** Anthropic official repository, actively maintained.
- **Bonus:** the `.agents/skills/` universal layout is runtime-portable in exactly the way PAEOS's adapter model wants — project skills travel with the repo across all target runtimes.

## Overlap analysis (installed set + built-ins)

No name collisions anywhere. Functional overlaps, with resolution:

| Overlap | Resolution |
|---|---|
| Superpowers `requesting/receiving-code-review` vs built-in `/code-review` | Complementary: built-in finds defects mechanically; Superpowers skills govern the *process* of asking/responding. Keep both; built-in remains the defect-finding tool of record. |
| Superpowers `verification-before-completion` vs built-in `/verify` | Complementary: one is a discipline (claim nothing unverified), the other a harness (drive the app). Keep both. |
| Superpowers `writing-plans`/`executing-plans` vs built-in plan mode | Built-in plan mode + PAEOS backlog packages are the tools of record for PAEOS (see Compatibility). |
| Superpowers `writing-skills` vs `skill-creator` | Real overlap, split retained deliberately: `skill-creator` (official, has evals/benchmarks) is primary for PAEOS policy-artifact skills; `writing-skills` applies only when editing Superpowers-idiom process skills. |

## Compatibility issues

1. **Methodology tension (flagged, managed):** Superpowers ships a linear 5-phase discipline (brainstorm → design → plan → code → verify) — precisely the pipeline PAEOS-0 demolished in favor of the evidence-state router. Its four process skills (brainstorming, writing-plans, executing-plans, subagent-driven-development) are therefore **superseded by PAEOS-2 for PAEOS implementation work** and should be treated as dormant reference material there; they remain useful for non-PAEOS projects. The craft skills (debugging, TDD, worktrees, review, verification) carry no such conflict — they are stance-level, not pipeline-level, and slot cleanly under PAEOS protocols. No mechanical conflict exists (skills fire on trigger, and PAEOS work will trigger the craft skills, not the pipeline ones).
2. **Session restart required:** plugin and project skills register at session start. Installed and structurally verified this session; they become invocable from the next session launched in this project. This is a Claude Code loading property, not an installation failure.

## Considered and REJECTED

| Candidate | Installs | Rejection reason |
|---|---|---|
| mattpocock/skills@improve-codebase-architecture | 488K | **Methodology lock-in:** encodes Ousterhout deep-module philosophy, generates ports-&-adapters designs, writes ADR-style RFCs — external architectural opinions, explicitly excluded. Highest-installed candidate rejected on principle; PAEOS derives its own architecture rules. |
| wshobson/agents@architecture-patterns / @architecture-decision-records | 19K / 11K | Pattern-catalog opinions; ADR machinery duplicates PAEOS's own Decision/Amendment objects. |
| othmanadi/planning-with-files | 38K | Imposes a planning methodology; PAEOS-2 derived its own, and built-in plan mode covers mechanics. |
| addyosmani/agent-skills (debugging, planning) | 13–14K | Quality source, but 100% overlapped by Superpowers at lower depth. No-overlap rule. |
| anthropics/skills@webapp-testing | 117K | Official and good, but PAEOS's kernel is CLI-level — no web surface to test. Revisit only if a workload needs browser automation. |
| anthropics/skills@mcp-builder | — | PAEOS adapters are not MCP servers. No current need. |
| anthropics/skills document suite (docx/pdf/pptx/xlsx) | — | Prose/document production — out of scope by the "engineering, not prose" criterion. |
| sickn33/antigravity-awesome-skills@context-* / davila7 context skills | ≤1.2K | Junk tier by adoption; context management is covered by Claude Code built-ins and, architecturally, by PAEOS's crash-only artifact design. |
| jeffallan/claude-skills@debugging-wizard, wshobson parallel-debugging | ≤10K | Overlap with systematic-debugging. |

**Categories intentionally left uninstalled:** codebase navigation & large-repo reasoning (built-in Explore agent + Agent tool are stronger than any registry offering); spec validation (PAEOS's validator IS the project — importing one would be lock-in); documentation generation (prose, excluded); context management (built-ins + crash-only design).

## Installation failures
None. Both installs exited 0 on first attempt and verified on disk.

## Recommendations
1. Start the next working session from `/Users/bob/GitHub/paeos` to activate both installs; smoke-test with a trivial invocation of systematic-debugging and skill-creator before Wave 1 dispatch.
2. Run `npx skills check` periodically (or before each wave) for skill-creator updates; `claude plugin list` shows Superpowers version drift.
3. When G-ROLES/genesis-skill authoring begins, use skill-creator's eval harness to baseline each policy skill — this doubles as seed data for PAEOS's own tournament evolution.
4. Do not add further skills without a demonstrated gap during implementation — the environment is intentionally two items plus built-ins, and every addition taxes every session's context (the K10 argument applies to the dev environment too).
