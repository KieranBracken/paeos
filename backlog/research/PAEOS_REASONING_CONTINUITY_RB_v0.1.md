# PAEOS Reasoning Continuity Layer
## Requirements & Behavioral Specification (RB)
### Version 0.1 — Formal Design Baseline
### Status: Proposed / Pre-Implementation

---

## 0. Purpose

This document formalizes a **Reasoning Continuity Layer (RCL)** for PAEOS.

The RCL exists to allow a long-running PAEOS reasoning mission to survive:

- model/session termination,
- context-window compaction,
- provider changes,
- model changes,
- account changes,
- quota exhaustion,
- subagent creation,
- adversarial/fresh-context evaluation,
- process restarts,
- crashes,
- partial execution,
- and long periods between work sessions,

**without making a live chat transcript the authoritative source of continuity.**

The central architectural principle is:

> **The reasoning session is ephemeral; the reasoning state is durable.**

PAEOS and SAKG remain separate systems. The RCL belongs to PAEOS because its purpose is continuity of **orchestration and reasoning work**, not ownership of SAKG's knowledge graph or knowledge-store responsibilities.

The RCL may consume information from SAKG and may produce requests/results involving SAKG, but it must not collapse the two architectures into one.

---

# 1. Problem Definition

## 1.1 Current failure mode

A long-running engineering/reasoning effort can accumulate critical information inside a model conversation:

- architectural rationale,
- rejected approaches,
- unresolved questions,
- active hypotheses,
- implementation progress,
- discovered repository facts,
- test evidence,
- constraints,
- failures,
- decisions,
- and the reasoning behind decisions.

A new model/session may have access to the repository but still lack this reasoning history.

Conversely, simply transferring the entire conversation is undesirable because:

- context windows are finite,
- conversations become expensive,
- irrelevant history accumulates,
- summaries are lossy,
- provider-specific context mechanisms are not portable,
- and prior conclusions can anchor supposedly independent reviewers.

Therefore PAEOS requires an explicit continuity mechanism.

---

# 2. Design Goal

The RCL SHALL provide:

> **High-fidelity, provider-independent, auditable continuity of a PAEOS reasoning mission while preserving the ability to create genuinely fresh and bounded reasoning contexts.**

This contains two apparently opposing requirements:

1. **Continuity:** a successor agent must know enough to continue correctly.
2. **Independence:** a critic/fresh subagent must not inherit conclusions merely because they were previously asserted.

The RCL therefore does not define "context" as one undifferentiated blob.

Instead it models context as typed information with explicit provenance and inheritance rules.

---

# 3. Non-Goals

The RCL is NOT:

### 3.1 A replacement for SAKG

SAKG remains a separate architectural system.

The RCL must not become:

- the project knowledge graph,
- the authoritative repository of domain knowledge,
- a substitute for SAKG's constitutional structures,
- or a second hidden SAKG.

### 3.2 A generic chat-history archive

Raw transcripts may be retained, but the RCL is not merely a transcript database.

### 3.3 A model-specific memory system

The RCL must not depend on:

- Claude Memory,
- ChatGPT Memory,
- Gemini Memory,
- provider-specific conversation persistence,
- or any proprietary memory feature.

Provider memory may be used as an optional optimization, never as the authoritative continuity mechanism.

### 3.4 A single giant summary

A single `summary.md` is explicitly insufficient.

### 3.5 An automatic truth oracle

The RCL records state, evidence, decisions, uncertainty and provenance.

It must not silently convert model claims into facts.

---

# 4. Core Architectural Principle

The RCL SHALL separate:

```text
Raw Interaction
       ↓
Observed Evidence
       ↓
Interpretation / Hypothesis
       ↓
Proposal
       ↓
Decision
       ↓
Execution
       ↓
Verification
       ↓
Continuity State
```

These categories must not be conflated.

For example:

> "Agent proposed changing projection X"

is not equivalent to:

> "Projection X must be changed."

Likewise:

> "Agent stated that test Y passes"

is not equivalent to:

> "Test Y has been independently verified."

---

# 5. PAEOS / SAKG Boundary

The architectural relationship is:

```text
                     SENTIUM ECOSYSTEM
                            │
             ┌──────────────┴──────────────┐
             │                             │
           PAEOS                          SAKG
             │                             │
     reasoning/orchestration         knowledge architecture
             │                             │
             └──────────────┬──────────────┘
                            │
                     explicit interfaces
```

PAEOS may:

- invoke SAKG,
- retrieve SAKG information,
- request analysis involving SAKG,
- pass SAKG artifacts to agents,
- record references to SAKG artifacts.

SAKG may:

- provide knowledge/evidence,
- provide precedent/context,
- expose its defined contracts.

The RCL itself remains a PAEOS subsystem.

A continuity record may contain references such as:

```text
sakg://decision/D-017
sakg://precedent/P-042
sakg://artifact/A-109
```

but those references do not make the RCL the owner of the referenced information.

---

# 6. Continuity Model

The RCL SHALL model a long-running effort as a **Mission**.

A Mission is a durable reasoning/work unit with:

- a stable identity,
- objective,
- scope,
- constraints,
- current state,
- decisions,
- evidence,
- unresolved questions,
- active work,
- provenance,
- and history.

A Mission may contain multiple:

- sessions,
- agents,
- model invocations,
- subagents,
- tasks,
- branches,
- checkpoints,
- decisions,
- and verification events.

Conceptually:

```text
Mission
 ├── Session
 │    ├── Invocation
 │    ├── Invocation
 │    └── Checkpoint
 │
 ├── Session
 │    ├── Invocation
 │    └── Checkpoint
 │
 ├── Decision history
 ├── Evidence
 ├── Invariants
 ├── Open questions
 ├── Work state
 └── Submissions / branches
```

The Mission is persistent even when every model session disappears.

---

# 7. Required State Categories

The RCL SHALL maintain at least the following state classes.

## 7.1 Mission State

Contains:

- mission ID,
- title,
- objective,
- scope,
- success criteria,
- current phase,
- status,
- owner/orchestrator,
- creation timestamp,
- last checkpoint,
- current task.

Example:

```yaml
mission_id: M-SAKG-S1
objective: "Complete Mission 1 baseline"
phase: "S1+S2"
status: "active"
```

---

## 7.2 Facts

A fact is an observed or authoritative statement supported by evidence.

Every durable fact SHOULD have:

- fact ID,
- statement,
- source,
- provenance,
- confidence/status,
- timestamp,
- verification status.

Facts must not be created solely because a model asserted them unless explicitly recorded as an unverified claim.

---

## 7.3 Constraints

Constraints describe what the agent is not permitted to violate.

Examples:

- constitutional requirements,
- API contracts,
- repository constraints,
- safety rules,
- deterministic replay requirements,
- compatibility requirements.

Constraints should have explicit authority/source.

---

## 7.4 Invariants

Invariants are properties that must remain true throughout the mission.

Each invariant SHOULD contain:

- invariant ID,
- statement,
- authority,
- verification method,
- current status.

Example:

```yaml
invariant_id: INV-017
statement: "Projection output remains deterministic under replay."
authority: "SAEOS-1 §..."
verification:
  - test_id: T-REPLAY-04
status: "verified"
```

---

## 7.5 Decisions

A decision records an adopted choice.

A decision SHOULD include:

- decision ID,
- subject,
- selected option,
- alternatives considered,
- rationale,
- supporting evidence,
- authority,
- status,
- reversibility,
- affected components,
- timestamp,
- deciding agent/process.

Decisions are not immutable truth. They are durable commitments with explicit status.

Possible statuses:

```text
proposed
accepted
rejected
superseded
reopened
disputed
```

---

## 7.6 Rejected Approaches

Rejected approaches deserve first-class representation.

This is critical because otherwise a successor agent may repeatedly rediscover and re-propose an already rejected solution.

A rejection SHOULD record:

- rejected proposal,
- reason,
- evidence,
- decision ID,
- conditions under which reconsideration is allowed.

The final field is important.

A rejection should not become an eternal prohibition if its underlying assumptions later change.

---

## 7.7 Open Questions

Questions that remain unresolved must be preserved explicitly.

Each question SHOULD contain:

- question ID,
- statement,
- why it matters,
- current hypotheses,
- evidence,
- owner,
- priority,
- blocking status.

Do not force uncertain questions into premature decisions merely to simplify continuity.

---

## 7.8 Hypotheses

A hypothesis is a candidate explanation or belief that has not achieved sufficient verification.

Example:

```yaml
hypothesis_id: H-021
statement: "The projection race originates in..."
status: "unverified"
supporting_evidence: [...]
contradicting_evidence: [...]
```

This prevents uncertainty from being lost during handoff.

---

## 7.9 Work State

Tracks execution:

- completed work,
- current work,
- blocked work,
- planned work,
- failed attempts,
- files changed,
- tests run,
- commits,
- external dependencies.

---

## 7.10 Evidence

Evidence is an observation that can support or challenge reasoning.

Examples:

- test output,
- source inspection,
- repository state,
- compiler output,
- runtime behavior,
- SAKG reference,
- constitutional clause,
- external documentation.

Evidence MUST retain provenance.

---

# 8. Provenance

Every durable reasoning object SHOULD be traceable to its origin.

Possible provenance:

```text
model observation
user instruction
repository inspection
test execution
SAKG retrieval
external source
PAEOS policy
constitutional document
human decision
derived inference
```

A derived conclusion should point to the evidence from which it was derived.

Example:

```text
Decision D-042
   ↓ based_on
Evidence E-103
Evidence E-109
Constraint C-017
   ↓ generated_by
Agent Invocation I-228
```

This creates a reasoning lineage.

---

# 9. Raw Transcript Preservation

Raw interactions SHOULD be retained where feasible.

The transcript is:

> **historical evidence, not authoritative state.**

The RCL should therefore have:

```text
raw interaction
      │
      ↓
structured extraction
      │
      ↓
continuity state
```

If structured extraction is later found to be incorrect, the original interaction remains available for reconstruction.

The system must never make the continuity state impossible to audit back to its source.

---

# 10. Checkpoints

A checkpoint is a durable snapshot of reasoning state.

A checkpoint SHOULD be created:

- before changing providers/models,
- before ending a substantial session,
- after completing a major task,
- after a significant architectural decision,
- before risky implementation,
- after verification,
- before quota exhaustion when known,
- after a failed attempt that changes understanding.

A checkpoint should contain:

```text
checkpoint_id
mission_id
parent_checkpoint_id
timestamp
repository_revision
state_revision
active_task
recent_changes
decisions
invariants
open_questions
known_failures
next_action
required_context
```

Checkpoints should be append-only or versioned rather than destructively overwritten.

---

# 11. Context Packages

The RCL SHALL be able to construct a **Context Package** for a new agent.

A Context Package is not necessarily the entire continuity state.

It is a task-specific projection of the state.

Example:

```text
Mission objective
+ relevant constraints
+ relevant invariants
+ relevant decisions
+ relevant evidence
+ relevant repository files
+ current task
+ unresolved questions
+ required instructions
```

This is how PAEOS avoids dumping an entire project's history into every prompt.

---

# 12. Context Policies

The RCL SHOULD support explicit context policies.

## FULL_CONTINUATION

Used when replacing an interrupted primary agent.

Include:

- current mission state,
- relevant historical decisions,
- active constraints,
- unresolved questions,
- recent interaction context,
- required repository context.

Purpose:

> Continue the same reasoning process.

---

## MINIMUM_SUFFICIENT

Used for a bounded task.

Include only the information necessary to perform the task correctly.

Purpose:

> Efficient reasoning without unnecessary historical contamination.

---

## FRESH

Create a new reasoning process with relevant facts and constraints but without prior conclusions unless explicitly required.

Purpose:

> Independent reasoning.

---

## BLIND

The agent receives the evaluation target and governing requirements but does not receive the previous agent's conclusion.

Purpose:

> Reduce anchoring.

---

## ADVERSARIAL

The agent receives sufficient evidence to challenge a proposal but is explicitly instructed not to preserve the proposal's assumptions.

Purpose:

> Falsification.

---

## RECONSTRUCTION

A successor attempts to rebuild the current reasoning state from durable artifacts.

Purpose:

> Test whether continuity is actually portable.

---

# 13. The Critical Principle: Facts Without Beliefs

The RCL SHOULD distinguish between:

### Inherited evidence

Allowed.

### Inherited constraints

Allowed.

### Inherited requirements

Allowed.

### Inherited previous decisions

Allowed during normal continuation.

### Inherited conclusions

Policy-dependent.

### Inherited persuasive reasoning

Must be explicitly controlled.

### Inherited uncertainty

Must be preserved.

This gives PAEOS the ability to create a critic who receives:

```text
requirements: YES
facts: YES
evidence: YES
constraints: YES
previous conclusion: NO
previous rationale: NO
```

This is substantially more useful than either:

> "give the critic everything"

or:

> "give the critic nothing."

---

# 14. Agent Identity

Every model invocation SHOULD have a durable identity.

An Invocation record SHOULD contain:

```text
invocation_id
mission_id
parent_invocation_id
agent_role
provider
model
model_version
session_id
context_policy
context_package_id
start_time
end_time
input_state_revision
output_state_revision
```

This makes model switching auditable.

For example:

```text
I-201
Claude / model X
       ↓
checkpoint C-81
       ↓
I-202
Gemini / model Y
       ↓
checkpoint C-82
```

The second invocation is therefore a successor, not an unrelated chat.

---

# 15. Provider Independence

The continuity representation MUST be provider-neutral.

It must not require:

- Claude-specific memory objects,
- OpenAI-specific conversation IDs,
- Gemini-specific chat history,
- proprietary prompt formats.

Provider adapters may translate a Context Package into a provider-specific request.

Conceptually:

```text
PAEOS Continuity State
        │
        ↓
Context Package
        │
 ┌──────┼─────────┐
 ↓      ↓         ↓
Claude Gemini   Codex
adapter adapter adapter
```

---

# 16. Model Switching

Model switching SHALL be treated as a first-class operation.

Example:

```text
SWITCH_MODEL
mission: M-001
from: claude
to: gemini
checkpoint: C-118
context_policy: FULL_CONTINUATION
```

The receiving model must be told:

1. it is continuing an existing mission;
2. which checkpoint it is continuing from;
3. what state is authoritative;
4. what remains unresolved;
5. what work is currently active;
6. what it must verify before acting.

---

# 17. Session Handoff Contract

A handoff MUST answer at minimum:

### What were we trying to accomplish?

### What has definitely been completed?

### What changed?

### Why did we change it?

### What evidence supports the change?

### What remains incomplete?

### What assumptions are currently active?

### What approaches were rejected?

### What is uncertain?

### What must the successor do next?

### What must the successor NOT assume?

That last question is deliberately included because negative knowledge is often lost during handoff.

---

# 18. Handoff Example

A handoff might contain:

```yaml
mission: M-SAKG-001
checkpoint: C-019

objective:
  "Complete the S1/S2 projection baseline."

completed:
  - "Projection dispatcher implemented."
  - "Replay determinism test added."

changed_paths:
  - "paeos/projection.py"
  - "tests/test_projection_replay.py"

accepted_decisions:
  - D-031
  - D-032

rejected:
  - R-014:
      reason: "Would violate deterministic replay invariant."

active_invariants:
  - INV-007
  - INV-011
  - INV-017

open_questions:
  - Q-009

known_failures:
  - "Integration test X remains failing."

next_action:
  "Investigate X before modifying projection semantics."

do_not_assume:
  - "Passing unit tests imply baseline completion."
  - "The rejected approach is invalid under all future conditions."
```

---

# 19. Continuity Integrity

A successor should not blindly trust the continuity package.

The RCL SHOULD distinguish:

```text
AUTHORITATIVE
VERIFIED
SUPPORTED
UNVERIFIED
DISPUTED
STALE
SUPERSEDED
```

A successor can therefore reason:

> "The handoff says this invariant is verified, but the repository revision differs from the checkpoint, so I must revalidate it."

This is essential after model/provider changes.

---

# 20. Repository Synchronization

A checkpoint SHOULD record the repository state from which it was generated.

At minimum:

- Git commit,
- branch,
- dirty/clean state,
- relevant changed paths,
- test status.

This prevents a reasoning state from being incorrectly applied to a different code state.

Conceptually:

```text
Checkpoint C-100
      │
      ├── state revision S-100
      └── git revision G-100
```

A successor operating on `G-105` must be aware that it is no longer operating on the exact code associated with C-100.

---

# 21. State Versioning

Continuity state MUST be versioned.

A state transition should resemble:

```text
S-100
  ↓
agent action
  ↓
S-101
```

Never silently mutate historical state.

This permits:

- rollback,
- audit,
- comparison,
- reconstruction,
- conflict detection.

---

# 22. Concurrent Agents

PAEOS may eventually have multiple agents operating simultaneously.

The RCL therefore SHOULD support branches.

Example:

```text
                    S-100
                      │
             ┌────────┴────────┐
             ↓                 ↓
          Branch A          Branch B
             │                 │
        proposal A         proposal B
             │                 │
             └────────┬────────┘
                      ↓
                  Reconcile
                      ↓
                    S-101
```

Branches must not automatically become canonical state.

A reconciliation operation determines which results become authoritative.

---

# 23. Subagent Continuity

Subagents are separate reasoning processes.

A parent may create:

```text
Parent Invocation
       │
       ├── Analyst
       ├── Critic
       ├── Implementer
       └── Verifier
```

Each receives an explicit Context Package.

The parent must specify whether each child:

- inherits conclusions,
- inherits only evidence,
- operates independently,
- is adversarial,
- or is continuing a prior child mission.

---

# 24. Fresh-Critic Sandbox

The RCL SHOULD support a dedicated fresh-critic mode.

Example:

```text
Proposal P-044
       │
       ↓
PAEOS extracts:
  requirements
  constraints
  evidence
  target artifact
       │
       ↓
NEW SESSION
       │
       ↓
Critic
```

The critic receives:

```text
YES:
- governing requirements
- relevant evidence
- implementation
- test results

NO:
- original agent's conclusion
- original agent's confidence
- persuasive rationale
- irrelevant conversation history
```

The resulting critique becomes new evidence.

It does not automatically invalidate the original decision.

---

# 25. Memory Formation

The RCL SHOULD NOT automatically convert every conversational statement into durable state.

A statement enters durable state only through a classification process.

Possible classifications:

```text
OBSERVATION
FACT
CONSTRAINT
DECISION
PROPOSAL
HYPOTHESIS
QUESTION
REJECTION
EVIDENCE
RESULT
FAILURE
```

The system should preserve uncertainty where classification is ambiguous.

---

# 26. Promotion Rules

A model-generated statement can progress through states.

Example:

```text
claim
 ↓
candidate observation
 ↓
evidence collected
 ↓
verified fact
```

Or:

```text
proposal
 ↓
review
 ↓
decision
 ↓
implementation
 ↓
verification
 ↓
accepted state
```

This prevents hallucinated model output from silently becoming institutional memory.

---

# 27. Contradiction Handling

If two durable records conflict, PAEOS MUST NOT silently overwrite one.

Example:

```text
Fact F-100:
"X is required."

Fact F-144:
"X is not required."
```

The RCL should create:

```text
CONFLICT C-009
```

with references to both records.

Resolution then becomes a reasoning task.

---

# 28. Staleness

Continuity state can become stale.

A record SHOULD be marked stale when:

- referenced code changes,
- underlying documentation changes,
- a decision is superseded,
- evidence becomes invalid,
- assumptions change.

The system should prefer:

> "This was true at checkpoint C-100"

over:

> "This is true."

Temporal provenance matters.

---

# 29. Security / Trust Boundary

The RCL should assume model-generated state is potentially incorrect.

Never allow a model to silently:

- rewrite constitutional authority,
- change trust levels,
- promote an assertion to an authoritative fact,
- erase historical decisions,
- erase rejected approaches,
- remove audit history.

Destructive state operations should require explicit policy authorization.

---

# 30. Failure Recovery

If a model crashes during execution:

```text
last checkpoint
      ↓
inspect repository
      ↓
detect uncommitted changes
      ↓
reconstruct state
      ↓
resume or rollback
```

The RCL must not assume that the last model message represents successful execution.

Repository evidence and test results determine actual execution state.

---

# 31. Context Construction Algorithm

A conceptual context construction pipeline:

```text
1. Identify mission.
2. Identify target task.
3. Identify required role.
4. Load authoritative constraints.
5. Load relevant invariants.
6. Load relevant facts/evidence.
7. Load relevant decisions according to context policy.
8. Load unresolved questions.
9. Load repository state.
10. Load task-specific artifacts.
11. Apply independence/anchoring rules.
12. Produce Context Package.
13. Record package hash/version.
14. Invoke model.
```

The exact implementation is intentionally left open to the implementation agent.

---

# 32. Context Budgeting

The RCL SHOULD rank context by relevance rather than blindly including everything.

Possible priority:

```text
P0 — mandatory
    constitutional constraints
    current objective
    critical invariants

P1 — highly relevant
    active decisions
    directly relevant evidence
    current implementation

P2 — useful
    related history
    prior failures
    nearby decisions

P3 — optional
    broader historical context

P4 — archival
    raw transcript
```

If context budget is limited, lower-priority material can be omitted without corrupting the core state.

---

# 33. Context Compression

Compression is permitted but MUST be provenance-preserving.

Bad:

```text
"We decided to use projection X."
```

Better:

```text
Decision D-031:
Selected X.
Alternatives A/B considered.
Rejected A because INV-017.
Evidence E-100 and E-103.
Decision made at checkpoint C-018.
```

Compression should reduce verbosity, not remove semantic structure.

---

# 34. Continuity Quality Metric

PAEOS SHOULD eventually measure continuity quality.

Possible metrics:

### Reconstruction accuracy

Can a fresh agent correctly reconstruct the mission state?

### Decision preservation

Does the successor know why important decisions were made?

### Constraint preservation

Does it preserve governing invariants?

### Negative-knowledge preservation

Does it know which approaches were rejected and why?

### Uncertainty preservation

Does it know what remains uncertain?

### Execution continuity

Can it continue the task without redoing substantial work?

### Provider portability

Can another model continue correctly?

---

# 35. The Reconstruction Test

A particularly important acceptance test:

> Give a fresh model only the durable continuity package and repository. Ask it to reconstruct the mission state. Compare its reconstruction against the authoritative state.

This should become a formal PAEOS test.

If the successor says:

> "The previous agent decided X because Y"

when Y was never actually established, continuity extraction has failed.

---

# 36. Gold-Standard Continuity Test

A stronger test:

```text
Agent A
  ↓
works for N interactions
  ↓
checkpoint
  ↓
destroy session
  ↓
Agent B receives only:
  - repository
  - continuity state
  - context package
  ↓
Agent B continues
```

Compare:

- decisions,
- implementation quality,
- test outcomes,
- architectural consistency,
- unnecessary rediscovery,
- contradictions.

A successful RCL should make the transition operationally boring.

---

# 37. Implementation Requirements

The implementation agent SHOULD determine the exact technology after inspecting the existing PAEOS architecture.

However, the implementation MUST preserve these principles:

1. Provider neutrality.
2. Durable state.
3. Versioning.
4. Provenance.
5. Explicit context policies.
6. Separation of evidence and conclusions.
7. Raw-history recoverability.
8. Repository-state awareness.
9. Crash recovery.
10. Fresh-session support.
11. Adversarial-session support.
12. Model switching.
13. Subagent lineage.
14. Auditability.
15. No hidden dependency on proprietary chat memory.

---

# 38. Suggested Logical Components

The implementation may naturally divide into:

```text
continuity/
├── models/
│   ├── mission
│   ├── decision
│   ├── evidence
│   ├── invariant
│   ├── question
│   ├── hypothesis
│   ├── checkpoint
│   ├── invocation
│   └── context_package
│
├── state/
│   ├── store
│   ├── versioning
│   └── reconciliation
│
├── extraction/
│   ├── classifier
│   ├── state_updater
│   └── provenance
│
├── context/
│   ├── builder
│   ├── policies
│   ├── ranking
│   └── compression
│
├── handoff/
│   ├── checkpoint
│   ├── export
│   └── import
│
├── providers/
│   ├── provider-neutral interface
│   └── adapters
│
└── verification/
    ├── reconstruction
    ├── integrity
    └── portability
```

This is illustrative, not a mandated directory layout.

---

# 39. API-Level Conceptual Interface

The RCL should expose operations conceptually equivalent to:

```python
create_mission(...)
get_mission(...)
record_observation(...)
record_evidence(...)
record_decision(...)
record_rejection(...)
record_hypothesis(...)
record_question(...)
record_invariant(...)
create_checkpoint(...)
restore_checkpoint(...)
build_context(...)
create_handoff(...)
create_fresh_context(...)
create_adversarial_context(...)
start_invocation(...)
complete_invocation(...)
record_result(...)
detect_conflict(...)
reconcile_branch(...)
export_continuity(...)
import_continuity(...)
```

Exact names and implementation should follow existing PAEOS conventions.

---

# 40. Canonical State vs Derived Views

The RCL should maintain a distinction between:

### Canonical state

Durable structured records.

### Derived views

Generated:

- summaries,
- handoffs,
- prompts,
- context packages,
- dashboards,
- reports.

A generated summary must never become authoritative merely because it is convenient.

---

# 41. Auditability

Every state mutation SHOULD be attributable to:

```text
who/what:
  user
  PAEOS
  model
  tool
  verifier

when:
  timestamp

why:
  triggering task

based_on:
  evidence / prior state

result:
  new state revision
```

This allows later investigation of:

> "Why does PAEOS currently believe this?"

---

# 42. Human Authority

The RCL should preserve a distinction between:

- model proposal,
- PAEOS decision,
- human instruction,
- authoritative constitutional requirement.

A model must not acquire authority simply by writing something into continuity state.

---

# 43. Economic Objective

The RCL is also intended to reduce unnecessary dependence on expensive model context.

Instead of repeatedly paying for the entire historical conversation, PAEOS can construct a compact but semantically rich Context Package.

The objective is NOT:

> minimize tokens at all costs.

The objective is:

> **minimize unnecessary context while preserving all information necessary for correct reasoning.**

Quality takes precedence over token savings.

---

# 44. Relationship to Model Selection

Once the RCL exists, PAEOS can treat models as replaceable reasoning workers.

For example:

```text
Task
 ↓
PAEOS determines required capability
 ↓
select provider/model
 ↓
construct context package
 ↓
invoke
 ↓
validate result
 ↓
update continuity
```

Therefore the RCL is an enabling layer for future model routing.

It should not itself hard-code a preferred provider.

---

# 45. Relationship to PAEOS Councils

Councils and veto systems can consume the RCL.

For example:

```text
Mission
  ↓
Proposal
  ↓
Council
 ├── Agent A
 ├── Agent B
 ├── Agent C
 └── Adversarial Agent
  ↓
Decision
  ↓
RCL
```

Each participant can have a controlled context policy.

A council member can be:

- continuation-aware,
- fresh,
- blind,
- adversarial,
- specialist,
- or evidence-only.

This gives PAEOS fine-grained control over epistemic independence.

---

# 46. Relationship to SAKG

SAKG may become one of the sources used to construct context.

For example:

```text
PAEOS task
    ↓
continuity state
    +
SAKG retrieval
    +
repository evidence
    ↓
Context Package
    ↓
model
```

The RCL should record that SAKG material was used, but should not duplicate large amounts of SAKG state unless required for immutable evidence/provenance.

---

# 47. Recommended First Implementation Scope

Do NOT attempt to implement the entire theoretical system immediately.

The first implementation should establish the smallest reliable vertical slice:

```text
Mission
  ↓
Checkpoint
  ↓
Structured continuity state
  ↓
Context Package
  ↓
Fresh successor session
  ↓
Continuation
```

Minimum required records:

```text
Mission
Decision
Evidence
Invariant
OpenQuestion
Checkpoint
Invocation
ContextPackage
```

Then add:

```text
Hypothesis
Rejection
Conflict
Branch
Adversarial context
Provider adapters
```

after the core mechanism is proven.

---

# 48. Phase 1 Acceptance Criteria

The first implementation is acceptable only if:

### AC-01
A mission can be created and persisted.

### AC-02
A mission can survive process restart.

### AC-03
A checkpoint can be created.

### AC-04
The checkpoint records repository revision.

### AC-05
Important decisions retain rationale and provenance.

### AC-06
Rejected approaches are preserved.

### AC-07
Open questions survive handoff.

### AC-08
A context package can be generated.

### AC-09
A fresh model/session can consume the context package.

### AC-10
The fresh model can continue the task without access to the original conversation.

### AC-11
A fresh/adversarial package can intentionally exclude previous conclusions.

### AC-12
Raw historical interactions remain recoverable.

### AC-13
State is versioned.

### AC-14
Provider/model identity is recorded.

### AC-15
The implementation does not introduce architectural coupling between PAEOS and SAKG.

---

# 49. Phase 2 Acceptance Criteria

After the first vertical slice:

- model switching,
- multiple provider adapters,
- subagent lineage,
- branch/reconciliation,
- contradiction detection,
- staleness detection,
- automated continuity extraction,
- context ranking,
- reconstruction testing.

---

# 50. Explicit Anti-Patterns

The implementation MUST avoid:

### Anti-pattern 1
One giant `memory.md`.

### Anti-pattern 2
Treating model statements as facts.

### Anti-pattern 3
Overwriting historical decisions.

### Anti-pattern 4
Deleting rejected approaches.

### Anti-pattern 5
Using provider-specific memory as the authoritative state.

### Anti-pattern 6
Passing the entire project history to every agent.

### Anti-pattern 7
Giving an adversarial critic the original conclusion when blind evaluation is required.

### Anti-pattern 8
Creating a new summary without provenance.

### Anti-pattern 9
Ignoring repository revision during handoff.

### Anti-pattern 10
Embedding SAKG inside PAEOS.

---

# 51. Design Principle Summary

The RCL should implement the following transformation:

```text
                    TODAY

        "The model remembers."
                  ↓
              FRAGILE


                    TARGET

        "PAEOS preserves state."
                  ↓
             PROVIDER-INDEPENDENT
             SESSION-INDEPENDENT
             MODEL-INDEPENDENT
             AUDITABLE
             RECOVERABLE
```

The model is therefore a worker.

The session is temporary.

The repository is authoritative for implementation.

SAKG is authoritative for its own knowledge domain.

PAEOS is authoritative for orchestration and reasoning-state management.

The RCL preserves the continuity required to move between workers without losing the intellectual state of the mission.

---

# 52. Final Architectural Principle

The most important requirement in this document is:

> **Continuity must preserve what is necessary to continue reasoning, while independence must preserve the ability to reason without inheriting conclusions.**

Therefore:

```text
CONTINUITY ≠ FULL TRANSCRIPT

MEMORY ≠ KNOWLEDGE

SUMMARY ≠ STATE

CLAIM ≠ FACT

PROPOSAL ≠ DECISION

DECISION ≠ TRUTH

CONTEXT ≠ BELIEF

MODEL ≠ REASONING SYSTEM

SESSION ≠ MISSION
```

PAEOS should be able to terminate a model session, start another model session hours or days later, provide it with a correctly constructed context package, and have that model continue the mission as though the reasoning process had been handed over intentionally rather than accidentally.

That is the fundamental purpose of the Reasoning Continuity Layer.

---

# 53. Implementation Brief for Gemini Pro

When implementing this specification, the implementation agent SHOULD:

1. Inspect the existing PAEOS repository before changing anything.
2. Map current PAEOS orchestration, agent, task, state, persistence, and context mechanisms.
3. Identify existing mechanisms that already partially satisfy this specification.
4. Do not duplicate existing abstractions.
5. Do not assume the proposed directory structure is mandatory.
6. Preserve PAEOS's existing architectural conventions.
7. Keep PAEOS and SAKG separate.
8. Implement the smallest coherent vertical slice first.
9. Add tests before broadening the subsystem.
10. Demonstrate a real session → checkpoint → fresh-session → continuation flow.
11. Demonstrate a fresh/adversarial context where the previous conclusion is intentionally withheld.
12. Report any architectural conflicts with this RB rather than silently compromising them.
13. Distinguish implementation requirements from design suggestions in this document.
14. Do not introduce provider-specific dependencies into the canonical continuity model.
15. Before declaring completion, perform a reconstruction/portability test.

The implementation agent should treat this document as the **behavioral and architectural baseline**, not as an instruction to blindly implement every illustrative data structure or directory shown above.

---

# Addendum: PAEOS_REASONING_CONTINUITY_RB_v0.2

## Research Backlog Addendum — Native Continuity, Epistemic Isolation & External-Agent Integration

**Status:** RESEARCH / NOT AUTHORIZED FOR IMPLEMENTATION  
**Parent:** `PAEOS_REASONING_CONTINUITY_RB_v0.1`  
**Purpose:** Capture architectural requirements and research questions discovered after v0.1 so they are not lost before RCL implementation begins.

---

# 0. Purpose of This Addendum

`PAEOS_REASONING_CONTINUITY_RB_v0.1` established the initial Reasoning Continuity Layer (RCL) concept:

> A long-running reasoning mission must be able to survive model/session/provider changes without treating ephemeral model chat history as authoritative state.

Subsequent investigation exposed several additional requirements.

Most importantly:

**PAEOS already has a functioning orchestration architecture.**

The objective is therefore NOT to build a second orchestration system beside PAEOS, nor to make Antigravity itself the reasoning orchestrator.

Instead:

> External environments such as Antigravity, Claude Code, Gemini, Codex, etc. should act as model/runtime environments underneath PAEOS, while PAEOS remains the authoritative orchestration and governance layer.

The RCL must therefore be designed *inside the existing PAEOS architecture*.

This document records the additional research required before implementation.

---

# 1. Canonical PAEOS Lifecycle Must Be Derived, Not Assumed

## Problem

Earlier RCL designs assumed simplified workflows such as:

```text
DESIGN
  ↓
PLAN
  ↓
IMPLEMENT
  ↓
COURT
  ↓
REVIEW
  ↓
SEAL
```

This was discovered to be an incomplete representation of the actual PAEOS lifecycle.

PAEOS contains a substantially richer layered workflow / governance architecture.

Therefore the RCL must NOT encode a simplified lifecycle based on assumptions.

## Research Requirement

Before implementing RCL, derive the actual canonical lifecycle from:

1. PAEOS architectural documentation
2. `kernel/types.py`
3. `runtime/orchestrator/`
4. `cli/paeos.py`
5. stage definitions
6. gates
7. Court
8. InformationBarrierManager
9. Review / Seal mechanisms
10. autonomous execution paths
11. existing tests and invariants

The resulting artifact should explicitly document:

* every canonical layer/stage
* entry conditions
* exit conditions
* artifacts produced
* governance checks
* context transitions
* model invocations
* state mutations
* veto / rejection paths
* retry / remand paths
* sealing conditions
* human intervention points
* persistence boundaries

## Acceptance Criterion

No RCL implementation should proceed until the canonical PAEOS lifecycle has been reconstructed from the actual code/documentation.

The lifecycle model must be treated as **architecture evidence**, not a model-generated assumption.

---

# 2. RCL Must Use the Existing PAEOS Orchestration Path

## Problem

A previous experimental `InvestigationLoop` demonstrated that PAEOS primitives can execute isolated branches, but the experiment bypassed the canonical PAEOS execution path.

It directly instantiated components such as:

* `Ledger`
* `CAS`
* `CapabilityBroker`
* `AgentDispatcher`
* `StagePlaybook`
* `ClaudeCodeRuntime`

and therefore bypassed parts of the canonical governance lifecycle.

This is not an acceptable pattern for RCL.

## Requirement

RCL must operate through the existing PAEOS runtime/orchestration architecture.

The canonical path should remain conceptually:

```text
External Launch / Intake
        ↓
PAEOS Control Plane
        ↓
Canonical PAEOS Orchestrator
        ↓
Governance / Gates / Court / Barriers
        ↓
Stage Execution
        ↓
Agent Dispatch
        ↓
Runtime / Model
```

RCL should become a **capability of PAEOS**, not an alternative orchestrator.

## Anti-Pattern

Do NOT create:

```text
Antigravity
   ↓
custom RCL orchestrator
   ↓
direct AgentDispatcher
```

when the canonical PAEOS path already exists.

---

# 3. External Agent Environments Must Be Treated as Runtime Providers

## Core Insight

Antigravity, Claude Code, Gemini, Codex, etc. should not become competing orchestration layers.

They are execution environments capable of:

* providing models
* creating subprocesses
* creating isolated workspaces
* running tools
* launching subagents
* maintaining temporary conversational context

PAEOS should remain responsible for:

* mission state
* governance
* stage transitions
* capability authorization
* context policy
* provenance
* checkpoints
* continuity
* verification
* sealing

## Research Question

Determine the cleanest PAEOS runtime abstraction allowing:

```text
PAEOS
  ↓
Runtime Adapter
  ├── Claude Code
  ├── Gemini / Antigravity
  ├── Codex
  ├── local model
  └── future provider
```

without changing the PAEOS constitutional layer for each provider.

---

# 4. Antigravity Sandbox Integration

## Motivation

Antigravity provides capabilities that can be extremely useful for PAEOS:

* isolated workspaces
* subagents
* parallel execution
* model switching
* large-context environment
* autonomous task execution

However, Antigravity must not become the source of truth.

## Proposed Model

When PAEOS needs an agent invocation, it may request an external runtime to create an isolated execution environment.

Conceptually:

```text
PAEOS
  │
  │ capability + context package
  ↓
Antigravity Runtime Adapter
  │
  ├── Sandbox
  │
  ├── Model
  │
  └── Optional subagents
  │
  ↓
Result / Artifacts / Evidence
  │
  ↓
PAEOS
```

The sandbox is disposable.

The authoritative state remains in PAEOS.

## Critical Rule

Never treat the Antigravity conversation/session itself as authoritative continuity state.

If the sandbox disappears, PAEOS must still be able to reconstruct the mission.

---

# 5. Fresh-Agent / Context-Policy Integration

RCL should not mean:

> Give every subsequent model the entire previous conversation.

That creates anchoring, context bloat, and reasoning contamination.

Instead, continuity should operate through **controlled context inheritance**.

The RCL should allow PAEOS to create a new model session with a deliberately selected context package.

Potential policies include:

### FULL_CONTINUATION

For provider/session handoff.

```text
Facts
Evidence
Constraints
Active Decisions
Relevant Rationale
Rejected Paths
Open Questions
Uncertainty
Artifacts
Current Objective
```

### MINIMUM_SUFFICIENT

For execution workers.

```text
Task
Relevant Facts
Relevant Constraints
Required Artifacts
Acceptance Criteria
```

### FRESH

For independent design.

```text
Requirements
Constraints
Evidence
Relevant Failures
```

but deliberately exclude prior conclusions.

### BLIND_CONCLUSION

For independent audit.

```text
Requirements
Constraints
Artifacts
Objective Evidence
Tests
```

while excluding:

```text
Decision
Rationale
Confidence
Recommendation
```

### ADVERSARIAL

For attack of an existing architecture.

The exact policy taxonomy should be researched against existing PAEOS InformationBarrierManager / ContextCompiler capabilities before implementation.

---

# 6. PAEOS Subagents as Fresh Reasoning Sessions

A major design question is whether PAEOS should intentionally create fresh agent sessions for specific reasoning roles.

The preferred conceptual model is:

```text
Canonical Mission State
        │
        ├──→ Fresh Researcher
        │
        ├──→ Fresh Architect
        │
        ├──→ Fresh Critic
        │
        ├──→ Fresh Adversary
        │
        └──→ Fresh Synthesizer
```

Each receives the **minimum context required for its role**.

The subagent's conversational history is not authoritative.

Its output becomes an artifact/evidence/result that PAEOS evaluates and persists.

This gives PAEOS both:

* continuity of the overall mission
* independence of individual reasoning episodes

This distinction is central to RCL.

---

# 7. Continuity ≠ Transcript Preservation

RCL should explicitly avoid defining continuity as:

```text
previous_chat_history + new_chat_history
```

Instead:

```text
Mission State
+
Provenance
+
Artifacts
+
Decisions
+
Constraints
+
Evidence
+
Open Questions
+
Current Position in Lifecycle
+
Context Policy
+
Checkpoint
```

The transcript may be retained as evidence/audit material, but it should not be the canonical state.

This allows:

```text
Claude → Gemini
Gemini → Claude
Claude → Codex
Codex → local model
```

without requiring the new model to possess the old model's conversation.

---

# 8. Model Provider Switching

RCL should explicitly support provider/model substitution.

Example:

```text
Run 001
    ↓
Claude
    ↓
Checkpoint
    ↓
Claude quota exhausted
    ↓
Gemini
    ↓
Resume
```

The new runtime should receive a canonical continuity package.

It should NOT depend upon:

* Claude's chat memory
* provider-specific conversation state
* hidden system prompts
* provider-specific summaries

## Research Questions

Determine:

1. What state is provider-independent?
2. What state is runtime-specific?
3. How are provider-specific context windows handled?
4. How should summaries be generated?
5. Who validates summaries?
6. How can continuity fidelity be tested?
7. How can a new model detect that the previous model's state was wrong?

---

# 9. Continuity Reconstruction Test

RCL requires a stronger portability test than simply restoring a checkpoint.

Proposed test:

```text
MODEL A
   ↓
Reasoning Mission
   ↓
Checkpoint
   ↓
Destroy Session
   ↓
Destroy Runtime
   ↓
Start MODEL B
   ↓
Hydrate from PAEOS
   ↓
Continue Mission
```

The test should verify:

* same active objective
* same constraints
* same authoritative decisions
* same unresolved questions
* same artifact references
* correct provenance
* correct lifecycle position
* no dependence on original transcript

A stronger version should deliberately switch providers.

---

# 10. Epistemic Independence Test

Continuity must not destroy independence.

Construct a test:

```text
Architect A
    ↓
Decision D
    ↓
Checkpoint
```

Then launch:

```text
Fresh Critic B
```

with a context policy that excludes D.

Critic B must independently evaluate the evidence.

Then compare:

```text
B's conclusion
        vs
D
```

The system must preserve the distinction between:

* inherited truth
* inherited constraint
* inherited evidence
* inherited conclusion

This should be tested mechanically.

---

# 11. Provenance and Contamination Propagation

If a persisted decision later becomes invalid, downstream reasoning may have been contaminated.

Example:

```text
D1
 ↓
D2
 ↓
P3
 ↓
H4
```

If D1 becomes:

```text
DISPUTED
```

PAEOS should identify dependent state.

RCL should therefore integrate with provenance rather than merely storing checkpoints.

Potential states:

```text
ACTIVE
DISPUTED
SUPERSEDED
INVALIDATED
REQUIRES_REVIEW
```

The exact state machine must be derived from existing PAEOS semantics before implementation.

---

# 12. Checkpoint Semantics

A checkpoint must capture the semantic position of a mission, not merely:

```text
git commit + transcript
```

It should be possible to answer:

> "What did PAEOS believe, why did it believe it, what was unresolved, what stage was it in, and what evidence supported the current state?"

Potential checkpoint components:

```text
checkpoint_id
goal_id
run_id
lifecycle_position
active_task
canonical_state_revision
context_revision
artifact_refs
decision_refs
open_questions
invocation_lineage
runtime/provider metadata
repository revision
integrity hashes
parent checkpoint
```

The exact schema remains a research question.

---

# 13. Code / Reasoning State Alignment

A major continuity hazard exists when reasoning refers to a codebase state that has changed.

Example:

```text
Reasoning checkpoint
        ↓
Code commit A
        ↓
Implementation changes
        ↓
Code commit B
        ↓
Resume old reasoning
```

RCL must detect this mismatch.

Potential mechanism:

```text
reasoning checkpoint
        │
        └── code revision/hash
```

On resume:

```text
current repository
        ↓
compare against checkpoint
        ↓
MATCH
    → continue

MISMATCH
    → require reconciliation
```

The exact semantics should be researched against PAEOS's existing CAS/Ledger and execution model.

---

# 14. RCL Must Not Duplicate SAKG

SAKG and PAEOS are separate architectural systems.

RCL belongs to PAEOS.

SAKG remains the external knowledge architecture.

PAEOS may reference SAKG knowledge through explicit contracts, but RCL must not silently reproduce SAKG's ontology or turn SAKG into a PAEOS state store.

Conceptually:

```text
PAEOS
 └── RCL
      └── references
           ↓
         SAKG
```

not:

```text
PAEOS
 └── copied SAKG graph
```

---

# 15. Context Compiler as the Likely Policy Enforcement Point

The existing `ContextCompiler` should be investigated as the primary mechanism for turning canonical continuity state into model-specific context.

Conceptually:

```text
Canonical RCL State
        ↓
Context Policy
        ↓
ContextCompiler
        ↓
Provider-specific Context Package
        ↓
Runtime
        ↓
Model
```

This keeps the model unaware of the full underlying epistemic database.

---

# 16. InformationBarrierManager Integration

The existing `InformationBarrierManager` should not be replaced casually.

Research should determine whether it can be generalized to support:

* fresh reasoning
* blind critique
* adversarial review
* provider switching
* context minimization
* continuity reconstruction

The objective is to avoid two competing context-isolation mechanisms.

---

# 17. Reasoning Economy

Continuity introduces a potentially enormous context cost.

Therefore RCL should research an explicit **Reasoning Economy**.

The system should decide:

> What information is worth spending model context/tokens to transmit?

Potential dimensions:

```text
importance
dependency
recency
confidence
epistemic status
task relevance
contradiction risk
reconstruction cost
token cost
```

A continuity package should therefore not necessarily contain every historical artifact.

The system may produce:

```text
Minimum Sufficient Context
```

while preserving access to deeper state when required.

This should integrate with PAEOS's existing governance rather than becoming an unconstrained summarization system.

---

# 18. Summarization Must Be Treated as a Transformation

A model-generated summary is not automatically authoritative.

If:

```text
State → LLM summary → future agent
```

the summary may introduce information loss or hallucination.

Therefore research should investigate:

* deterministic state extraction
* structured state serialization
* model-generated summaries as secondary artifacts
* summary verification
* provenance of summarized claims
* reconstruction tests

Preferred hierarchy:

```text
Canonical structured state
        ↓
deterministic context compiler
        ↓
optional model summary
```

rather than:

```text
conversation
   ↓
LLM summary
   ↓
new conversation
```

---

# 19. Antigravity Subagent Use

Antigravity subagents can be useful for:

* parallel research
* independent critiques
* implementation workers
* testing
* repository exploration

But PAEOS must remain the authority over:

* what task is authorized
* what context is visible
* what files may be changed
* whether work is accepted
* whether evidence is valid
* whether a transition occurs
* whether a result is sealed

The correct relationship is:

```text
             PAEOS
               │
       ┌───────┴────────┐
       ↓                ↓
  Runtime A          Runtime B
       │                │
   sandbox          sandbox
       │                │
    model             model
       │                │
       └───────┬────────┘
               ↓
           PAEOS
        verification
```

Antigravity should not silently become a second constitution.

---

# 20. Autonomous Continuation

The ultimate RCL goal is autonomous continuation.

A mission should be able to continue after:

* model quota exhaustion
* provider failure
* process termination
* terminal closure
* machine restart
* runtime replacement
* context-window exhaustion
* human absence

Conceptually:

```text
MISSION
  ↓
PAEOS
  ↓
MODEL A
  ↓
CHECKPOINT
  ↓
MODEL A unavailable
  ↓
RUNTIME SWITCH
  ↓
MODEL B
  ↓
RECONSTRUCT
  ↓
VERIFY
  ↓
CONTINUE
```

The mission should not need the human to manually reconstruct its history.

---

# 21. Human Intervention Boundary

RCL must distinguish:

### Automatically recoverable

* provider switch
* session loss
* process restart
* model replacement
* context-window exhaustion

from:

### Governance events requiring review

* authoritative decision invalidated
* critical invariant violated
* repository state incompatible with checkpoint
* evidence conflict
* provenance corruption
* security boundary violation

Continuity must never be used to bypass governance.

---

# 22. Required Research Experiments

Before implementation, perform the following experiments through the **canonical PAEOS workflow**.

### R1 — Lifecycle Reconstruction

Derive the true PAEOS lifecycle from code/documentation.

### R2 — Runtime Boundary

Determine exactly where PAEOS hands execution to a model/runtime.

### R3 — Context Isolation

Prove that a fresh agent can receive selected canonical state without receiving excluded conclusions.

### R4 — Provider Switch

Run:

```text
Provider A → checkpoint → Provider B
```

and verify reconstruction.

### R5 — Sandbox Continuity

Run an agent inside an isolated external sandbox, terminate it, then reconstruct from PAEOS state.

### R6 — Adversarial Independence

Give a critic evidence but hide the original conclusion.

### R7 — State Invalidation

Invalidate an upstream decision and verify downstream dependency detection.

### R8 — Code Revision Mismatch

Change the repository after checkpoint creation and verify that PAEOS detects the mismatch.

### R9 — Context Compression

Compare full canonical state against minimum-sufficient context.

### R10 — Crash Recovery

Terminate the runtime at different lifecycle points and resume from durable PAEOS state.

---

# 23. Implementation Constraints

The eventual implementation MUST:

1. Use the existing PAEOS orchestration lifecycle.
2. Preserve existing governance.
3. Preserve existing invariants.
4. Preserve PAEOS/SAKG separation.
5. Treat model sessions as disposable.
6. Treat PAEOS state as authoritative.
7. Support multiple runtime providers.
8. Preserve epistemic distinctions.
9. Preserve provenance.
10. Support controlled context inheritance.
11. Support fresh/adversarial reasoning.
12. Support checkpoint/resumption.
13. Detect incompatible repository state.
14. Never depend on provider-specific chat memory.
15. Avoid introducing a parallel unofficial orchestrator.

---

# 24. Explicit Non-Goals

This research item does NOT authorize:

* replacing SoftLoop merely because it is imperfect
* building a second orchestration framework
* replacing the PAEOS constitution
* moving authoritative state into Antigravity
* treating chat history as canonical
* copying SAKG into PAEOS
* blindly summarizing all historical context
* implementing a generic DAG merely because branching is useful
* replacing InformationBarrierManager without evidence
* introducing speculative architecture before capability experiments

---

# 25. Success Condition

The RCL research is successful when we can demonstrate:

```text
                PAEOS
                  │
             Canonical State
                  │
          Context Compiler
                  │
        ┌─────────┴─────────┐
        ↓                   ↓
    Model A              Model B
   / Sandbox            / Sandbox
        │                   │
        └─────────┬─────────┘
                  ↓
               PAEOS
             Verification
                  │
             Checkpoint
                  │
             Continuation
```

and demonstrate that:

> The mission continues coherently even when the original model, session, runtime, sandbox, or provider disappears.

At the same time:

> A fresh reasoning agent can remain genuinely independent when the context policy requires independence.

That combination — **continuity without contamination** — is the central architectural objective of RCL.

---

# 26. Current Status

**RCL v0.1:** Conceptual architecture established.

**RCL v0.2:** Additional research requirements captured.

**Implementation:** NOT YET AUTHORIZED.

**Next action:** Execute the research experiments through the canonical PAEOS lifecycle and derive the actual implementation architecture from the resulting evidence.

---

# 27. Guiding Principle

> **PAEOS remembers the mission. Models remember only what they need to perform the next act of reasoning.**

And:

> **Continuity preserves the state of the reasoning process; it does not require continuity of the reasoning session.**

