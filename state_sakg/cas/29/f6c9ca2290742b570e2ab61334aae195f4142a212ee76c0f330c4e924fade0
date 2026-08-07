# 01 — Implementation Blocker Register

Method: implement mentally, file an issue at every point where an engineer must ask
"what should happen here?". Each issue: severity · the engineer's question · evidence ·
binding resolution · corpus impact. Issues marked ⚠K4 touch frozen kernel surfaces
(§14.5) and require amendment ceremony, not just clarification.

---

## BLOCKING

### B-01 ⚠K4 — Nobody is authorized to write Goal status transitions (or budget debits)
**Question:** "A goal gets verified — who writes the new Goal version with `status: verified`?"
**Evidence:** K4 §2.5 stores `status` as a field; K4 §5.3 mutation matrix: GENERATE may not
write status (X6), FALSIFY may not, SELECT may write only Evidence/DispatchRecords. The
founder may not. No actor may. Same hole for `budget.spent_direct` debits (§10.3 "at call
time" — by whom?).
**Resolution:** `status` and `budget` spent/delegated fields become **kernel-maintained**:
computed and written by the syscall/reactor layer as a consequence of evidence and debits.
Agents proposing objects containing these fields ⟹ FORBIDDEN_CLASS. Requires adding actor
`kernel` to the Provenance enum (see B-02).
**Impact:** K4 §2.3, §2.5, §5.3 amendment. F-SCHEMA fixtures affected.

### B-02 ⚠K4 — Provenance is agent-supplied, therefore forgeable
**Question:** "An agent's ProposedWrites include `author: {actor: syscall}` on a fake
execution evidence — what rejects it?"
**Evidence:** §5.2 agents return ProposedWrites; nothing states that WRITE stamps
provenance. A-09 checks `actor=syscall ∧ signature` — both fields are in the proposed
object, authored by the agent.
**Resolution:** Provenance is **never accepted from a proposer**. WRITE stamps `author`
server-side from the spawn lease (agent identity, role, model, adapter) or call context
(founder CLI, kernel). Proposed objects carrying author fields are rejected. Provenance
enum gains `kernel` (reactor/liveness writes, B-01).
**Impact:** K4 §2.3 amendment; I-SYS-RW contract; security model (06).

### B-03 — Schema self-reference + genesis ordering contradiction
**Question:** "Every Header requires `schema: HASH`. What goes in the schema field of the
schema artifacts themselves? And how can G1 (genesis record) precede G2 (schemas) if the
genesis record must pin a schema that doesn't exist yet?"
**Evidence:** K4 §2.2; R §12 G1 < G2. An object cannot contain its own hash.
**Resolution:** (a) A pinned **meta-schema sentinel** `schema: "sha256:meta.v1"` legal
only for schema-kind policy artifacts and the GenesisRecord; the meta-schema is defined
in the kernel spec text, not the store. (b) G1 and G2 become **one atomic WRITE batch**
(commit = transaction; PAEOS-3's "first artifact" ordering is logical order within the
batch, not commit order).
**Impact:** SC register (new entry); R §12; I-GEN; F-SCHEMA.

### B-04 — Store ref model vs git is undefined (two hash namespaces, one working tree)
**Question:** "Is `head/<object-id>` a git ref? Git refs point at git SHAs; kernel hashes
are SHA-256-of-JCS. Also: if speculation branches are git branches of the repo, checking
one out swaps the *kernel code* too. And how do parallel agents share one working tree?"
**Evidence:** K4 §2.1 refs; R §6 "WRITE batch = one git commit"; A-16 isolation. Nothing
reconciles the namespaces or the checkout problem.
**Resolution (binding):**
- Objects at `store/objects/<kernel-hash>.json` — path IS the kernel hash; git's own
  hashing is irrelevant/opaque.
- Kernel refs live in `store/refs/<namespace>.json` manifests, updated in the same commit
  as the object batch (the commit is the ref transaction). Git branch `main` is the only
  checked-out branch for the store.
- Speculation isolation via **git worktrees** on `refs/paeos/spec/<goal-id>/<n>`:
  work-product files only; kernel objects are always proposed back to main via WRITE.
- Snapshot token = git commit id (opaque).
**Impact:** I-STORE contract rewrite; R §6 correction; 05_STORAGE_MODEL.md is the spec.

### B-05 — Rendered context template is undefined; §6.1 only pins the manifest
**Question:** "Two conformant kernels produce identical manifests and *different rendered
prompts* — is that conformant? It changes agent behavior."
**Evidence:** K4 §6.3 "rendered: text — deterministic template over manifest"; §6.1
requires byte-identical **manifests** only.
**Resolution:** Pin the rendering grammar (section order = resolution order; fixed
delimiters; per-slot header lines carrying object id+version; verbatim bodies) and add
golden **rendered** fixtures. New backlog node **F-RENDER** (Wave 1, fable).
**Impact:** K4 §6 clarification; PAEOS-5 backlog is missing a node — PAEOS-5 defect.

### B-06 — "Tokens" is not a unit: truncation and CAP are tokenizer-dependent
**Question:** "Which tokenizer does deterministic truncation use? Claude's? Gemini's?
They disagree — so §6.4 truncation and K10's CAP produce different results per adapter,
breaking §6.1 determinism."
**Evidence:** K4 §6.4, K10, §10 budget `tokens`.
**Resolution:** Kernel-level unit is **bytes** (UTF-8). `CAP`, truncation, and the budget
dimension become byte-denominated; adapters map bytes→model tokens via
`capabilities().max_context_tokens` with a declared bytes-per-token factor.
**Impact:** ⚠K4 §6.4/§10/K10 amendment (unit change on a frozen surface); SC-09 restated in bytes.

### B-07 — The Check object does not exist: what does EXEC actually run?
**Question:** "EXEC takes `cmd: [string]` — run from which directory, against which files,
defined where? And the Router's `v=mechanical` consults a 'check inventory' — what object
is that?"
**Evidence:** K4 §7.1 read_set includes "check-inventory head" — no such object is
schema'd anywhere. F-SPI sandbox_exec has cmd but no working-set contract.
**Resolution:** New artifact convention: **Check** = Artifact
`media_type: application/x-paeos-check+json`, body `{cmd, input_selector, expected_exit,
claim_template}`. Check inventory = kernel ref `store/refs/checks.json` listing live
Check hashes. EXEC working dir = a materialized worktree of the goal's speculation branch
(B-04). Router `v=mechanical` ⟺ ∃ Check whose claim_template covers the evidence_spec.
**Impact:** F-SCHEMA scope (missing schemas, see H-04); K4 clarification; I-SYS-EXEC.

### B-08 — READ's filter language is undefined; the reconciler cannot find work
**Question:** "'type+filter' — what filter grammar? Without it I cannot implement the
reconciler's 'find dispatchable goals' loop at all."
**Evidence:** K4 §11 READ selector; R §1.15.
**Resolution:** Pin minimal selector DSL (closed set, no general queries):
`{type, kind?, status?, workload?, parent?, has_classification?}` conjunctive only.
Anything richer is a derived index (Investigation 12), never a syscall extension.
**Impact:** K4 §11 clarification; I-SYS-RW; I-RECON.

---

## HIGH

### H-01 — Write concurrency model unstated (single-writer lock)
Store commits race. **Resolution:** single-writer discipline: one global store write lease
held by the reconciler process; reactor writes via the same in-process queue; CLI takes
the lease briefly. Agents never hold it (they propose). IDENTITY_CONFLICT + bounded retry
with fresh snapshot (M-03) covers the rest. Distribution implications in 07/Inv-13.

### H-02 — Eternal-evidence attack: verdict read-sets are proposer-declared
An adversary-stance agent writes a verdict with an empty read_set ⟹ never expires.
**Resolution:** kernel stamps a mandatory minimum read-set on verdict evidence:
{goal version, context manifest hash} ∪ agent-declared extras. Declared-only was a hole.

### H-03 — Signature verification is not in the validator check registry
A-09 defines the emission side; no named check verifies Ed25519 against genesis trust
roots at WRITE. **Resolution:** new check id `SIG` in the registry (F-VAL fixture pair required).

### H-04 — Four schemas referenced but never defined; F-SCHEMA package scope is short
`SpawnRecord` (Provenance.spawn), `DispatchRecord` (§7), `FiringEvent` (§2.7),
`GenesisRecord` (§13.1 lists fields but not as a schema), `Check` (B-07), plus the
kernel refs manifests (B-04). **Wave 0 F-SCHEMA package is defective — scope must be
extended before assignment.**

### H-05 — Reactor must be state-driven, not event-driven
An event cursor ("last processed commit") is state outside the store or mutable state
inside it — either way a D1 violation. **Resolution:** reactor is **idempotent over
current state**: every cycle recomputes pending automatic transitions from the snapshot
(T1–T5 are functions of state, not of events). Crash catch-up is therefore free.

### H-06 — Boot-time working-tree recovery may destroy founder work
`git reset --hard` after crash would nuke founder drafts. **Resolution:** kernel-managed
paths (`store/**`) are reset to last commit on boot; all other paths untouched. Pin the
managed-path list in the store spec.

### H-07 — Speculation branch content is ambiguous
**Resolution (with B-04):** speculation worktrees contain work-product files ONLY.
Kernel objects never live on speculation refs. Candidate artifacts enter the store
as objects (with content refs) via ProposedWrites at return time.

### H-08 — "Dependents-set" (classification read-set) is an undefined object
**Resolution:** derived index materialized as artifact `store/refs/dependents.json`
(goal → integrated goals whose read-sets touched its outputs), rebuilt from evidence;
classification evidence binds to its hash. It is a cache with a canonical rebuild.

---

## MEDIUM

- **M-01** Ref manifest vs per-object git refs: pinned to manifests (B-04); note growth ⟹ shard by first hash byte at >10⁴ objects.
- **M-02** Founder authentication = OS account access. Accepted per H2 (parchment); document in 06.
- **M-03** Retry policy: IDENTITY_CONFLICT ⟹ ≤3 retries with fresh snapshot, then incident.
- **M-04** Context must be storable: manifest saved as Artifact at SPAWN so read-sets can bind to it (needed by H-02).
- **M-05** Hash-algorithm epoch migration (10-yr): new-epoch store with cross-epoch link map; accepted future cost, no present action.
- **M-06** Liveness must be incremental (reverse index updated per commit); full recompute only on cache rebuild. Mandatory, not optional (see 07/Inv-12).
- **M-07** Timestamp source: store commit time (single clock), never agent clocks.

## LOW

- **L-01** ULID uniqueness within a batch: generator must guarantee monotonic ULIDs per commit.
- **L-02** JCS float hazard: forbid non-integer numbers in kernel objects (uint only) — removes RFC 8785 number-canonicalization edge cases entirely.
- **L-03** `store/refs/*.json` history growth: refs are mutable files whose history lives in git — no compaction needed; note only.
- **L-04** Language/licensing constraints absent from G-ROOT template guidance (founder judgment slot exists; add reminder).
