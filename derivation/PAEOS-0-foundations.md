# PAEOS-0: The Methodology

> **Archival status:** Frozen derivation document, archived 2026-07-19 from the original
> derivation session (July 2026). Preserved as derived and as reviewed by PAEOS-3.5 —
> NOT updated for subsequent amendments. Effective current law is PAEOS-4 as amended
> (reviews/3.5-adversarial/, reviews/5.5-implementation-audit/, SPEC-CLARIFICATIONS).
> Do not edit: changes to this document falsify the derivation lineage.

---

## First principles: what is actually true

Strip away every inherited workflow and five constraints remain. Everything else should be derived from these, and anything that can't be derived from these is cargo cult.

1. **Generation is cheap; verification and judgment are scarce.** The cost structure of software engineering has inverted. Every legacy workflow (waterfall, agile, code review) was designed for a world where writing code was expensive and rework was catastrophic. That world is gone. The bottleneck is now knowing whether output is correct and whether it's the *right* output.
2. **Model context is ephemeral and lossy; the filesystem and git are durable.** Any knowledge that lives only in a conversation is already lost.
3. **Errors within one model/framing are correlated; across models, framings, and adversarial stances they are less correlated.** This is the only rigorous justification for multi-agent anything.
4. **The founder has exactly four irreplaceable inputs:** intent, taste, contact with external ground truth (users, market, money), and accountability for irreversible actions. Everything else a founder does today is a workaround for tool limitations.
5. **Runtimes churn; artifacts persist.** Claude Code, Cursor, Codex, Gemini CLI, OpenHands are all temporary. Plain text, git, and shell-executable checks are the only stable substrate.

And one entropy law: **any rule not enforced mechanically decays.** Instructions in prose are suggestions; only executable checks are invariants.

## Challenging the assumptions, one by one

**Linear phases are wrong — but not for the reason people think.** Plan→implement→review assumes rework is expensive, so you front-load thinking. When implementation costs minutes, *building the thing is often the cheapest way to evaluate the plan*. But the opposite extreme ("just let agents run") fails because verification cost didn't drop. The resolution: replace **temporal phases** with **evidence states**. Work doesn't move through stages; it moves through confidence levels — *speculated → executed → verified → integrated* — and the gate between states is evidence (a passing check, a survived critique), never the calendar or the sequence. Multiple states can be in flight simultaneously; three speculative implementations can exist while the plan is still being critiqued, and the implementations *are* plan-critique.

**Planning survives, but plans-as-prose die.** A prose plan is a prompt that decays the moment it's written. A plan should be a **falsifiable artifact**: interfaces, invariants, executable acceptance checks, and an explicit list of what would prove the approach wrong. If a plan can't fail, it isn't a plan; it's a vibe.

**Review as diff-reading dies.** An AI reviewing another AI's diff with the same training distribution shares its blind spots — this is verification theater. Real review is (a) **execution-grounded**: run the thing, exercise the behavior, don't read about it; (b) **adversarial**: the reviewer's job is to construct a failing input, not to approve; (c) **shifted left into the substrate**: types, property tests, and invariant checks catch at generation time what review catches too late. Cross-model critique is worth paying for only where axiom 3 applies — judgment-heavy decisions — not for mechanical correctness, which checks handle for free.

**Prompting dies as a craft.** Handwritten prompts are unversioned, unportable, and unreproducible. In PAEOS, prompts are **compiled, not written**: assembled deterministically from artifacts (constitution + task spec + relevant ADRs + current evidence state). The skill of "prompt engineering" becomes the engineering of the artifact base the compiler draws from.

**Context management dies; artifact management replaces it.** The design goal isn't clever compaction — it's making context *not matter*. Borrowing from crash-only software: **every agent must be killable and restartable from files alone**, with zero loss. If killing an agent mid-task loses information, that information should have been an artifact. The repo is the memory; context windows are a cache.

**"One AI owns one task" is wrong, but so is multi-agent maximalism.** Fan-out has a real cost: coordination overhead, fragmented context, and re-derivation of state by every spawned agent. The principled rule: **parallelize where errors are uncorrelated and selection is cheap; single-thread where integration matters.** Concretely — tournaments (N attempts, adversarial judge picks one) for exploration and hard problems; a single integrating mind for merging, because architectural coherence is precisely the property that fragments under parallelism. Specialization should be by *stance* (builder, adversary, judge, historian) rather than by domain, because stance diversity is what decorrelates errors.

**"Minimize founder intervention" is subtly the wrong objective.** A zero-intervention system drifts from intent — you'd get a beautifully architected product nobody asked for. The correct objective is **maximum leverage per intervention**: few interventions, each one setting policy rather than deciding an instance. Every escalation to the founder should end by amending an artifact so that *class* of question never escalates again. Founder interaction is batched and asynchronous — a decision queue, not interrupts.

**Even "maximize architectural quality" needs challenging.** Quality is instrumental. The terminal value for a solo founder is **low cost of change** — option value. Architecture that maximizes elegance but requires elaborate ceremony to modify is a failure by the actual objective.

## The single biggest structural conclusion: route, don't pipeline

There is no one optimal workflow, because tasks differ along two axes that dominate everything else:

| | **Cheap to verify** | **Expensive to verify** |
|---|---|---|
| **Reversible** | Full autonomy, tournament-style, no gates | Autonomy + adversarial critique before integration |
| **Irreversible** | Autonomy + mechanical gate (checks must pass) | The *only* quadrant requiring founder judgment |

The heart of PAEOS is therefore a **router**, not a pipeline: classify each task by verifiability and reversibility, then apply the cheapest workflow that quadrant permits. Most legacy methodology is the top-right quadrant's ceremony applied indiscriminately to everything.

## Therefore: how PAEOS should be designed

This is the actual answer to the question — the methodology that produces the OS.

**1. Self-hosting from commit zero.** PAEOS must be built *using* PAEOS. The first artifact is a minimal kernel (a page of constitution, a router, one executable check), and it is immediately used to build its own next version. Any methodology you wouldn't submit to yourself is untested theory. Dogfooding isn't a nicety here; it's the only empirical loop available to a solo founder.

**2. Failure-driven derivation — no rule without a scar.** Every rule in PAEOS must trace to an observed failure it prevents. The months of Sentium excavation are the seed corpus: mine it into an incident catalog first, then derive rules from incidents. A rule without a failure story doesn't ship. This is what keeps PAEOS from becoming the very thing this document exists to forget — an accretion of plausible-sounding best practices.

**3. Every component ships with its own falsifier.** Each rule states: what failure it prevents, what observation would prove it useless, and its removal test. Schedule periodic pruning passes where an adversarial agent argues for deleting each rule. Rules that haven't fired in N cycles are deleted. An OS that only grows is a dying OS.

**4. A hard minimality budget, because the OS taxes every prompt.** This is unique to AI-native systems: every line of the constitution is loaded into every future context window. Kernel size is capped (~2 pages of invariants). Adding a rule requires removing one or explicitly paying against the budget. Bulk goes in **skills/protocols loaded on demand by the router**, never in the always-loaded kernel.

**5. Kernel/userland/adapter split, enforced by CI.** The kernel is invariants in plain markdown; userland is protocols and skills as markdown + shell-executable checks; adapters are thin per-runtime shims (a CLAUDE.md generator, a Cursor rules generator, etc.). The portability test is mechanical and continuous: *the same task spec must produce semantically equivalent behavior on at least two runtimes.* Anything that can't survive that test gets demoted from the spec to an adapter. This is what makes PAEOS an OS rather than a Claude Code config.

**6. Evolution by tournament, not by argument.** When unsure between two protocols (e.g., "plan-first" vs. "three speculative builds"), don't debate — run both on real tasks, judge blind, amend the constitution with the winner *and the evidence*. The OS's amendment log becomes its own training corpus.

**7. The founder's design-time role: write the constitution's invariants, then handle exceptions.** During PAEOS's construction the founder makes exactly the four irreplaceable contributions: intent (what the OS is for), taste (what "good" looks like, encoded as judgeable examples rather than adjectives), ground truth (does it actually make Sentium-class work better), and sign-off on irreversible structural choices. Everything else — drafting rules, testing protocols, writing adapters — is done by agents under the bootstrap kernel.

## The one-sentence version

**PAEOS should be designed as a small, self-hosting, falsifiable constitution of plain-text artifacts and executable checks — organized around evidence states and a verifiability×reversibility router instead of phases — evolved by failure-driven amendment and tournament selection, with the founder as a batched exception-handler whose every intervention amends policy rather than deciding an instance.**

The immediate next step this methodology implies: not designing PAEOS's components, but mining the Sentium excavation into the incident catalog — because under rule 2, that catalog is the raw material from which every legitimate rule must be derived.
