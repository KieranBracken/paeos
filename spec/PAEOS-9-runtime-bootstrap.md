# PAEOS-9 — Runtime Bootstrap Architecture

> Status: architecture (design, not implementation). The **runtime entrypoint**: every
> implementation session executes this bootstrap before any engineering work begins. Its job
> is to transform the constitutional corpus (30–50 markdown files) into **one authoritative,
> executable engineering context** that the worker consumes instead of the raw documents.
> **This does not modify the constitution.** The raw corpus remains the source of truth; the
> compiled context is the *executable interface* between the constitution and the AI worker.

## §0 Framing — what the bootstrap is, and what it reuses

**The problem it kills (the Sentium scar):** AI workers ignored, forgot, or inconsistently
applied constitutional documents *because those documents were passive markdown competing for
attention in a context window.* PAEOS-9 makes the constitution **active**: compiled, injected
as the only thing in the prompt, mechanically enforced, and automatically refreshed.

**The model — source → IR → executable (LLVM analogy):**
```
raw corpus (git)          =  source of truth (immutable, human-authored)
         │  Context Compiler (§2) — deterministic, precedence-resolving
         ▼
compiled_context (.runtime) =  the IR: one authoritative snapshot, content-hashed
         │  Prompt Generator (§4) — deterministic render
         ▼
worker prompt              =  the executable the AI runs
```

**It invents no new law.** Every mechanism below is an existing kernel/lifecycle concept made
operational:
- determinism ← kernel `compile()` §6.1 (byte-identical manifest) + F-1 render grammar
- precedence resolution ← §0 / Z-1 (8.1 > ratified amendments > PAEOS-4 v1.1 > rest)
- amendment overlay ← §9.4 amendment lifecycle
- contradiction → COMPILE_FAILURE + auto-incident ← §6.2 scope-conflict
- anti-stale (context expiry) ← **K2** read-set binding + transitive expiry
- compiled context is a rebuildable cache, never authoritative ← H-08 / D1
- prompt is generated, never hand-written ← **K5**
- enforcement = the WRITE validator + lifecycle gates ← §11, X1–X6, §5.3, L-state machine

**It is a genesis-authority scaffold.** Until the PAEOS Runtime + kernel `compile()` exist
(S3+), this bootstrap is the hand-built loader. At self-hosting it is *replaced by* the
kernel's own `compile()`; PAEOS-9 is that function's specification at session scope.

**The determinism guarantee (the founder's goal):** two Claude Code sessions started months
apart, over the same corpus state, MUST produce the same `compiled_context.content_hash`, and
therefore the same worker prompts, and therefore identical pre-implementation behavior. The
content_hash is the reproducible-build fingerprint; a mismatch is a detected defect, never
silent drift.

---

## §1 Repository Loading

The loader produces a **Load Manifest**: an ordered list of `(slot, path, sha256, load_mode)`.
Load order **is precedence order** (§0), highest first, so contradictions resolve
deterministically. Two sessions over identical repo state produce an identical manifest — this
is the first half of the determinism guarantee.

### 1.1 Load modes
- **FULL** — entire normative content enters the compiled context.
- **SUMMARY** — a deterministic digest (headers + normative clauses only) enters; full text is
  on-demand.
- **INDEX** — path + hash + one-line role only; content loaded on explicit reference.
- **EXCLUDE** — never loaded for rules (loaded only for lineage audit).

### 1.2 Canonical loading order (deterministic)
```
slot  load_mode  source                                        role
────────────────────────────────────────────────────────────────────────────────
01    FULL       spec/PAEOS-4-v1.1.md §0 (precedence+constants) the reading order itself
02    FULL       spec/PAEOS-4-v1.1.md (kernel, canonical)       the executable kernel law
03    FULL       spec/PAEOS-8.1-runtime-clarifications.md        tier-(a); governs named clauses
04    FULL       any post-v1.1 ratified amendment (proposals→ratified)  overlay (newest wins per §0)
05    FULL       operations/ENGINEERING_LIFECYCLE.md (v1.1)      lifecycle states + CER rules
06    FULL       operations/WORKFLOW_STATE_MACHINE.yaml          executable transitions/gates
07    FULL       operations/FOUNDER_IMPLEMENTATION_PRINCIPLES.md FP-1..7 (session discipline)
08    FULL       operations/ROLE_RESPONSIBILITIES.md             authority + mutation bindings
09    FULL       operations/PROMPT_TEMPLATES.md                  the render templates (§4)
10    FULL       backlog/packages/<active-task>.md               the current implementation package
11    SUMMARY    backlog/PAEOS-5-backlog.yaml                    task graph (for dep/selection)
12    SUMMARY    proposals/ (open only)                          surfaced advisories (CER-2)
13    SUMMARY    ledger/debt/ (open only)                        active debt (CER-3)
14    INDEX      reviews/ (3.5, 5.5, 6, 8)                        scar corpus — loaded on demand
15    INDEX      derivation/ (0..3.5)                             justification — loaded on demand
16    INDEX      genesis/                                         only FULL during genesis
17    EXCLUDE    spec/PAEOS-4-kernel.md (v1.0)                    SUPERSEDED by v1.1 (§0); lineage only
```

### 1.3 Mandatory vs optional
- **MANDATORY** (bootstrap HALTS if absent/hash-mismatched): slots 01–10. These are the
  executable law + the current task. No session proceeds without all ten.
- **OPTIONAL/advisory:** 11–13 (loaded if present; empty is legal).
- **INDEXED-ONLY:** 14–16 (never in the base context; pulled on reference or by a `scar`
  lookup).
- **EXCLUDED:** 17 (a worker that loads v1.0 for *rules* is a defect — v1.1 is canonical).

### 1.4 Integrity check (during load)
The loader MUST verify `genesis/constitutional-basis.sha256` against the derivation files
(constitutional lineage intact) and record every file's sha256 in the manifest. Any missing
mandatory file, hash mismatch on a mandatory file, or lineage mismatch ⟹ **BOOTSTRAP_HALT**
(§5 B4) — never a silent partial load.

---

## §2 Context Compiler

`compile_context(load_manifest, task) → CompiledContext`. Pure, deterministic. Workers **never
individually decide what documents matter** — the compiler decides, once, mechanically.

### 2.1 Pipeline (six deterministic stages, mirrors kernel §6)
```
1. RESOLVE   : order slots by precedence (§0). Higher-precedence text is authoritative.
2. OVERLAY   : apply amendments over frozen text (§9.4). A post-v1.1 ratified amendment
               overrides the clause it names; unamended clauses pass through. This is the
               kernel-clause overlay (gen-1 skill) automated.
3. DETECT    : cross-check for residual contradiction — two clauses in force that conflict and
               are NOT separated by precedence. Any such pair ⟹ COMPILE_FAILURE + auto-incident
               (mirrors §6.2). The compiler never guesses a winner.
4. EXTRACT   : pull the EXECUTABLE subset from each FULL doc — invariants, rules, gates,
               mutation matrix, forbidden lists, evidence specs, the task package — NOT the
               prose justification. Justification is SUMMARY-tier (scars, derivation refs).
5. BUDGET    : fit to the byte budget (§6.4). MANDATORY tier (01–10 executable subset) is
               NEVER truncated. SUMMARY/INDEX truncate first, in reverse precedence order, each
               drop recorded. If the mandatory executable subset itself overflows the budget,
               that is a COMPILE_FAILURE AND a K10 violation (the constitution exceeded its own
               size cap) → an incident against the constitution, not a silent drop.
6. RENDER    : emit CompiledContext with a manifest (ordered (slot,path,version,hash)) and
               content_hash = HASH(SERIAL(manifest ‖ body)). Byte-identical across
               implementations (§6.1, F-1 grammar).
```

### 2.2 How contradictions, precedence, amendments are handled (explicit)
- **Precedence** is not re-decided per session; it is the fixed §0 order. The compiler applies
  it mechanically.
- **Amendments override frozen documents** by the overlay in stage 2: the frozen text is
  loaded, then each ratified amendment's delta replaces its named clause. The compiled context
  shows the *resolved* rule plus a provenance line (`⟵ 8.1 A-1` etc.) so the override is
  auditable.
- **Contradiction detection** is clause-level and conservative: if precedence resolves it, it
  is resolved; if not, the bootstrap halts. There is no "compiler judgment" — a judging
  compiler would be the ungoverned intelligence K5/A-05 forbids.

### 2.3 Summaries
Each SUMMARY-tier doc contributes a **deterministic digest**: its headers plus any clause
tagged normative (MUST/SHALL/MUST NOT), verbatim, in document order. No paraphrase (paraphrase
is non-deterministic). Scars (reviews/) summarize to `(finding-id, one-line, severity)`.

### 2.4 Output location
`.runtime/compiled_context.json` (+ a human-readable `.runtime/compiled_context.md` rendering).
**This is a rebuildable cache, gitignored, regenerated every boot** (H-08/D1) — never
authoritative, never committed. The raw corpus is the source of truth; the cache is
reproducible from it. The content_hash is logged to `.runtime/boot.log` for audit.

---

## §3 Runtime Context object

The single in-memory object present during implementation. Everything the worker needs; nothing
it doesn't. (Field → grounding.)
```
RuntimeContext {
  # identity — the reproducible-build proof
  content_hash:   sha256          # fingerprint of this whole object (determinism check)
  corpus_hash:    sha256          # hash of the Load Manifest (which corpus state produced this)
  compiled_at:    TIME
  compiler_version: string
  load_manifest:  [ (slot, path, sha256, load_mode) ]      # auditable; diffable across sessions

  # current task (one per session — FP-1)
  task: { goal_id, delta, evidence_spec:[EvidenceReq], constraints:[ref],
          classification:{v,r}, ceremony_depth: trace_a|trace_b, budget:Budget, workload }

  # lifecycle position
  lifecycle: { current_L_state, lattice_status,            # G-1 mapping (L→kernel lattice)
               applicable_states:[…],                       # which of L01–L19 apply (router)
               next_gate: {state, approver} | null }

  # authority (§5.3 + §14.5 + roles)
  authority: { role:(stance,domain), model_family, founder_present:bool,
               may_write:[…], must_not_write:[…], gates_ahead:[…] }

  # the executable constitution — precedence-resolved ACTIVE subset (not prose)
  constitution: { invariants:[K1..K11 digest], cer:[CER-1..5], global_rules:[1..17],
                  founder_principles:[FP-1..7], precedence_note }

  # prohibitions (hard, checkable)
  forbidden: { files:[…] (L11 package), transitions:[X1..X6], writes:[mutation-matrix denials] }

  # evidence gate for the current state/goal
  evidence: { required:[EvidenceReq], decorrelation, signing_required:bool,
              present:[Evidence refs], missing:[EvidenceReq] }

  # the active implementation package
  package: { name, required_sections, acceptance_tests, commit_boundaries, review_checklist,
             forbidden_modifications }

  # advisory — surfaced, NEVER applied (CER-5)
  proposals:  [ open PAEOS-IP-NNNN digests ]          # CER-2
  debt:       [ open DEBT-NNNN relevant to task ]      # CER-3
  scars:      [ finding refs relevant to task domain ] # justification for the active rules
  active_amendments: [ post-v1.1 overlays applied ]
}
```
The worker reads this object. It does not read raw markdown. If a field it needs is absent,
that is a compiler defect (incident), not the worker's problem to improvise around.

---

## §4 Prompt Generator

`generate_prompt(RuntimeContext, state) → WorkerPrompt`. Deterministic render (F-1 grammar).
**A builder agent NEVER receives a hand-written prompt** (K5) — the flow is fixed:
```
Task → Context Compiler (§2) → RuntimeContext (§3) → Prompt Generator (§4) → Worker Prompt
```

### 4.1 Template (every section, in fixed order)
```
[1] UNIVERSAL PREAMBLE   — verbatim from PROMPT_TEMPLATES.md (role, workload, state, HALT rule,
                           CER preamble: falsify the architecture, propose don't legislate).
[2] AUTHORITY            — from RuntimeContext.authority: your role (stance,domain), your model,
                           what you MAY write, what you MUST NOT write, the gates ahead.
[3] ACTIVE CONSTITUTION  — the executable digest: the invariants, CER, global rules, and FP that
                           bind THIS state (not the whole corpus — the applicable subset).
[4] TASK                 — goal delta, evidence_spec, constraints, serving-clause, budget.
[5] PACKAGE              — the implementation package's required artifacts + acceptance tests.
[6] EVIDENCE REQUIRED    — exactly what evidence promotes this state; signing/decorrelation.
[7] FORBIDDEN            — forbidden files, forbidden transitions, forbidden writes (hard list).
[8] ADVISORY             — open scars for this domain; open debt; (proposals are founder-facing,
                           shown read-only). "If you discover an improvement, file a Proposal."
[9] OUTPUT CONTRACT      — the exact artifact shape to return (from the state's produced_evidence
                           schema); "return artifacts only; the Runtime gates the transition."
[10] CONTEXT FINGERPRINT — content_hash + corpus_hash (so the worker's output is attributable to
                           an exact context; two identical fingerprints ⟹ identical prompt).
```
Sections 2–10 are populated purely from RuntimeContext; section 1 is verbatim template. Same
RuntimeContext ⟹ byte-identical prompt.

---

## §5 Worker Boot Sequence

From opening the repository to first implementation action. Every step is forced; none is
"normal startup." Any failure ⟹ **BOOTSTRAP_HALT** with a reason (never a partial start).
```
B1  LOCATE + VERIFY REPO   : resolve repo root; git working tree clean on managed paths
                             (store/**, .runtime/**); reset .runtime/ (it is a cache). ⟵ 5.5 BOOT-1/2
B2  LOAD CORPUS            : build the Load Manifest in canonical order (§1); hash every file;
                             confirm all MANDATORY slots (01–10) present.                 ⟵ §1
B3  VERIFY INTEGRITY       : constitutional-basis hashes match (lineage intact); mandatory
                             hashes recorded. Mismatch ⟹ HALT.                            ⟵ §1.4
B4  COMPILE CONTEXT        : run the Context Compiler (§2). COMPILE_FAILURE (contradiction or
                             mandatory-overflow) ⟹ HALT + auto-incident. Emit
                             .runtime/compiled_context.{json,md} + content_hash.          ⟵ §2
B5  ACQUIRE TASK           : select EXACTLY ONE roadmap task whose deps are all integrated
                             (FP-1); load its package (slot 10); bind task fields.        ⟵ FP-1
B6  ASSIGN AUTHORITY       : bind role (stance,domain) + model family for the current state;
                             enforce decorrelation (auditor/adversary ≠ builder family, A-08).⟵ §3
B7  VALIDATE BRANCH        : confirm trunk releasable (FP-2); create/verify the speculation
                             worktree (A-16); confirm classification + ceremony depth set.  ⟵ FP-2,A-16
B8  INITIALIZE LIFECYCLE   : set current L-state + lattice status (G-1 map); compute
                             applicable_states + next_gate; assemble RuntimeContext.        ⟵ §3
B9  GENERATE + BEGIN       : generate the first worker prompt (§4); begin implementation under
                             runtime enforcement (§7). Log content_hash to boot.log.       ⟵ §4,§7
```

---

## §6 Context Refresh (anti-stale = K2 expiry)

Workers run for hours; the corpus can change under them. The mechanism is **exactly kernel
evidence expiry (K2)**: the CompiledContext is *bound* to `corpus_hash` (its read-set = the
Load Manifest). If any bound file changes, the context is **stale by definition** and MUST be
recompiled before the next action.
```
FRESHNESS CHECK (before every state transition and on a periodic tick):
  recompute corpus_hash from disk; if ≠ RuntimeContext.corpus_hash ⟹ STALE ⟹ recompile (B4)
  and re-derive RuntimeContext. Nothing proceeds on a stale context.

REFRESH TRIGGERS:
  • any WRITE to a mandatory corpus file            ⟹ recompile
  • a proposal ratified into an amendment (§9.4)     ⟹ recompile (overlay changes)
  • a lifecycle state transition                     ⟹ re-derive state-scoped fields
                                                       (authority, evidence, forbidden, next_gate)
  • periodic tick (bounded interval)                 ⟹ freshness check

AMENDMENT DETECTION: the compiler watches proposals/ for founder-ratified transitions and the
  active-amendment set; a new ratified amendment invalidates corpus_hash ⟹ forced recompile.
PROPOSAL SURFACING: new open proposals appear in RuntimeContext.proposals on the next refresh
  (surfaced read-only; never auto-applied — CER-5).
STALE PREVENTION: a content_hash/corpus_hash mismatch is a hard stop, not a warning. It is
  mechanically impossible to keep acting on a stale context because the freshness check gates
  every transition.
```

---

## §7 Runtime Enforcement (a gate machine, not a suggestion)

The runtime does not trust the worker to self-regulate. It (a) compiles the constraints INTO
the context, and (b) checks the worker's proposed writes AGAINST them before commit — the
session-scope mirror of the kernel WRITE validator. Each prevented violation maps to an existing
mechanism:
```
VIOLATION                 PREVENTED BY
─────────────────────────────────────────────────────────────────────────────────────
jumping lifecycle stages  the L-state machine gates transitions; the runtime only generates the
                          prompt for the CURRENT legal state; the worker cannot self-advance
                          (it returns artifacts; the Runtime advances). L-states are metadata;
                          kernel lattice governs promotion (G-1, K1).
skipping verification     K1 evidence-gated: a state does not close without its produced_evidence
                          present and live; L14 audit is a hard gate.
editing forbidden files   forbidden.files (L11 package) is a write-mask; a proposed write to a
                          forbidden path is rejected pre-commit (mirrors EXEC sandbox write-mask,
                          06-A12).
authority violations      §5.3 mutation matrix compiled into forbidden.writes; a builder writing
                          Evidence, or any actor writing status, is FORBIDDEN_CLASS (B-01/B-02).
missing evidence          K1: promotion blocked (default-deny, A-10); the next_gate will not open.
scope creep               work must reference the L11 contract + serving_clause; the runtime
                          checks proposed artifacts against the package scope; drift ⟹ incident
                          (A-11 spec-sufficiency; intent conservation).
architecture change       CER-5/§14.5: any change to kernel/lifecycle/authority/invariants is
                          rejected unless it is a founder-ratified amendment. The runtime files
                          a Proposal instead (CER-2).
```
Enforcement posture: **pre-commit rejection**, not post-hoc detection. The worker literally
cannot commit a violating write; it receives the rejection and must conform or HALT to an
incident. (Pre-kernel this is the bootstrap's own check layer; post-kernel it is the actual
WRITE validator — same contract.)

---

## §8 Session Memory (crash-only; store = permanent, context = cache)

Grounded in D1 (crash-only) + A2 (artifacts durable, context ephemeral). The rule: **if it
matters, it is in the store before session end.**
```
SURVIVES (permanent — written to the store, git, append-only K4):
  • integrated work products + their evidence
  • the Constitutional Review (CER-4)
  • proposals (proposals/PAEOS-IP-NNNN)          — CER-2
  • debt entries (ledger/debt/DEBT-NNNN)          — CER-3
  • incidents raised; amendments IF founder-ratified
  • the boot.log content_hash (audit trail of what context governed the session)

DISCARDED (ephemeral — regenerable, never authoritative):
  • the conversation / chat history
  • the RuntimeContext + .runtime/compiled_context.* (a cache; rebuilt at next boot, H-08)
  • intermediate reasoning, un-committed speculation-branch work

PROMOTION PATHS (how ephemeral becomes permanent — the ONLY ways):
  discovered improvement → Proposal (proposals/)         [never a silent code change]
  deliberate compromise  → Debt (ledger/debt/)
  failure/ambiguity      → Incident (store)
  ratified proposal      → Amendment → corpus (founder only)
  reusable pattern       → Skill/Template (L18)
```
Crash-only corollary: killing the session at any point loses only the cache and the chat —
never a decision, never a scar, never work — because those were written as they were made
(this is the founder session-close ritual, FP, made mechanical).

---

## §9 Runtime Health (diagnostics)

A read-only projection of RuntimeContext, answerable at any instant (`paeos status`):
```
HealthReport {
  active_lifecycle_stage : lifecycle.current_L_state (+ lattice_status)
  active_authority       : authority.role + model_family + founder_present
  applicable_rules       : constitution digest that binds the current state
  evidence_missing       : evidence.missing  (what the next gate is waiting on)
  blocked_reason         : the first unsatisfied gate — one of
                           {missing_evidence, failed_audit, forbidden_write_attempted,
                            authority_denied, stale_context, budget_exceeded, awaiting_decision}
                           with the specific artifact/gate id
  corpus_freshness       : content_hash vs disk corpus_hash (FRESH | STALE)
  open_proposals         : count + ids       open_debt : count + ids
  budget_remaining       : per dimension
}
```
"Why is implementation blocked?" is always answerable with a single gate id and its unmet
condition — never "I'm not sure." If `blocked_reason = stale_context`, the fix is a recompile
(§6); the diagnostic names it.

---

## §10 Adversarial Review (attack the bootstrap, then harden)

Per CER-1 / the PAEOS-3.5 method, run on the bootstrap itself.

| Attack | Would it work? | Mitigation (baked into the design) |
|---|---|---|
| **An AI ignores the compiled context** (treats it as more skippable markdown) | Only if raw docs also compete for attention | The worker prompt contains **only** the generated context (§4); raw docs are not in the window. Enforcement is mechanical pre-commit rejection (§7), not "please comply." Nothing to ignore *toward*. |
| **Prompt drift** (same task, different prompt over time) | Only if render is non-deterministic | Deterministic render (F-1) + content_hash pin: same RuntimeContext ⟹ byte-identical prompt. Drift = hash mismatch = detected, not silent. |
| **Stale context accumulates** | Only if staleness is un-checked | K2 binding: the context is read-set-bound to corpus_hash; the freshness check gates **every** transition (§6). Acting on stale context is mechanically blocked, not merely discouraged. |
| **Documents silently diverge** (two docs disagree) | Only if divergence is unresolved and undetected | Precedence (§0) resolves most; a residual contradiction ⟹ COMPILE_FAILURE + incident (§2 stage 3). Constitutional-basis hashes catch lineage tampering (B3). The reproducible-constitution test (PAEOS-3 S5) catches deep drift. |
| **Token/byte pressure corrupts loading** (mandatory content silently dropped) | Only if truncation is silent | Mandatory tier (01–10 executable subset) is NEVER truncated (§2 stage 5). If it overflows, that is a COMPILE_FAILURE **and** a K10 violation (constitution exceeded its own cap) — an incident, not a drop. Only SUMMARY/INDEX truncate, recorded. |
| **Two sessions diverge** (the founder's core fear) | Only if corpus differs or compiler is non-deterministic | corpus_hash detects corpus difference; §6.1 forbids compiler non-determinism. Identical corpus ⟹ identical content_hash ⟹ identical prompts. Behavioral non-determinism below that is the worker layer's, gated by evidence (K1) — it cannot promote a wrong result. |
| **Worker edits the compiled context to loosen a rule** | Only if the cache were authoritative | The cache is not authoritative; it is regenerated from the corpus every boot and freshness-checked every transition. A hand-edited cache is overwritten on the next recompile and its hash won't match — detected. Rules change only by founder-ratified amendment (CER-5). |
| **Worker skips the bootstrap entirely** | Possible for a rogue session | The runtime entrypoint IS the bootstrap; a session that skips it has no RuntimeContext, so §7 enforcement (which reads RuntimeContext) has nothing to gate against — this is the one residual that depends on the *entrypoint* being wired as mandatory. Mitigation: the bootstrap is the Claude Code session entrypoint (a hook/first-action), and the absence of a boot.log content_hash for a session is itself an auditable incident. Stated as the residual (parchment-adjacent: a sovereign can bypass; detection remains). |

**Revision applied:** the two attacks that initially worked in draft — silent mandatory
truncation and stale-context accumulation — are closed by (a) never-truncate-mandatory +
COMPILE_FAILURE-on-overflow, and (b) K2 corpus-hash binding gating every transition. The one
irreducible residual (a session bypassing the entrypoint) is handled by detection (missing
boot.log), consistent with the parchment clause — the runtime cannot prevent a sovereign
bypass, but it makes it visible.

---

## Closing — the determinism guarantee, restated

```
same corpus state
  ⟹ same Load Manifest (§1, ordered + hashed)
  ⟹ same CompiledContext.content_hash (§2, deterministic compiler, mandatory never truncated)
  ⟹ same RuntimeContext (§3)
  ⟹ byte-identical worker prompts (§4, F-1 render)
  ⟹ identical pre-implementation behavior
```
Two Claude Code sessions months apart compile the same constitutional context and behave
identically before any implementation begins — **because the constitution is no longer 30–50
passive files a worker might read, but one content-hashed executable the runtime compiles,
injects, enforces, and refreshes.** The raw corpus remains the source of truth; the compiled
context is the executable interface; the content_hash is the proof they agree.

At self-hosting (S3+), this entire bootstrap is subsumed by the kernel's own `compile()` (§6)
and WRITE validator (§11) — PAEOS-9 is the specification of what those must do at session scope,
and the scaffold that performs it until they exist.
