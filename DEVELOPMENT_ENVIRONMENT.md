# PAEOS Development Environment

Date: 2026-07-18 · Companion to INSTALLATION_REPORT.md (skills). This document covers
everything else: CLI tooling, git, MCP, and the capability-coverage map.
Policy: fewer excellent tools; nothing installed without a named use during PAEOS-5.

## Installed capabilities

### Pre-existing (verified, no action)
| Tool | Version | Role |
|---|---|---|
| git | 2.39.5 (Apple) | store substrate (K4 §2.1 realization) |
| gh | 2.92.0 (2026-04) | GitHub ops for KieranBracken/paeos remote |
| ripgrep | 14.1.1 | text search across corpus/implementation |
| jq | 1.6 | JSON manipulation — kernel objects are JCS JSON |
| node/npm | 24.1.0 / 11.3 | skills CLI, potential implementation runtime |
| python3 | 3.10.13 (pyenv) | potential implementation runtime |
| Homebrew | 6.0.10 | package management |

### Added this session (with rationale)
| Tool | Version | Why (named PAEOS use) |
|---|---|---|
| **ast-grep** | 0.44.1 | structural/AST search & lint rules across languages — code navigation and pattern enforcement once implementation starts; language-agnostic, so not blocked on the G-ROOT language decision |
| **shellcheck** | 0.11.0 | shell is guaranteed in scope regardless of language choice: the null adapter, EXEC checks, and conformance harness are shell-level (K4 §12.5, B-07). Lint them from day one |
| **shfmt** | 3.13.1 | canonical formatting for the same shell surface |
| **fd** | 10.4.2 | fast file finding for fixture/corpus sweeps |
| **yq** | 4.53.3 | the backlog and future task tooling are YAML; first smoke test immediately found a real defect (backlog node-count 30 → actual 35, now fixed) — leverage demonstrated on install day |

### Deliberately NOT installed (with rationale)
- **MCP servers for development: zero.** Current 2026 guidance converges on 3–5 scoped
  servers (GitHub + Filesystem + Context7 as the common core) — but Claude Code's native
  tools already cover filesystem, `gh` covers GitHub, and WebSearch/WebFetch cover docs
  lookup. Every connected server costs context and audit surface; none pays for itself
  here today. Revisit trigger: recurring library-doc friction during kernel
  implementation → add Context7 only.
- **delta** (pretty diffs): the reviewer is an agent; plain `git diff` is sufficient. Future nicety.
- **semgrep / language linters / test frameworks / dependency inspection**: BLOCKED by
  design on the G-ROOT language constraint (founder judgment slot, package L-04). Choosing
  them now would front-run a founder decision.
- **pre-commit framework**: PAEOS's validator IS the hook system (K4 §11 WRITE
  validation); installing a foreign hook manager would duplicate a kernel organ.
- **tokei/scc/hyperfine**: no current use; hyperfine returns for Inv-12 performance work.
- **Vector/semantic code indexing**: repo is small; built-in Explore agent + ripgrep +
  ast-grep outperform an index at this scale.

## Configuration applied
- `git config core.fsync=committed` (repo-local) — the durability pin from
  reviews/5.5-implementation-audit/03_BOOT_SEQUENCE.md.
- `.gitignore` created (.DS_Store, node_modules/, *.log, .scratch/).
- Homebrew tap-trust: installs ran with a one-invocation
  `HOMEBREW_NO_REQUIRE_TAP_TRUST=1` bypass because pre-existing third-party taps
  (timescale, cloudflare) are untrusted under Homebrew 6 and hard-fail unrelated
  installs. **No persistent trust was granted** — founder should either
  `brew trust` or `brew untap` those taps at leisure.
- Repo state noted: single commit `da4f471 "firrst commit"` holds the corpus; untracked:
  `.agents/`, `.claude/`, `INSTALLATION_REPORT.md`, `skills-lock.json`, plus this file
  and `.gitignore`. Committing them is a founder act (recommended: yes, all — project
  skills and env docs should travel with the repo).

## Capability coverage map (requested categories)
| Category | Coverage | Status |
|---|---|---|
| Skills | Superpowers v6.1.1 + skill-creator (see INSTALLATION_REPORT.md) | ✅ |
| MCP servers | zero by design (rationale above) | ✅ decided |
| Git integration | git + gh + remote + fsync pin | ✅ |
| Search tools | ripgrep + fd | ✅ |
| Tree/AST analysis & semantic search | ast-grep + built-in Explore agent | ✅ |
| Diff tooling | git diff (+ constitutional-diff skill, planned — see design/PAEOS-skills-gen1.md) | ✅ / planned |
| Testing integrations | conformance harness IS the deliverable (T-HARNESS node); language-level runner blocked on G-ROOT | ⏸ by design |
| Formatting / linting | shellcheck + shfmt now; language linters post-G-ROOT | ✅ partial, gated |
| CI helpers | none yet — see recommendations | ⏸ |
| Documentation tooling | excluded (prose; corpus is hand-governed) | ✅ decided |
| Dependency inspection | post-G-ROOT | ⏸ gated |
| Repository indexing | not needed at this scale | ✅ decided |

## Remaining recommendations
1. **Founder:** commit the untracked environment files; resolve the two untrusted brew taps.
2. **CI (after Wave 3):** GitHub Actions workflow running validator + conformance
   levels on push — the repo has a remote, so the portability CI (PAEOS-0 M4) has a
   natural home. Do not build CI before T-HARNESS exists; CI is the harness's shell.
3. **Post-G-ROOT language decision:** install that language's formatter, linter, test
   runner, and dependency auditor in one pass; add gitleaks before the repo gains
   secrets exposure (adapter signing keys must never be committed — K4 §13 trust roots
   hold public keys only).

## Future upgrades
Context7 MCP (on doc-friction trigger) · delta (reviewer comfort) · hyperfine
(Inv-12 benchmarks) · semgrep rulepack expressing K-invariants as static checks over
kernel code (post-language; would mechanize part of the validator-bypass architectural
test from the 5.5 audit).
