# PAEOS-2: The Founder Workflow

> **Archival status:** Frozen derivation document, archived 2026-07-19 from the original
> derivation session (July 2026). Preserved as derived and as reviewed by PAEOS-3.5 —
> NOT updated for subsequent amendments (notably: the intervention-decay theorem is
> re-read by the Ω-14/Ω-19/Ω-22 synthesis in reviews/6-hidden-assumptions.md, which
> shows the founder channel is also the soundness anchor and must never decay to zero).
> Effective current law is PAEOS-4 as amended. Do not edit: changes falsify the lineage.

---

**A necessary reframing before deriving anything.** In a pipeline, a "workflow" is a sequence of stages. In a reconciliation system, there are no stages to sequence — the store reconciles continuously, in parallel, wherever there are unreconciled goals. So the question "how does work flow?" decomposes into two derivable questions: **under what conditions does each activity exist at all** (planning, architecture, research, parallelism, intervention), and **what is the founder's interaction surface** with a system that otherwise runs itself. The workflow is not a sequence; it is a set of *existence conditions* plus an *event-driven founder loop*. Deriving it that way is forced by PAEOS-1: any fixed sequence would resurrect the pipeline the router exists to kill.

## 1. When planning exists, and when it does not

Define planning in kernel terms: *authoring a decomposition and evidence specs before building anything*. Then derive its existence condition from A1 (generation is cheap) and the router:

**Planning exists exactly where a wrong attempt costs more than the analysis that would have prevented it.** Three cases satisfy that inequality:

1. **Non-leaf goals** — structurally, you cannot reconcile what you haven't decomposed. Decomposition is the one form of planning that always exists.
2. **Irreversible leaves** — when reversal is expensive, speculation's cheapness is an illusion; the attempt itself is the cost. Pre-commitment analysis is justified.
3. **Verification-expensive leaves** — here the evidence spec doesn't come for free from existing checks, so *designing how you'll know it's right* must precede building. That design activity is planning, even though no schedule is involved.

Everywhere else — reversible, cheaply verified work, which is most of the goal tree's volume — **planning does not exist, because speculation dominates it**: building N candidates is cheaper than analyzing which candidate to build, and the surviving candidate's structure *is* the plan, discovered rather than authored. This is PAEOS-0's "building is plan-critique" made into a dispatch rule.

A corollary worth stating because it kills a whole institution: **estimation does not survive derivation.** Estimates exist in human organizations to allocate scarce human hours across a calendar. PAEOS's scarce resources are verification budget and founder decisions, neither of which estimation allocates. What replaces it is a **spend cap**: each goal carries a budget bound (tokens, wall-clock, verification passes) set by the router quadrant, and a goal that exhausts its cap without promoting files an Incident rather than silently overrunning. You never ask "how long will this take?" — you declare "this is worth at most this much," and the system tells you if reality disagrees.

## 2. When architecture exists, and when it does not

Define architecture in kernel terms: *constraints emitted at a decomposition node that bind more than one child*. Then:

**Architecture exists exactly at goal-tree nodes where fan-out is high and reversal is expensive.** At a node whose children don't share constraints, there is nothing architectural to decide — the children are independent and the router treats them independently. At a node whose constraints bind many descendants, every constraint choice is multiplied by the subtree's size, which is precisely what makes it expensive to reverse — and expensive-to-reverse routes to maximum ceremony *by the matrix, not by policy*: rival decompositions, adversarial attack, tournament judgment, and (per §5) possibly a founder Decision.

Two consequences distinguish this from "architecture phase" thinking:

- **Architecture is a property of nodes, not a stage of projects.** The question "how much architecture does this project need?" has no answer; the question "is this node high-fanout and irreversible?" is answered per-node by the Router. A project whose tree has no such nodes legitimately has no architecture activity, and that is correct, not negligent.
- **Architecture is standing and expirable, not historical.** An architectural constraint is bound (I2) to the evidence that justified it — the scale assumptions, the vendor benchmark, the market signal. When that bound state changes, the evidence expires, the node's `verified` status regresses, and the architecture is *re-reconciled*, not archaeologically excavated years later. What the industry calls an ADR is, in PAEOS, just the Evidence and constraint artifacts at these nodes — with the crucial difference that expiry makes them load-bearing rather than commemorative. This is the mechanism that would have made the Sentium excavation unnecessary: the months spent recovering buried decisions is the scar this section is derived from.

## 3. When research exists

Define research: *a goal whose desired delta is Evidence about the world rather than change to the world*. Then from I1 (promotion requires evidence) the existence condition falls out:

**Research exists exactly when a promotion is blocked by missing evidence about the world — never as a phase.** Three blockers generate all research:

1. The **Router cannot classify** a goal (its verifiability or reversibility is itself unknown).
2. A **Judge cannot select** among candidates (the tournament is evidence-starved).
3. A **Decomposer cannot bound constraints** (the architectural node lacks grounding — the trace-B case above).

Research is therefore always *pull-driven by a specific blocked promotion*, with a named consumer waiting on the answer. Speculative, phase-style research ("first, two weeks of investigation") does not survive derivation, and I2 explains why: evidence about the world expires as the world changes, so evidence gathered ahead of need tends to expire before use — negative expected value except where an irreversible decision is already visible on the horizon. Research produced without a consumer is scope creep the intent-conservation audit should flag.

## 4. When many agents exist, and when one does

From A3 (errors decorrelate across stances, not within them) and A1 (generation cheap, verification scarce), the fan-out rule derives cleanly, and what actually bounds it is worth stating:

**Parallel generation exists when candidate errors decorrelate AND selection is cheaper than generation.** Both conjuncts are load-bearing. If the task is so constrained that N agents produce near-identical output, parallelism buys nothing — the errors are correlated across attempts, so best-of-N ≈ best-of-1. If no Judge can cheaply select a winner, tournaments just multiply unverified candidates. So: tournaments live in the *generation-uncertain, verification-cheap* region.

**Adversarial pairs exist where verification is expensive.** When no mechanical check exists, independence (I3) must come from stance diversity — a Builder and an Adversary — because that is the only remaining source of decorrelation.

**A single agent exists in three derivable cases:**
1. **Mechanically verifiable work** — the check suite *is* the adversary; a second mind adds correlated redundancy, not independence. One Builder plus EXEC.
2. **Integration** (I9) — coherence is the property that fragments under parallelism; single-threaded by invariant.
3. **Degenerate candidate distributions** — the low-entropy tasks above, where fan-out is provably wasted.

And the true bound on parallelism, which inverts the industry's intuition: **fan-out is limited by verification budget, not generation budget.** Tokens are cheap; Judge attention and evidence production are the scarce inputs (A1). N is set per-quadrant by the marginal value of best-of-N against the cost of judging N — which is why N is a bootstrap parameter, tuned by tournament, not a constant chosen today. This also means the system has a natural work-in-progress limit: not an imposed Kanban rule, but the point where unverified `executed` goals saturate verification capacity. WIP limits re-derive as a resource constraint rather than a ritual.

## 5. When the founder is required

From A4, founder involvement exists exactly where one of the four irreplaceable inputs is consumed, and the kernel makes each occasion precise:

1. **Intent authoring** — a new root Goal. The founder's largest and rarest act.
2. **The irreducible quadrant** — irreversible + unverifiable decisions *not already covered by policy*. If a Protocol or prior Amendment covers the class, no escalation occurs; the escalation itself is definitionally a policy gap.
3. **Constraint loosening** (I10) — relaxing an inherited constraint is reversing a founder commitment, which only the founder may do.
4. **Taste starvation** — a Judge facing a taste-laden verdict with no adequate precedent in the taste corpus. The resolution enters the corpus, so the same starvation cannot recur for that class.
5. **External ground truth** — evidence only the founder's contact with users, market, or money can produce.

Everything else — and the claim is exactly this strong — involves no founder. Two consequences follow:

**Founder intervention decays by construction.** I8 forces every Decision to close with an Amendment or an explicit one-off; cases 2–4 each close their own class when they fire. For a stationary problem domain, the intervention rate falls monotonically toward the floor set by cases 1 and 5 — intent and ground truth, the two inputs no policy can absorb. The system converges on founder-as-oracle, and the *rate of convergence* is itself observable: a flat intervention rate means the Steward is failing to mine Decisions into policy, which is an Incident. *(Archival note: PAEOS-3.5's Ω-14/Ω-19/Ω-22 later show this decay must have a floor above zero — the founder channel is also the only non-Goodhartable soundness anchor — so "minimize intervention" must be read as "spend it only on soundness, taste, and ground truth," never eliminate it.)*

**The clean-intent invariant: the founder never edits work products directly.** This needs deriving because it will chafe daily. A founder hotfix injects intent that is undecomposed, has no evidence spec, cites no parent clause, and carries its rationale only in the founder's head — invisible to the conservation audit, uncompilable into future contexts (I6), and unrecoverable after the fact (A2; the Sentium excavation, again, is the scar). So founder dissatisfaction has exactly three legitimate entry points: file an **Incident** ("this output is wrong"), contribute a **taste exemplar** ("this is what right looks like"), or amend a **constraint**. The system then fixes its own output, and the *reason* survives as an artifact. A direct edit is itself an Incident — evidence of a gap in the ABI.

## 6. How goals decompose — the criterion

PAEOS-1 gave the mechanism (recursive reconciliation, serving-clauses, aggregation contracts). What remained under-derived is the *criterion*: among the many valid decompositions of a goal, which should a Decomposer prefer? It falls out of the router in one sentence:

**Decompose to concentrate irreversibility and distribute verifiability.** Since ceremony cost scales with the irreversible surface, isolate irreversible choices into the smallest possible dedicated goals — pay tournament-and-Decision ceremony on a point, not on an area. Since autonomous throughput scales with independently verifiable leaves, cut boundaries along *verification seams*: each child's evidence spec should be executable without its siblings. A decomposition that forces children to be verified jointly has misplaced its cuts; joint verification is the tell that the boundary crosses a seam. The Adversary attacks proposed decompositions on exactly these two counts, plus intent conservation.

The recursion's floor is unchanged: a leaf is a goal one reconciliation loop can carry to `verified`.

## 7. The canonical founder workflow

The founder operates PAEOS through **five verbs**, all asynchronous, none scheduled:

1. **Author** — write a root Goal: desired delta, evidence spec, constraints. Rare; the highest-leverage hours the founder spends. Everything in §§1–6 executes downstream of this act without further touch.
2. **Resolve** — service the Decision queue. Batched, not interrupt-driven; each resolution ends in an Amendment or a recorded one-off (I8).
3. **Inject** — feed external ground truth into the store as highest-provenance Evidence: user feedback, revenue signal, a competitor's move. Continuous trickle; this is what keeps reconciliation aimed at the actual world.
4. **Curate** — extend the taste corpus when Judges starve, or proactively when the founder sees output that's *almost* right. Taste enters as data, never as interruption.
5. **Audit** — optionally walk integrated deltas and the intent-conservation report. Disagreement exits through the clean-intent invariant: Incident, exemplar, or constraint amendment — never a direct edit.

**Cadence derives from queue pressure, not calendar.** Sprints exist to allocate scarce human hours; PAEOS has none to allocate. What it has is a Decision queue whose latency blocks the most expensive subtrees — so the founder engages when *blocked-work cost exceeds engagement cost*, a quantity the system computes and pages on. In practice this converges to something resembling a short daily queue-service session plus rare deep sessions for root-goal authoring — but that shape is an *equilibrium of the pressure rule*, not a ritual, and it shifts as the intervention rate decays (§5).

**Founder time accounting at maturity:** almost everything in *Author* and *Inject* — intent and ground truth, the two channels that never close — with *Resolve* and *Curate* decaying toward zero and *Audit* discretionary. That is the "minimize intervention, maximize architectural quality" objective realized structurally: quality is guarded by ceremony concentrated at the nodes that need it (§2), intervention is spent only where A4 says it's irreplaceable.

## 8. Two traces — the router's spread

**Trace A — reversible, cheaply verified (the volume case).** *"Config flag rename."* Declared → Router classifies bottom-left → no planning (§1), no architecture (§2), no research (§3), single Builder (§4), checks run under EXEC → `executed` → check evidence promotes to `verified` → Integrator merges → `integrated`. No tournament, no Adversary, no founder. Minutes, fully autonomous. **Most of the goal tree, by count, is this trace.**

**Trace B — high-fanout, irreversible (the rare, expensive case).** *"Choose the multi-tenant data model."* Router classifies top-right of a high-fanout node → planning exists (§1, case 2–3) → research goals spawn against the Decomposer's blockers (§3) → three rival decompositions (§4: errors decorrelate on open design) → Adversary attacks each on irreversibility-concentration, verification seams, intent conservation (§6) → Judge selects against the taste corpus → an irreducible residual escalates as a Decision (§5, case 2) → founder resolves it in the next queue-service batch; the resolution amends policy with the tenancy principle → children inherit the constraint (I10) and fan out as Trace-A work.

The entire discipline of the system is visible in the contrast: **ceremony is a point mass at rare Trace-B nodes, not a coat of paint over everything** — which is precisely what every uniform methodology gets wrong in both directions at once (bureaucracy for Trace A, insufficient rigor for Trace B).

## 9. How the four activities interact — loop dynamics

Implementation, verification, evolution, and amendment are not stages; they are the two loops of PAEOS-1 coupled through the store, and their interaction has derivable dynamics:

- **Implementation ⇄ verification** is the promotion-and-regression economy: Builders push goals up the lattice, Evidence gates every step (I1), and expiry (I2) drags statuses back down as the world shifts under them. The system is never "done and drifting"; it is always re-truthing. Verification capacity, not generation capacity, sets throughput (§4), so the Steward's highest-value amendments are usually *cheaper evidence* — new checks that convert verification-expensive classes into verification-cheap ones, migrating whole goal classes from Trace B economics toward Trace A.
- **Implementation → evolution** through Incidents: every failure, cap-overrun, escalation, and founder direct-edit feeds the Steward.
- **Evolution → implementation** through Amendments: policy deltas recompile into every future context (I6), so a lesson learned once is learned by every subsequent agent. Amendments carry their own evidence specs, so a rule that doesn't earn its keep regresses and gets pruned like anything else — the constitution stays under its cap by selection, not restraint.
- **Self-application closes the loop:** a Constitution amendment is itself irreversible-ish and hard to verify, so the router sends it through Trace-B ceremony — including, at the limit, a founder Decision. Founder oversight of constitutional change is not a special rule; it falls out of the matrix.

The resulting maturation curve: early PAEOS runs hot — high incident rate, frequent escalation, heavy ceremony — and cools as scars accumulate into policy, checks accumulate into cheap verification, and exemplars accumulate into judgeable taste. The steady state is the §7 equilibrium: the founder authoring intent and injecting reality; everything else reconciling.

## 10. Autopsy — what died, what re-derived

| Legacy element | Verdict | Derivation |
|---|---|---|
| Standup | **Dead** | Coordination-by-meeting exists because human state is private; the store is shared truth (A2) |
| Sprint / iteration | **Dead** | Calendar allocation of scarce human hours; replaced by queue pressure (§7) |
| Estimation | **Dead** | Replaced by spend caps (§1); Shape Up's *appetite* is the one fragment that re-derives, as a budget bound |
| Backlog grooming | **Dead** | The goal tree plus router ordering; conservation audit kills zombie items automatically |
| Retrospective | **Re-derived** | Survives as the Steward — continuous, evidence-gated, with teeth (I7–I8), instead of a ceremony with none |
| Code review | **Re-derived** | Survives only as adversarial Evidence (I3); dead as ritual approval by a correlated peer |
| Definition of done | **Re-derived** | The evidence spec — mechanically enforced (I1) instead of aspirationally posted |
| WIP limits | **Re-derived** | The verification-budget bound (§4); a resource constraint, not a ritual |

That some fragments re-derive is a feature of the method, not a compromise: it means the derivation recovers what was load-bearing in legacy practice while discarding what was scaffolding for human limitations.

## The one-sentence version

**The PAEOS founder workflow is five asynchronous verbs — author intent, resolve decisions, inject ground truth, curate taste, audit deltas — over a system in which planning, architecture, research, and parallelism are not stages but existence-conditioned activities the router instantiates per goal, where ceremony concentrates as a point mass on rare irreversible nodes, where every founder intervention permanently closes its own class, and where the founder's residual role converges by construction to the two things no policy can absorb: intent and contact with reality.**
