# PAEOS-3: Bootstrap

> **Archival status:** Frozen derivation document, archived 2026-07-19 from the original
> derivation session (July 2026). Preserved as derived and as reviewed by PAEOS-3.5 —
> NOT updated for subsequent amendments (notably: PAEOS-5.5 B-03 makes G1/G2 a single
> atomic batch and adds the meta-schema sentinel; the genesis record schema is formalized
> in PAEOS-4 §13). Effective current law is PAEOS-4 as amended. Do not edit: changes
> falsify the derivation lineage.

---

**The framing that makes this derivation different from the previous three.** PAEOS-0/1/2 derived a system that legitimates everything through its own machinery: artifacts gate on evidence, policies require scars, prompts must be compiled, changes flow through Amendments. Bootstrap asks how such a system can begin — and the honest starting point is that it *cannot*, by its own rules. That impossibility is not a flaw to be papered over; it is the central object of this derivation, and resolving it correctly determines everything else.

## 1. The bootstrap paradox, stated precisely

**Every mechanism that legitimates artifacts is itself an artifact.**

Unroll it: no agent may act without a compiled context (I6) — but the Compiler is an artifact someone must build. No policy may exist without a scar and falsifier (I7) — but the rule *requiring* scars is itself a policy, admitted by whom? Policy changes only via Amendment — but Amendments are produced by the evolution loop, which requires a Steward, which is a Role, which is a Policy, which requires an Amendment to exist. No status promotes without Evidence (I1) — but the validator that recognizes Evidence must first be written by something ungoverned. The empty repository contains no authority by which the first byte can be legitimate.

Every real bootstrap in computing and law has faced exactly this circle, and they all resolved it the same way:

- The first compiler for a language is written in a *different* language — cross-compilation — after which the language compiles itself and the host toolchain is discarded.
- A blockchain's genesis block is not validated by the consensus rules; it is hardcoded, and every subsequent block is validated against the chain it anchors.
- A constitution is never ratified by its own procedures. The convention that writes it is extra-constitutional; legal theory calls the presupposed founding norm the *Grundnorm*. The founding act is outside the order it creates — necessarily, not accidentally.

**Resolution: PAEOS is cross-compiled.** The host toolchain is *the founder plus a raw frontier runtime* — Claude Code running Fable with no PAEOS governing it, which is literally the situation producing this document. This host constitutes a **genesis authority** with three derivable properties:

1. **It is recorded, not hidden.** Every act of the genesis authority is written into the same store it is creating, marked with genesis provenance. The system can forever audit its own founding. (Forced by A2 and I4: an unrecorded founding is exactly the buried-decision failure mode the Sentium excavation spent months paying for.)
2. **It is scarred, not arbitrary.** The genesis authority does not exempt its artifacts from I7 — it *satisfies* I7, because the scars already exist: the Sentium incident catalog and the PAEOS-0/1/2 derivations are the pre-existing failure corpus from which every genesis policy must cite its justification. This answers "how are the first Policies created before a Steward exists": by the genesis authority, with scars imported from a corpus that predates the system. The months of archaeology were not preparation for the bootstrap; they *are* the bootstrap's first half, performed before the repository existed.
3. **It schedules its own death.** The genesis authority's founding document states the exact evidence condition under which the authority dissolves (§6). A founding power without an expiry becomes a permanent back door — the standing violation of clean-intent that would rot every other invariant (A6).

## 2. What PAEOS-0/1/2 force upon any bootstrap

Four constraints that eliminate most imaginable bootstraps:

- **Dogfooding begins at the earliest structurally possible moment, not at the end.** Self-hosting is not a destination; it is a ratchet. The instant Goals can exist, all further bootstrap work is tracked as Goals with Evidence — even while the founder is the one doing it. Side benefit, derivable from I6: the founder's manually-worked examples become the seed exemplars that compiled contexts will cite, and the seed of the taste corpus. The bootstrap doubles as the system's first training data.
- **Nothing is built before its first demand.** Creating a Role, Skill, or Protocol before anything needs it violates no-rule-without-a-scar — the demand *is* the justification. So the kernel organs are **demand-paged**: each is born at the moment an invariant cannot otherwise be satisfied. This single rule generates the entire birth order in §4 mechanically.
- **Bootstrap runs on real work only.** A rejected alternative: a "staging period" on toy workloads. Toy work generates toy scars, and a policy base derived from synthetic failures is cargo cult with extra steps — precisely what PAEOS-0 exists to prevent. The bootstrap's workload is the only real work available at genesis: building PAEOS.
- **The founder exits function-by-function, not at a ceremony.** From PAEOS-2's clean-intent invariant, a per-function handoff rule derives: *the founder performs each kernel function manually exactly until the artifact automating it reaches `verified` — and from that moment is forbidden from performing it manually.* The founder's bootstrap job is to fire themselves from one role at a time. There is no single moment when "the founder stops building"; there is a monotonic sequence of small abdications, each one evidence-gated, whose completion is itself the self-hosting condition.

**Rejected bootstrap primitives:** an *installer script* (untracked state; the bootstrap must be Goals and Evidence in the store, or the founding is unauditable); a *pre-built agent team* (violates demand-paging); a *pre-written skill library* (no scars — every skill must wait for its incident, with one principled exception in §5); a *big-bang constitution* covering anticipated cases (the evolution loop exists precisely so the constitution never needs to anticipate; genesis ships I1–I12 and nothing else).

## 3. The Smallest Viable Kernel

The complete list of what must exist before the first agent can legitimately act — everything here is founder-built under genesis authority, everything after it is demand-paged:

1. **The genesis record** — the literal first artifact (§8, Q1).
2. **The six object schemas** — Goal, Evidence, Policy, Incident, Decision, Amendment. Must precede any object: the kernel is a *typed* store, and an untyped artifact can't be validated, which makes every I-invariant unenforceable (A6).
3. **The validator** — the first executable check: does the store conform to the schemas, do policies carry scar/falsifier/firing-record, do promotions carry evidence? This is the first CI, and it is the mechanical enforcement without which the constitution is prose (A6 again).
4. **The Constitution** — I1–I12, each invariant citing its scar in the genesis corpus and stating its falsifier. Capped at genesis size.
5. **The Compiler** — the deterministic context-assembly function. Must precede the first agent, because I6 forbids agents on hand-written context; every hand-written prompt after the Compiler is verified is a constitutional violation. (Before it, the founder hand-compiles under genesis authority — and those hand-compilations are recorded, becoming the Compiler's test fixtures.)
6. **One Role: Builder.** The minimum stance for anything to be produced. The other six roles are demand-paged (§4).
7. **Four genesis Protocols** — one per router quadrant, maximally naive (e.g., bottom-left: "one Builder, checks verify, integrate"). All refinement is left to evolution; shipping clever protocols at genesis would be rules without scars.
8. **The root Goal** — *"PAEOS is self-hosting,"* whose evidence spec is exactly the criterion in §6.
9. **The founder ABI surfaces** — the Decision queue and the taste-corpus location, seeded with exemplars mined from the Sentium excavation.
10. **The reference adapter shim** (Claude Code) and, before self-hosting can be declared, the **null adapter** — derived in §5.

That is the whole kernel. No Router, no Steward, no Judge, no Skills, no tournaments exist yet. Their absence is not a gap; it is the demand-paging rule working.

## 4. The stage sequence

Consistent with everything since PAEOS-0, stages are **evidence states, not calendar phases** — each defined by its exit evidence, not its duration. They may overlap; they may regress if their evidence expires.

**S0 — Genesis.** Empty repository → items 1–4 of the SVK, founder-manual, extra-constitutional but fully recorded. *Exit evidence: the validator runs and the Constitution passes its own admission rules* — every invariant scarred and falsifiable. The moment the constitution is subject to its own test is the moment the extra-constitutional period starts closing.

**S1 — First light.** Compiler, Builder role, genesis protocols, root Goal declared. Then the milestone the whole stage exists for: **the first legitimate agent** — spawned with a compiled context, executing a leaf child of the root Goal, promoted to `verified` on check evidence. The founder is still hand-routing goals at this point, so the natural first assignment for the first agent is *to build the Router* — the organ that ends hand-routing. *Exit evidence: one goal carried from `declared` to `verified` entirely by an agent under compiled context.*

**S2 — Delegation cascade.** The remaining organs are born strictly on first demand, which yields the birth order as a theorem rather than a plan:

- **Decomposer** — immediately, since the root Goal is non-leaf.
- **Router** — the moment goals of more than one quadrant class coexist (in practice: first, per S1).
- **Adversary** — at the first goal whose evidence spec no mechanical check can satisfy (I3 forces a second stance).
- **Judge** — at the first tournament, i.e., the first goal where generation is genuinely uncertain and candidates fan out.
- **Integrator** — at the first moment two work streams target the same trunk (I9 becomes binding).
- **Steward** — at the first Incident (§S3).

Throughout S2, the founder executes the handoff rule — each function abdicated as its automation verifies. *Exit evidence: a goal flows `declared → integrated` with the founder acting only through the five verbs of PAEOS-2.*

**S3 — Evolution ignition.** The evolution loop cannot be *verified* to exist until it has run once, so this stage's demands are concrete: a first Incident, a first Steward run, a first Amendment. The first Incident needs no scheduling — bootstrap friction will supply it naturally, and the genesis parameters (quadrant rubric thresholds, spend caps) are the overwhelmingly likely source, since they were chosen provisionally by construction. **If** nothing has failed naturally (it will have), a fault is injected deliberately — kill an agent mid-task, which doubles as the crash-only conformance test for I5. The Steward is born to mine that Incident; its second task is the one large exception to wait-for-the-scar: **mining the Sentium incident catalog** — scars that already happened, merely in a pre-PAEOS substrate — which births the first real Skill population and populates the taste corpus. Also in S3: the **null adapter** (§5) comes up, and the portability conformance goal passes on both runtimes. *Exit evidence: one complete Incident → Amendment → recompiled-context cycle, plus dual-runtime conformance.*

**S4 — Ratification.** The self-test that defines self-hosting (§6) runs and passes. The final act of the stage — and the founder's last constructive act of the entire bootstrap — is resolving the ratification Decision, which produces the **ratification Amendment**: the record that the genesis authority's expiry condition is evidenced and the authority is dissolved. Note the elegance the kernel forces here: the founder's last act of *building* the OS is already inside the founder ABI — a Decision resolution. The handoff completes by using the interface it hands off to. *Exit evidence: the ratification Amendment, integrated.*

**S5 — Evolution.** PAEOS governs itself and takes external workloads (§7). Maturity is not a stage but an asymptote, with observable criteria: the founder-intervention rate decaying per PAEOS-2 §5; the constitution's size stable-or-shrinking under its cap; and one final, optional audit worth naming because it answers the Trusting-Trust anxiety inherent in any self-hosted system: **the reproducible constitution test** — periodically, an agent team is given only the incident corpus and asked to re-derive the constitution blind; material divergence between the derivation and the actual constitution is an Incident. A mature PAEOS can prove its rules still follow from its scars, the exact analog of a reproducible build.

## 5. The null adapter — how runtimes attach, derived

PAEOS-0's portability rule demands conformance on ≥2 runtimes, but building a Cursor or Codex adapter during bootstrap would delay loop-closure for no decorrelation benefit. The derivation instead notices that the second runtime is available for free: the **null adapter** — bare shell plus raw model API calls, implementing READ/WRITE as file operations, EXEC as shell, and SPAWN in its maximally degraded form (sequential self-invocation, no subagents, no hooks, no MCP). It is the *degenerate runtime*, and passing conformance on it proves precisely the thing that matters: that the kernel depends on nothing but the four syscalls. Every future adapter (PAEOS-6) then attaches by the same contract: implement four syscalls, implement context-lowering to the runtime's native format, pass the conformance goal. The null adapter is also the system's disaster floor — the runtime that cannot be discontinued, because it is barely a runtime at all.

## 6. The self-hosting criterion — "PAEOS can now build PAEOS"

A compiler is self-hosting when it compiles its own source; the strong form is fixpoint reproducibility. The PAEOS equivalent must be an executable evidence spec, and only one formulation survives derivation because only one exercises every organ at once:

> **PAEOS is self-hosting when a change to PAEOS itself traverses the complete lifecycle — declared as a Goal, routed, decomposed if needed, built, adversarially verified, integrated, and — on the failure path — captured as an Incident and resolved by an Amendment — while the founder acts only through the five verbs.**

Both branches are required: the success path proves the work loop; the failure path proves the evolution loop; the subject being *PAEOS itself* proves self-application; the founder-only-through-verbs clause proves the handoffs completed. This criterion is written into the genesis record at S0 as the authority's expiry condition — the founding document names its own death, and §S4's ratification Amendment is merely the recording that the death occurred.

## 7. The first real project

**The first workload is PAEOS itself — and this is a consequence, not a choice.** The bootstrap's demand-paging rule requires real work to generate the demands that birth every organ, and at genesis the only real work in the universe of the repository is the root Goal "PAEOS is self-hosting." Any other answer would require importing a workload into a system that cannot yet host one.

The interesting question is therefore the first **external** workload, and the criteria derive cleanly: it must be *real* (A4 — only real work produces the ground-truth evidence and genuine incidents that feed evolution; a demo workload generates decorative scars), *rich in Trace-B nodes* (an all-Trace-A workload would never exercise tournaments, Decisions, or architecture ceremony, leaving those paths unverified in production), and ideally *pre-scarred* (an existing incident corpus to convert into Skills). **Sentium is overdetermined on all three** — it is real, it is architecturally deep, and its excavation is already the seed corpus inside PAEOS's own constitution. The inversion is thus not just aesthetically right but derivable: Sentium doesn't contain PAEOS; Sentium is workload #1 *on* PAEOS, and the system's first Skills will have been mined from Sentium's scars before Sentium ever runs on it — the two projects bootstrapping each other in opposite directions.

## 8. Direct answers

1. **First artifact?** The genesis record: the declaration of the genesis authority, its scar corpus (Sentium catalog + PAEOS-0/1/2), and its expiry condition. It must be first because every other artifact's legitimacy — including the Constitution's compliance with its own admission rules — derives from it. It is the Grundnorm made into a file.
2. **Kernel before any agent?** The SVK items 1–5: genesis record, schemas, validator, Constitution, Compiler. An agent spawned earlier is ungoverned generation — exactly what the OS exists to prevent.
3. **Object order?** Genesis record → Schemas → Policy (Constitution) → Goal (root) → Evidence (first validator run) → Decision (first rubric escalation) → Incident (first friction) → Amendment (first correction). Each appears at first structural demand.
4. **Frozen before self-hosting?** The PAEOS-1 frozen structure: six objects and required fields, the lattice and its transition rules, seven stances, four syscalls, I1–I12, and the self-hosting criterion itself.
5. **Deliberately undefined until evolution?** All Skills, all Protocol refinements beyond the four naive genesis protocols, all adapters beyond reference + null, all numeric parameters (caps, N, thresholds, cadences — provisional at genesis, amendable with evidence), and the taste corpus beyond its seed.
6. **Exact point the founder stops building?** No single point — the per-function handoff rule, each abdication evidence-gated; the *last* manual act is resolving the ratification Decision, which is already inside the ABI.
7. **Paradox and resolution?** "Every mechanism that legitimates artifacts is an artifact." Resolved by cross-compilation: a recorded, scarred, self-expiring genesis authority (founder + raw runtime), grandfathered like a genesis block, auditable forever, dissolved by ratification.
8. **First Skills?** Mined by the newborn Steward from the Sentium catalog (scars that pre-date the system) and from bootstrap Incidents; thereafter, skills are born as *compressions of recurrence* — repeated similar Incidents, or the same guidance being hand-added to multiple contexts, are the mechanical signals that a Skill wants to exist.
9. **First Policies before a Steward?** Genesis authority, with imported scars — I7 satisfied, not suspended.
10. **Router born?** First organ built *by* an agent (S1→S2); the founder hand-routes until it verifies, then never again.
11. **Agents begin existing?** The first legitimate agent: Compiler verified + Builder role + compiled context + a leaf goal — the S1 milestone.
12. **First Goal allowed?** The moment Constitution and schemas exist: the root Goal, "PAEOS is self-hosting." Everything after S0 is its descendant.
13. **First Incident?** Whatever bootstrap friction supplies first — most probably a genesis parameter proving wrong; the crash-only fault-injection test is the guaranteed backstop.
14. **First Amendment?** The correction of that genesis parameter. The *last bootstrap* Amendment is ratification.
15. **"PAEOS can now build PAEOS" means:** the §6 criterion — a change to the OS traversing both the work loop and the failure loop, founder on the five verbs only, on two conformant runtimes.

## The one-sentence version

**PAEOS bootstraps by cross-compilation: a recorded, scarred, self-expiring genesis authority — the founder plus a raw frontier runtime — hand-builds only the smallest viable kernel (genesis record, schemas, validator, constitution, compiler, one Builder, four naive protocols, one root Goal), after which every organ is demand-paged into existence by the invariants themselves, the founder fires themselves function-by-function as each automation verifies, and the authority dissolves at the evidenced moment a change to PAEOS itself completes both the work loop and the evolution loop with the founder touching nothing but the five verbs — making PAEOS necessarily its own first workload and Sentium, already the source of its scars, the overdetermined first tenant.**
