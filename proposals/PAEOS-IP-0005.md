# PAEOS-IP-0005 — Ownership of institutional-memory *creation*: a first-principles derivation

Status: **AWAITING FOUNDER** · Filed: 2026-07-30 · Channel: CER-2
Source finding: a **first-principles architectural analysis** (founder-directed) of who should own
the creation of institutional memory — scars, lessons, precedents, checklist/skill updates. The
analysis was performed **ignoring the current implementation**, deriving the answer from the
constitutional rules (CER-1..6), the forcing requirements (FR-3/4/5/6), and the 19-stage lifecycle.
The derived rule **differs from the current implementation**, so per CER-5/CER-6 the divergence is
filed here as a proposal — **no code is modified**. This proposal **generalises [PAEOS-IP-0004]**
(the narrow loop-vs-Evolution-Layer scar conflict) into its governing principle.

---

## 1. Observation — the question, stated precisely

"Institutional memory" is every durable artifact by which PAEOS remembers how to engineer better next
time: **scars** (failure memory + active guards, FR-6), **precedents** (recurring adversarial
findings, §7.2), **regression guards** (§7.3), and **procedural memory** — checklist / skill /
playbook / prompt updates (§7.2, soft loop). The question: **which subsystem should own the *creation*
of these artifacts?** "Creation" is deliberately ambiguous, and disambiguating it is most of the
answer.

## 2. Method — derive, don't inspect (CER-6)

I decompose "creation" into three acts and ask, for each, *which constitutional principle assigns an
owner*:

1. **Trigger** — the decision that a lesson is *warranted* at all.
2. **Authoring** — producing the artifact's *content* (root cause + detection signature; or the
   checklist/skill delta).
3. **Commit** — the durable, indexed, append-only *write* into the memory of record.

The corpus assigns each act to a different owner by the **same separation-of-powers logic** that
governs everything else in PAEOS. There is no single "creator."

## 3. Derivation

### 3.1 Trigger is owned by the adjudicating power (kernel / Court), never invented

FR-4 (evidence-gated) and the Court (§4.3) make *whether a failure occurred* an **adjudicated fact**,
not an opinion. A scar's legitimacy rests on a power having ruled: a **Court remand** (stage 11), a
**blocking adversarial dissent** (stage 12), a **G-Seal reject** (stage 14 — "a reject is a lesson,
not a deletion," §4.4), or a **post-seal regression / constitutional incident** (§4.5/§7.3). CER-1
(mandatory critical thinking) obliges the system to *surface* candidate lessons, but the trigger that
makes one *real* is an adjudicated outcome. **No subsystem may author memory from a failure it
declared itself** — that would let a worker manufacture the evidence for its own lesson. The trigger
owner is therefore the kernel/Court, upstream of authoring.

### 3.2 Authoring is owned by the Evolution Layer, at stages 15→17 — this is "who creates"

The 19-stage lifecycle is decisive. Memory is authored across three consecutive stages that form the
**Evolution phase**:

- **RETROSPECT (15)** — extract *root cause*, not symptom (G-Retro will not close without one, §7.1).
- **EVOLVE (16)** — turn the root cause into a reusable asset: a scar's **detection signature**, or a
  checklist/skill/playbook delta (§7.1/§7.2).
- **MEMORY_UPDATE (17)** — the scar record with its detection signature (§4.4 G-Memory).

§3.2 assigns stages **15–19** to the **Evolution Layer** ("retrospective extraction … memory update …
runtime-improvement proposals"). Therefore **authoring institutional memory is constitutionally the
Evolution Layer's stage-15→17 job.** Two independent principles confirm it and *exclude every other
subsystem*:

- **CER-5 (separation of powers).** Authoring a lesson is a *recommendation-class* act — it records
  and guards; it does not enact law. The Evolution Layer "may **propose** … may not **apply** kernel
  changes (routes to the FR-2 amendment path)" (§3.2). It is the one Z2 subsystem whose entire remit
  is *recommend-not-legislate*, which is exactly the authority profile memory authoring requires.
  When a lesson implicates the *constitution itself*, EVOLVE must **not** encode it as memory but
  route it to the amendment path (§7.2/§7.4) — a boundary only the Evolution Layer is defined to hold.
- **§5 role separation.** Only the **Documentation** role may *write* records, and it "only **records**
  what the powers decided" — it holds no decision power. Planner, Builder, Critic, Court, and Adversary
  **read** memory (scars injected as context at 0/7/8/11) but are constitutionally barred from
  authoring it (the Builder "cannot append ledger"; the Court's remit ends at the verdict). The
  writing hand (Documentation) operates *within* the Evolution phase — it does not author memory from
  inside a detection stage.

**Corollary (the load-bearing consequence): a *detection* stage may emit a trigger but must not author
memory.** VERIFY (11) and ADVERSARIAL_REVIEW (12) *detect*; they hand their verdict forward. Authoring
a scar at stage 11/12 is a **stage-17 act performed in the wrong stage by the wrong subsystem** — it
collapses the trigger/author separation of §3.1–3.2.

### 3.3 Commit is owned by the kernel, serialised at the stage-17 gate

FR-5 and §3.4 invariant (a): *every* state mutation "terminates in a ledger append performed by the
kernel (single writer)"; agent outputs are "**inert** until the kernel accepts them at a gate." §3.7
makes this explicit for memory: "**scar *writes* serialise through the kernel at stage 17**; **no agent
may delete a scar**." So the *commit* of institutional memory is the kernel's, at the **G-Memory**
gate (17), append-only and non-deletable — identical in shape to the ledger's single-writer rule and
guarded against T3 memory-poisoning (broad-signature quarantine, §3.7/PAEOS-7.5).

### 3.4 The derived rule

> **Institutional-memory creation is a three-owner act. The *trigger* is owned by the adjudicating
> power (kernel/Court); the *authoring* is owned by the Evolution Layer, executing stages 15→17 with
> the Documentation role as its writing hand; the *commit* is owned by the kernel, serialised at the
> stage-17 (G-Memory) gate, append-only and non-deletable. No detection stage (VERIFY 11 /
> ADVERSARIAL_REVIEW 12) and no worker role (Planner/Builder/Critic) may author or commit memory;
> they may only emit a trigger or read a guard. A lesson that implicates the constitution is not
> memory — it routes to the FR-2 amendment path.**

This rule is uniform across artifact kinds: scars, precedents, regression guards, and procedural
(checklist/skill/playbook) updates are all *authored in EVOLVE (16)* and *committed at MEMORY_UPDATE
(17)* — the soft ones by the kernel memory-write, the constitution-implicating ones by routing to the
founder (§7.4). Skills-as-capabilities ([PAEOS-IP-0001]) does not change ownership: a skill update is
procedural memory authored in the Evolution phase.

## 4. Divergence from the current implementation

The derived rule **differs** from what the code does today:

- `runtime/orchestrator/__init__.py` — `SoftLoop.run` **authors and writes a scar inline at the
  Court-remand step** (≈ stage 11 / VERIFY), *before* stages 15–17 and *outside* the Evolution Layer.
  This is a **stage-17 act executed in a detection stage by the wrong subsystem** — it violates the
  trigger/author separation (§3.1–3.2) **and the corpus's own existing text** ("scar writes serialise
  through the kernel at stage 17", §3.7). The divergence's *symptom* was already caught empirically in
  [PAEOS-IP-0004]: the coarse inline scar corrupts the Evolution Layer's recurrence detection. This
  analysis supplies its *cause*: memory was authored in the wrong stage.
- The Evolution Layer (`runtime/evolution.py`, B2.F) authors memory correctly (stages 15→17) but is
  **not the sole owner**, because the loop also writes. Two authoring owners is precisely the
  condition the derived rule forbids.

No other institutional-memory writer exists today (precedents/skills/checklists are not yet
auto-authored), so the divergence is currently confined to the scar path — but the rule should be
ratified generally, before those writers are built, so they are placed correctly from the start.

## 5. Risks / backwards compatibility

- Relocating scar authoring to stage 17 changes **ratified** B1.F/B2.B behaviour and its tests
  (`test_soft_loop.py`, `test_selfhost.py`) — a behavioural change requiring its own task + review
  (proposed **B2.G**, per IP-0004). This proposal does **not** perform it.
- No kernel-surface change is *required* by the rule itself; it is a **clarification** of existing
  §3.7 intent plus a relocation of one runtime write. If ratified, the smallest amendment is a
  one-line sharpening of PAEOS-7 §3.7/§4.4 making the exclusivity explicit ("memory is authored only
  in stages 15–17, by the Evolution Layer; detection stages emit triggers only").
- Interaction with the ledger single-writer rule is *consistent* — the derived commit-owner (kernel)
  is the same. No new mechanism is proposed.

## 6. Constitutional impact

- **PAEOS-7 §3.2 / §3.7 / §4.4 / §5 / §7.1** — clarify (do not contradict): institutional-memory
  *authoring* is exclusive to the Evolution phase (15–17) and the Evolution Layer; detection stages
  (11/12) emit triggers only; commit stays kernel-serialised at G-Memory (17).
- **Operational, not kernel-invariant-changing.** It sharpens an existing boundary rather than adding
  one; it needs founder ratification as a spec clarification (CER-2/CER-5), and its *implementation*
  (the B2.G relocation) is a separate F2-SOFT task.

## 7. Recommendation

**Ratify the derived rule (§3.4)** as a PAEOS-7 clarification, and **accept [PAEOS-IP-0004] Option A**
as its first concrete application, scheduling **B2.G — relocate scar authoring to stage 17 / the
Evolution Layer** as a separate, behaviour-changing task under its own Constitutional Review. Ratifying
the *general* rule now (before precedent/skill auto-authoring is built) ensures every future memory
writer is placed correctly by construction. This proposal recommends; it changes nothing until
ratified. **No code was modified; no ratified behaviour was touched.**
