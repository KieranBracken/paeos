# Task Lifecycle Checklist v1.0

> The exact checklist every engineering task follows. The Runtime ticks this automatically;
> a human running the lifecycle by hand ticks it manually. **Router-first:** you fill in
> the classification, which tells you which states are live. Auto-discharged states still
> get a one-line evidence stub — a blank box is a constitutionally invalid transition.

## 0. Classify first (this decides the rest)
- [ ] **L01 Intake** — artifact created: description · source · motivation · expected value · initial class → `evidence: ______`
- [ ] **L02 Triage** — disposition (keep/merge/reject/dormant/research/immediate): `____` · duplicate + forbidden-zone checked · **classification (v × r): `____`** · **ceremony depth: `Trace-A / Trace-B`**

> If Trace-A: L03–L11 and L17–L18 auto-discharge (stub each: "auto-pass, Trace-A"). Jump to L12.
> If Trace-B: every box below is live.

## Understanding *(Trace-B)*
- [ ] **L03 First-Principles** — model · constraints · fundamental laws → `evidence: ______`
- [ ] **L04 Ideation** — ≥3 decorrelated architectures · idealized solution · failure modes
- [ ] **L05 Frontier Research** *(only if blocked)* — dossier · novelty · prior art · **named consumer: `____`**
- [ ] **L06 Trade-off Analysis** — matrix (latency/accuracy/memory/risk/maintainability/complexity/…)
- [ ] **L07 Trade-off Mitigation** — mitigations · kill switches · fallback · shadow mode · safety constraints
- [ ] **L08 System Design** — components · interfaces · data flow · state machines · schemas · storage · APIs · deps · **intent-conservation audit passed**

## Constitutional Review *(Trace-B)*
- [ ] **L09 Multi-Perspective Critique** — all 7 stances reported (builder/architect/risk/perf/security/replay/maintainer)
- [ ] **L10 Adversarial Review** — verdict: `RATIFY / RATIFY-W-AMENDMENTS / REJECT` · **GATE** · findings in court format
- [ ] **L11 Formal Planning** — affected files · **forbidden files** · rollback · acceptance criteria · test strategy · deps · **contract frozen**

## Engineering *(always)*
- [ ] **L12 Branch Implementation** — approved scope only · commits ref the contract · no scope creep · runs (`executed`)
- [ ] **L13 Verification** — compile ✓ lint ✓ unit ✓ integration ✓ simulation ✓ replay ✓ performance ✓ · **signed evidence** · flaky re-run
- [ ] **L14 Independent Audit** — **different model family** · slop/mocks/dead-code/violations/security/regression hunted · **GATE** → `clean / findings`

## Integration *(always)*
- [ ] **L15 Documentation & Ledger** — atlas · roadmaps · diagrams · knowledge graph · decision logs · **traceable to origin**
- [ ] **L16 Promotion Decision** — `merge / seal / reject / research-only / dormant` · single-threaded integrate · **GATE (founder if founder-work)**

## Learning & Evolution *(Trace-B full; Trace-A on trigger)*
- [ ] **L17 Retrospective** — what slowed/failed/repeated · which prompts improved · what should be policy
- [ ] **L17 Constitutional Review (MANDATORY, CER-4)** — answered in writing: (a) weaknesses discovered · (b) assumptions invalidated · (c) parts of PAEOS strengthened · (d) Proposals created · (e) Debt recorded · (f) strategy change? **← task is NOT done without this**
- [ ] **L18 Knowledge Extraction** — new pattern/protocol/skill/template/invariant/heuristic (scarred + falsifiable)
- [ ] **L19 Constitutional Evolution** *(if triggered)* — Incident · Amendment (delta + scar + falsifier + evidence spec) · **founder GATE for kernel-surface**

## Constitutional Execution Rules — active every task (CER, v1.1)
- [ ] **CER-1** attempted to *falsify* the architecture (not just accept it) — weaknesses/complexity/assumptions/abstractions/TCB/verification/determinism/portability
- [ ] **CER-2** every discovered improvement → `proposals/PAEOS-IP-NNNN.md` (recommended, not silently applied)
- [ ] **CER-3** every deliberate non-ideal choice → `ledger/debt/DEBT-NNNN.md`
- [ ] **CER-5** nothing kernel/lifecycle/authority/invariant changed without founder ratification (runtime recommended, never legislated)

## Global rules — verify on every transition
- [ ] evidence present at this transition (no evidence = invalid)
- [ ] implementation stayed inside the contract (no architecture invented in L12)
- [ ] any defect/ambiguity → filed as Incident (HALT, not local fix)
- [ ] any repeated mistake → promoted to Skill/Template/Amendment
- [ ] artifact traceable to its origin goal

**Done =** L16 disposition recorded + L15 ledger synced + (Trace-B) L17–L19 closed. Not before.
