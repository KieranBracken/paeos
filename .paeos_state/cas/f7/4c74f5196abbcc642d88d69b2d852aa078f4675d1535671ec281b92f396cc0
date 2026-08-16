# PAEOS Skill Ecosystem — Generation 1 (Constitutional Design)

Status: DESIGN ONLY — no implementation. Date: 2026-07-18.

## The governing constitutional distinction

PAEOS forbids rules without scars (I7/K6) — but that constraint governs **PAEOS
userland**, not the host toolchain. Gen-1 skills are **development tooling operated
under genesis authority** (PAEOS-3 §1): Claude Code skills that help *build* PAEOS,
written with skill-creator, living in `.agents/skills/` + `.claude/skills/`. Several
are designed to **graduate** into PAEOS userland at S3+ as Policy(kind=skill) artifacts
— at which point they acquire scars (importable from the 3.5/5.5/Ω reviews, which are
incurred incidents) and falsifiers. Each entry below records its layer now and its
graduation target, if any.

Layer vocabulary: **Kernel** (must be kernel code, never a skill) · **Runtime**
(graduates to kernel-scope Policy skill) · **Project** (graduates to workload-scope
Policy skill) · **Dev** (host toolchain, stays outside PAEOS).

---

## S1. `kernel-clause` — the clause oracle
- **Purpose:** answer "what governs X?" with verbatim clause text + full amendment
  overlay. The corpus is now 9 layered documents where PAEOS-4 text may be overridden
  by 3.5 amendments, 5.5 patches (B-*/H-*), SC-01..24, and Ω dispositions — resolving
  the *effective* rule by hand is the most common and most error-prone operation in the
  project.
- **Triggers:** any "what does the spec say about…", worker-package authoring, review
  work, dispatch prompts containing clause refs.
- **Inputs:** a topic/question or clause id. **Outputs:** effective-rule statement +
  citation chain (base clause → every amendment touching it, in order) + open-question
  flag if a pending amendment (unresolved B-*) affects it.
- **Workflow:** locate base clause (rg over spec/) → sweep amendment layers
  (reviews/3.5 06_*, reviews/5.5 01_*, SC register, Ω register) for the clause id →
  compose overlay → emit with precedence explained.
- **Dependencies:** none (rg/fd). **Interacts with:** every other skill cites through it.
- **Example:** "kernel-clause: who may write Goal.status?" → K4 §5.3 base + B-01
  amendment (kernel-maintained) + PENDING flag (amendment not yet founder-resolved).
- **Layer:** Dev. Graduation: Runtime (the Compiler's link-authoring assistant), at S3.

## S2. `amendment-author`
- **Purpose:** draft constitutionally complete amendments: PolicyDelta + motivation
  refs + falsifier watch + evidence spec + frozen-surface ceremony flag. Immediate
  need: the three kernel amendments (B-01, B-02, B-06+EXEC) gating Wave 1.
- **Triggers:** "draft an amendment", any SC-register entry conversion, incident
  resolution proposing a rule change.
- **Inputs:** defect/finding id(s) + intended change. **Outputs:** amendment-kind Goal
  payload (per K4 §2.5) ready for founder resolution, with §14.5 ceremony routing if a
  frozen surface is touched.
- **Workflow:** pull finding via kernel-clause → classify surface (frozen vs userland)
  → draft delta → attach motivation/scar refs → author falsifier watch → run
  constitutional-diff (S3) for blast radius → emit.
- **Dependencies:** S1, S3. **Interacts:** consumes adversarial-court findings and
  sc-register entries; output feeds founder `resolve`.
- **Example:** "amendment-author: B-06" → bytes-denomination amendment touching K4
  §6.4/§10/K10, ceremony-flagged, falsifier = "byte-cap produces adapter-divergent
  truncation in conformance".
- **Layer:** Dev. Graduation: Runtime (Steward stance library), at S3 — with scar =
  the 5.5 audit itself.

## S3. `constitutional-diff`
- **Purpose:** impact analysis for any proposed change to spec/ or kernel artifacts:
  which clauses, invariants, fixtures, conformance tests, and backlog nodes are
  affected; whether a §14.5 frozen surface is touched.
- **Triggers:** before any edit to spec/**; amendment drafting; review of worker output
  that cites clauses.
- **Inputs:** a diff or proposed change description. **Outputs:** affected-artifact
  table + ceremony classification + list of tests whose fixtures must change (fixture
  changes = spec amendments per R §1.13 — the skill enforces awareness of that trap).
- **Workflow:** parse diff → clause-id extraction → reverse lookup through the
  traceability structure (until T-TRACE exists: rg-based sweep of fixtures/packages/
  backlog for clause citations) → classify → report.
- **Dependencies:** S1. **Interacts:** called by S2 always; by package-qa on review.
- **Example:** "what does changing EvidenceReq.min_count touch?" → K4 §2.5, F-SCHEMA
  fixtures (12), F-VAL pairs (2), C6 fixture, backlog I-VAL acceptance.
- **Layer:** Dev. Graduation: none — superseded by T-TRACE (code) at Wave 4; retires.

## S4. `package-qa`
- **Purpose:** mechanical inspection of worker packages before dispatch (13 required
  sections, ULID-table conformance, no unresolved placeholders, forbidden-modifications
  well-formed) and of worker *output* against the package's review checklist. Directly
  executes the Chief-Implementation-Architect review role's mechanical half.
- **Triggers:** "inspect package X", worker completion, pre-dispatch of any wave node.
- **Inputs:** package file or worker diff + its package. **Outputs:** pass/fail per
  checklist item + HALT-rule compliance check (did the worker resolve an ambiguity
  locally? = automatic fail + SC-register referral).
- **Workflow:** structural lint → cross-check against backlog node fields (yq) →
  clause-citation spot-check via S1 → checklist verdicts.
- **Dependencies:** S1; yq. **Interacts:** feeds adversarial-court for the judgment
  half of review; feeds sc-register on HALT detection.
- **Example:** "package-qa: F-SCHEMA worker output" → enumeration-rule coverage counts,
  golden-tool independence verified (SC-12), 2 checklist items flagged for human review.
- **Layer:** Dev. Graduation: Project layer ((F,GOALSTRUCT) audit material), at S3.

## S5. `fixture-smith`
- **Purpose:** generate and lint schema fixtures per the F-SCHEMA enumeration rule
  (mechanical by design — the rule was written so that fixture generation requires no
  judgment); maintain manifest/coverage lint.
- **Triggers:** F-SCHEMA execution, any schema amendment (fixtures must follow).
- **Inputs:** schema definitions + enumeration rule. **Outputs:** fixture files +
  manifest + coverage report; NEVER golden bytes (SC-12: goldens come from the
  independent tool — the skill refuses, by design, to compute them).
- **Workflow:** parse schema field tables → expand enumeration rule → emit fixtures
  with pinned ULIDs → manifest → coverage lint.
- **Dependencies:** S1 (schema clauses). **Interacts:** output consumed by package-qa.
- **Example:** "fixture-smith: regenerate goal-kind fixtures after B-01 amendment."
- **Layer:** Dev. Graduation: none — subsumed by kernel validator + T-HARNESS.

## S6. `sc-register`
- **Purpose:** operate the HALT rule end-to-end: check a fresh ambiguity against
  SC-01..24, either cite the binding resolution or append a properly formed candidate
  entry (never resolve locally), and queue the G-RUN incident conversion.
- **Triggers:** any worker/reviewer hitting underspecified behavior; the word "HALT".
- **Inputs:** the ambiguity description + context. **Outputs:** citation OR new SC
  entry + halt report.
- **Workflow:** normalize question → search register → if miss: draft entry with
  binding-resolution slot EMPTY (resolution authority = Chief Architect or founder,
  never the halting worker) → log.
- **Dependencies:** S1. **Interacts:** package-qa auto-invokes on HALT detection;
  amendment-author consumes entries at conversion time.
- **Example:** worker asks "what encoding for signature bytes in JSON?" → cites SC-03
  (base64url per Ed25519 entry) — no new entry needed.
- **Layer:** Dev. Graduation: Runtime — this IS the incident-intake flow; at S3 it
  becomes the incident-kind Goal authoring skill, scar = the Wave-0 package that
  invented the HALT rule.

## S7. `adversarial-court`
- **Purpose:** run the ratified review protocol (3.5/5.5 format) against any artifact:
  findings with violated-principle / evidence / severity / smallest-amendment fields,
  explicit rejected-attacks section, and the fixed verdict vocabulary. Reusable at
  every freeze point and for Trace-B ceremony during implementation.
- **Triggers:** "review X constitutionally", any freeze proposal, Trace-B goals.
- **Inputs:** target artifact + the principles it claims to satisfy. **Outputs:**
  findings register + verdict (REJECT / REJECT WITH MAJOR AMENDMENTS / RATIFY WITH
  AMENDMENTS / RATIFY).
- **Workflow:** stance setup (forget authorship — decorrelation discipline) → attack
  per investigation list → verify each finding against corpus via S1 → severity → 
  verdict + amendment stubs handed to S2.
- **Dependencies:** S1, S2, S3. **Interacts:** the judgment half behind package-qa's
  mechanical half.
- **Example:** "adversarial-court: the F-SPI freeze" before Wave-1 dispatch.
- **Layer:** Dev. Graduation: Project — becomes the (FALSIFY,*) stance library, the
  single most scar-backed skill in the system (its scars are the 3.5 and 5.5 reviews
  themselves).

## S8. `scar-miner`
- **Purpose:** mine a failure corpus into SC-08-schema scar artifacts + demand-table
  fulfillment + anti-fabrication discipline (source-pointer required; vicarious
  substitution path). Exists to execute G-CORPUS and, later, Steward mining.
- **Triggers:** G-CORPUS execution; "mine X for scars"; post-incident analysis.
- **Inputs:** corpus location + demand table. **Outputs:** scar artifacts + index +
  substitution flags + taste-exemplar candidates.
- **Workflow:** apply the G-CORPUS rubric (rework-from-lost-decision, defect-past-
  review, repeated-intervention, reversal-cost) → extract with source pointers →
  schema-check → demand-table reconciliation.
- **Dependencies:** S1, fixture schemas. **Interacts:** output feeds G-CONST scar refs;
  taste candidates feed founder Curate.
- **Example:** "scar-miner: reviews/5.5-implementation-audit → scars for the three
  kernel amendments' motivation fields."
- **Layer:** Dev. Graduation: Runtime — the Steward's core competence, at S3.

## S9. `conformance-runner`
- **Purpose:** drive the C1–C8 / L0–L5 suites against an adapter and emit
  evidence-shaped reports (per-test: claim, observation, polarity) so that conformance
  output is already in kernel Evidence form before the kernel exists to store it.
- **Triggers:** any wave acceptance check; "run conformance"; pre-merge gates.
- **Inputs:** suite selection + adapter target. **Outputs:** evidence-shaped results +
  failure localization hints (which module's golden diverged).
- **Workflow:** invoke T-HARNESS (once built; before that, per-suite scripts) → 
  collect → format → compare against prior runs for regressions.
- **Dependencies:** T-HARNESS (code), S1. **Interacts:** package-qa consumes results
  as acceptance evidence.
- **Layer:** Dev. Graduation: none — T-HARNESS/kernel EXEC absorb it; the skill is its
  human-facing shell and retires at S4.

## S10. `genesis-builder`
- **Purpose:** dry-run and execute the G1–G7 sequence: validate all inputs present
  (G-CONST/G-CORPUS/G-ROLES/G-ROOT outputs), order-check against R §12 (as amended by
  B-03: G1+G2 atomic), rehearse on a scratch store, then perform the recorded founding
  batches via I-GEN.
- **Triggers:** S0 execution readiness; "rehearse genesis".
- **Inputs:** genesis input artifacts + I-GEN binary. **Outputs:** rehearsal report;
  then the founding commits (founder present — G-RUN is a founder act).
- **Workflow:** completeness check → dry-run on scratch → diff dry-run store against
  expected → founder ceremony checklist → execute.
- **Dependencies:** S1, S4, S5, S8 outputs; I-GEN. **Interacts:** terminal consumer of
  half the ecosystem. **Layer:** Dev, single-shot; retires at S0-exit.

---

## Rejected / deferred designs (user candidates not carried forward as gen-1)

| Candidate | Disposition |
|---|---|
| Constitutional Derivation | **Rejected.** Derivation is frozen; a skill for it institutionalizes re-litigation — the failure mode the freeze exists to prevent. Post-ratification, derivation happens only through incidents (kernel-clause + amendment-author cover that path). |
| Kernel Freeze | Subsumed: freeze = adversarial-court verdict + amendment-author ceremony + constitutional-diff blast radius. No separate skill. |
| Specification Consistency Checker | **Is code, not a skill** — the T-TRACE backlog node (computed traceability matrix). A skill version would decay (A6); the matrix must be mechanical. |
| Interface Contract Validator | **Is the kernel validator itself** (Kernel layer). Never a skill. |
| Evidence Validator | Kernel layer (K1/K2 machinery + SIG check). Never a skill. |
| Router Auditor / Bootstrap Auditor | Real, but post-genesis (S3+): they audit a running system. Gen-2, as Runtime-layer policy skills with scars from whatever the bootstrap actually breaks. |
| Implementation Derivation | Done (PAEOS-4.5). Same re-litigation risk as Constitutional Derivation. |

## ROI ranking and build order

Ranking weighs: (a) how many wave-nodes consume it, (b) whether it unblocks the
current gate (the three kernel amendments blocking Wave 1), (c) error-cost of doing
the same work by hand, (d) build cost with skill-creator.

| Rank | Skill | Why here |
|---|---|---|
| 1 | **kernel-clause** | Consumed by every other skill, every worker, every review; the amendment-overlay problem is today's biggest silent-error source; cheapest to build. Build first, same day as any other work. |
| 2 | **amendment-author** | The gate: Wave 1 is blocked on three kernel amendments. Nothing else matters until they're drafted and founder-resolved. |
| 3 | **constitutional-diff** | Required by #2 for ceremony classification; also guards every spec edit from here to freeze. |
| 4 | **package-qa** | Wave-0 packages need reissue (F-SCHEMA scope, F-SPI workdir) then dispatch — this skill is the dispatch gate's mechanical half. |
| 5 | **sc-register** | Must exist before the first worker dispatch, or HALT discipline is manual and will be skipped under pressure (A6 applies to us too). |
| 6 | **fixture-smith** | Wave-1 critical path (F-SCHEMA is the root of the DAG). |
| 7 | **adversarial-court** | First hard need: reviewing the reissued F-SPI freeze and the amendment drafts; recurring at every milestone. High value, moderate build cost. |
| 8 | **scar-miner** | Needed when G-CORPUS dispatches (Wave 0, but not on the critical path until G-CONST's scar refs are due). |
| 9 | **conformance-runner** | Valuable from Wave 3 (first C-tests exist); pointless earlier. |
| 10 | **genesis-builder** | Single-shot, Wave 5; build last, after its inputs exist. |

**Recommended build cadence:** 1–3 immediately (they unblock the amendment ceremony);
4–6 before first Wave-0 dispatch; 7 before the F-SPI freeze review; 8–10 just-in-time.
All built with skill-creator, evaluated with its harness — those eval records become
the seed corpus for each skill's graduation scars.
