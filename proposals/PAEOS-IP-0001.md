# PAEOS-IP-0001 — Capability-Based Skill Loading

Status: **AWAITING FOUNDER RATIFICATION** · Filed: 2026-07-21 · Channel: CER-2
Source finding: `reviews/7-skills-as-capabilities.md` (CAP-1). This proposal is the formal
ratification-channel form of an improvement already discovered but deliberately **excluded**
from PAEOS-4 v1.1 (§16) because it is unratified. It recommends; it changes nothing until the
founder ratifies.

## 1. Observation

Skill loading (PAEOS-4 v1.1 §6.2, §2.7) is **reactive**: a skill fires when its `TriggerExpr`
matches, and a trigger can see only `goal.kind`, `classification.v/r`, `workload`,
`role.stance/domain`, and `media_in_links` (media types of *already-linked* artifacts, SC-06).
There is no language/domain/capability axis.

## 2. Current behaviour

On a **greenfield** goal — e.g. "implement the validator in Python," at declaration, before
any Python artifact exists — `python_skill`'s trigger cannot fire (`media_in_links` is empty
of Python, classification carries only v/r). The Builder therefore spawns **without** the
capability and produces worse output. The reactive model fails precisely at creation, which is
most of implementation.

## 3. Proposed improvement

- **Schema (§2.5):** add optional `Goal.spec.capabilities: [CapabilityRef]` (the field is
  already reserved-but-absent in v1.1 §2.5). A `CapabilityRef` is a stable capability name
  (e.g. `"lang:python"`, `"db:postgres"`); its namespace grammar is pinned in a new SC entry.
- **Schema (§2.7):** add `Policy(kind=skill).provides: [CapabilityRef]`.
- **Resolution (§6.2):** the Compiler loads skills matched by trigger **OR** providing a
  declared capability, then the `requires` closure:
  `Skills := {trigger=true} ∪ {provides ∩ goal.capabilities ≠ ∅} ∪ closure(requires)`.
  Multiple providers resolve by existing `priority`/id order (§6.4).

The Decomposer, which knows the goal is a Python goal, declares `capabilities:["lang:python"]`
— a *need*, naming no skill and requiring no Python knowledge. The Compiler resolves need→
provider deterministically.

## 4. Justification

Preserves K5/A-05 (a capability name resolving to a skill is a deterministic, versioned lookup
— identical in kind to a package name resolving to a library; nothing hand-assembled). Fixes a
genuine defect in §6.2 (greenfield trigger failure) rather than a preference. Free bonuses:
multi-provider capabilities (fast vs thorough `lang:python`) and a clean selection point for
skill-version tournaments (PAEOS-2 §5).

## 5. Risks

- Capability namespace fragmentation if the `CapabilityRef` grammar is not pinned (mitigation:
  pin it as an SC entry before ratification).
- A Decomposer could over-declare capabilities, bloating contexts (mitigation: §6.4 byte
  budget + truncation already bound this).

## 6. Backwards compatibility

Additive and optional. Goals without `capabilities` behave exactly as v1.1 (trigger-only).
Skills without `provides` are unaffected. No existing store object becomes invalid; conformance
suite unchanged except a new positive test for capability resolution.

## 7. Constitutional impact

Kernel-surface (§2.5, §2.7, §6.2) ⟹ requires **§14.5 ceremony + founder ratification**. If
ratified, it merges into a future PAEOS-4 v1.2 and the reserved `capabilities` field in v1.1
§2.5 becomes active.

## 8. Recommendation

**Ratify**, conditional on pinning the `CapabilityRef` namespace grammar first. The defect it
fixes (greenfield capability loading) is blocking before the first workload with a technology
stack (Sentium), though not before kernel genesis — so it may be ratified any time before
workload #1.
