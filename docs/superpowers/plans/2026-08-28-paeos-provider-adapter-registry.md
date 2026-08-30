# PAEOS Provider Adapter Registry Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development`
> (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make model providers registerable through validated descriptors and transport adapters
without editing core routing, coordinator, lifecycle, or audit-policy code, while preserving all
existing provider behavior during migration.

**Architecture:** Keep `ModelRouter`, the catalog, privacy eligibility, provider state, AIMD, and
A-08 as the existing policy seams. Replace the closed provider enum as the canonical identity with
a validated string key, retain `ProviderId` only as a compatibility input, and move provider facts
and wire behavior into trusted startup descriptors and transport adapters. No runtime filesystem
plugin discovery or arbitrary import strings are allowed.

**Tech Stack:** Python 3.12, frozen dataclasses, protocols, SQLite, LiteLLM, HTTPX, pytest, Ruff,
Pyright, AST architecture checks.

**Spec:** `docs/superpowers/specs/2026-08-26-paeos-ai-supervised-autonomy-design.md` section 4.1

## Global Constraints

- Depends on Gate B transaction fencing and must finish before headless supervisor adapters bind to
  model-provider selection.
- Preserve existing Google, Cline, NVIDIA, Kilo, and OpenRouter catalog entries and behavior.
- `ProviderId` remains import-compatible until all repository consumers have migrated; new core
  APIs store and compare normalized provider keys rather than enum members.
- Descriptors are trusted local configuration assembled in Python. Do not execute configuration,
  load arbitrary module paths, or discover plugins from writable directories.
- Credentials remain references to environment-variable names. Secret values never enter a
  descriptor, trace, fixture, receipt, or commit.
- Provider-specific endpoints, headers, message normalization, error rules, rate defaults, and
  transport behavior live in provider descriptors or adapter modules, not `ModelRouter`, lifecycle
  code, supervisor coordinators, or audit policy.
- A-08 remains family-based. Adding a provider cannot alter Builder/Auditor eligibility without a
  separately validated physical model-family observation.
- Every migration step runs existing model-router tests to prove compatibility before deleting a
  legacy branch.

---

## Task 1: Introduce Validated Provider Keys and an Immutable Descriptor Registry

**Files:**

- Create: `paeos/model_router/providers.py`
- Modify: `paeos/model_router/types.py`
- Modify: `paeos/model_router/__init__.py`
- Test: `tests/model_router/test_provider_registry.py`

**Interfaces:**

```python
ProviderKey = str

def normalize_provider_key(value: str | ProviderId) -> ProviderKey: ...

@dataclass(frozen=True, slots=True)
class ProviderDescriptor:
    key: ProviderKey
    credential_env: str
    transport_adapter_id: str
    trains_on_inputs: bool
    retains_prompts: bool
    allows_internal: bool
    allows_confidential: bool
    max_rpm: int | None
    max_tpm: int | None
    max_rpd: int | None
    preference_rank: Mapping[LogicalModel, int]
    task_fit: Mapping[TaskClass, float]
    quality_bias: float
    latency_bias: float

class ProviderRegistry:
    def register(self, descriptor: ProviderDescriptor) -> None: ...
    def resolve(self, key: str | ProviderId) -> ProviderDescriptor: ...
    def snapshot(self) -> tuple[ProviderDescriptor, ...]: ...
```

- [x] **Step 1.1: Write RED validation and compatibility tests**

Test lowercase ASCII keys, rejection of empty/path/control-character keys, duplicate registration,
unknown lookup, deterministic snapshots, secret-free descriptor representation, and lookup through
both `ProviderId.GOOGLE` and `"google"`. Register `future-provider` in the test and verify no enum
member is required.

- [ ] **Step 1.2: Run RED once**

```bash
/Users/bob/GitHub/paeos/.venv/bin/python -m pytest -q \
  tests/model_router/test_provider_registry.py
```

Expected: collection fails because `paeos.model_router.providers` does not exist.

- [x] **Step 1.3: Implement provider-key normalization and immutable registry behavior**

Normalize legacy `StrEnum` values through `.value`, validate against
`^[a-z][a-z0-9-]{0,62}$`, reject duplicates, and return snapshots sorted by key. Keep the existing
`ProviderId` declaration and exports as a deprecated compatibility surface; do not add future
providers to that enum.

- [ ] **Step 1.4: Run GREEN and static checks**

```bash
/Users/bob/GitHub/paeos/.venv/bin/python -m pytest -q \
  tests/model_router/test_provider_registry.py \
  tests/model_router/test_catalog_and_privacy.py
/Users/bob/GitHub/paeos/.venv/bin/python -m ruff check \
  paeos/model_router/providers.py paeos/model_router/types.py \
  tests/model_router/test_provider_registry.py
/Users/bob/GitHub/paeos/.venv/bin/python -m pyright \
  paeos/model_router/providers.py paeos/model_router/types.py
```

The registry and compatibility tests pass, and the new registry files pass Ruff and Pyright. The
combined Ruff command still reports **38 pre-existing findings** in `types.py` (legacy enum and
typing style); those unrelated findings are preserved rather than mass-repaired. The separate RED
transcript is not retained as a standalone artifact in this checkpoint.

- [x] **Step 1.5: Commit**

```bash
git add paeos/model_router/providers.py paeos/model_router/types.py \
  paeos/model_router/__init__.py tests/model_router/test_provider_registry.py
git commit -m "feat(routing): add validated provider descriptor registry"
```

---

## Task 2: Move Provider Wire Behavior Behind Transport Adapters

**Files:**

- Create: `paeos/model_router/provider_transports.py`
- Modify: `paeos/model_router/transport.py`
- Modify: `paeos/model_router/errors.py`
- Test: `tests/model_router/test_provider_transports.py`
- Test: `tests/model_router/test_error_normalization.py`

**Interfaces:**

```python
class ProviderTransport(Protocol):
    def dispatch(
        self,
        model_entry: ModelCatalogEntry,
        request: TaskRequest,
        *,
        api_key: str,
        timeout: float,
    ) -> RouterResponse: ...

@dataclass(frozen=True, slots=True)
class OpenAICompatibleConfig:
    api_base: str
    extra_headers: Mapping[str, str]
    single_tool_call_only: bool
    confidential_zdr: bool

class ProviderTransportRegistry:
    def register(self, adapter_id: str, transport: ProviderTransport) -> None: ...
    def resolve(self, adapter_id: str) -> ProviderTransport: ...
```

- [ ] **Step 2.1: Write RED transport parity and synthetic-provider tests**

Capture existing Google, NVIDIA, Kilo, OpenRouter, and Cline request/response fixtures. Assert exact
endpoint, message normalization, ZDR headers, Cline envelope parsing, usage/model observation, and
normalized errors. Register an in-memory synthetic transport and prove `LiteLLMTransport.dispatch`
uses it without a provider-name conditional.

- [ ] **Step 2.2: Run RED once**

```bash
/Users/bob/GitHub/paeos/.venv/bin/python -m pytest -q \
  tests/model_router/test_provider_transports.py \
  tests/model_router/test_error_normalization.py
```

Expected: collection fails because transport adapters do not exist.

- [ ] **Step 2.3: Extract generic and Cline transports, then inject the registry**

Implement one configurable OpenAI-compatible transport and one Cline-envelope transport. Convert
`LiteLLMTransport` into a dispatcher that resolves the provider descriptor, obtains the credential,
and delegates exactly once. Move provider-specific error predicates into the applicable adapter or
descriptor. Preserve raw response/error evidence and do not add retries.

- [ ] **Step 2.4: Run GREEN and assert removal of provider branches**

```bash
/Users/bob/GitHub/paeos/.venv/bin/python -m pytest -q \
  tests/model_router/test_provider_transports.py \
  tests/model_router/test_error_normalization.py \
  tests/model_router/test_routing_policy.py
rg -n "ProviderId\.(GOOGLE|CLINE|NVIDIA|KILO|OPENROUTER)" \
  paeos/model_router/transport.py
```

Expected: tests pass and the final `rg` produces no matches. Record its exit code `1` as the
expected no-match result, not a failed verification.

- [ ] **Step 2.5: Commit**

```bash
git add paeos/model_router/provider_transports.py paeos/model_router/transport.py \
  paeos/model_router/errors.py tests/model_router/test_provider_transports.py \
  tests/model_router/test_error_normalization.py
git commit -m "refactor(routing): isolate provider wire transports"
```

---

## Task 3: Migrate Catalog, Credentials, Limits, and Policy to Descriptor Facts

**Files:**

- Modify: `paeos/model_router/catalog.py`
- Modify: `paeos/model_router/credentials.py`
- Modify: `paeos/model_router/aimd.py`
- Modify: `paeos/model_router/observability.py`
- Modify: `paeos/model_router/policy.py`
- Modify: `paeos/model_router/privacy.py`
- Modify: `paeos/model_router/router.py`
- Test: `tests/model_router/test_provider_descriptor_policy.py`
- Test: `tests/model_router/test_state_and_aimd.py`
- Test: `tests/model_router/test_routing_policy.py`

**Interfaces:**

```python
def build_builtin_provider_registry() -> ProviderRegistry: ...
```

- [ ] **Step 3.1: Write RED behavior-parity and extension tests**

Freeze existing candidate ordering for representative `paeos-auto`, `paeos-code`, and
`paeos-cheap` requests, including privacy exclusions, quota state, and AIMD. Register a synthetic
provider with explicit routing facts and verify it participates without changes to `policy.py`,
`credentials.py`, `aimd.py`, or `observability.py`.

- [ ] **Step 3.2: Run RED once**

```bash
/Users/bob/GitHub/paeos/.venv/bin/python -m pytest -q \
  tests/model_router/test_provider_descriptor_policy.py
```

Expected: tests fail because built-in policy still uses provider-name tables and branches.

- [ ] **Step 3.3: Move provider facts into built-in descriptors**

Populate trusted built-in descriptors with credential references, data policy, rate defaults, and
routing facts. Make catalog filtering, credential lookup, AIMD initialization, observability, and
policy scoring consume normalized keys and descriptor facts. Preserve model-family and task-type
logic as policy; only provider-name-specific facts move.

- [ ] **Step 3.4: Run GREEN and static checks**

```bash
/Users/bob/GitHub/paeos/.venv/bin/python -m pytest -q \
  tests/model_router/test_provider_descriptor_policy.py \
  tests/model_router/test_catalog_and_privacy.py \
  tests/model_router/test_state_and_aimd.py \
  tests/model_router/test_routing_policy.py
/Users/bob/GitHub/paeos/.venv/bin/python -m ruff check paeos/model_router tests/model_router
/Users/bob/GitHub/paeos/.venv/bin/python -m pyright paeos/model_router
```

- [ ] **Step 3.5: Commit**

```bash
git add paeos/model_router/catalog.py paeos/model_router/credentials.py \
  paeos/model_router/aimd.py paeos/model_router/observability.py \
  paeos/model_router/policy.py paeos/model_router/privacy.py \
  paeos/model_router/router.py tests/model_router/test_provider_descriptor_policy.py \
  tests/model_router/test_state_and_aimd.py tests/model_router/test_routing_policy.py
git commit -m "refactor(routing): derive provider policy from descriptors"
```

---

## Task 4: Preserve Durable State Compatibility Across Provider-Key Migration

**Files:**

- Modify: `paeos/model_router/state.py`
- Modify: `paeos/model_router/observability.py`
- Modify: `paeos/model_router/probe_harness.py`
- Test: `tests/model_router/test_provider_state_migration.py`
- Test: `tests/model_router/test_state_and_aimd.py`

- [ ] **Step 4.1: Write RED legacy-state migration tests**

Create a state database containing every existing provider key using the current schema. Open it
with the migrated code and assert identical health, cooldown, concurrency, quota-window, and usage
records. Verify unknown but valid future keys persist and reload. Invalid keys must quarantine the
record or fail startup before routing; they must never be silently normalized to another provider.

- [ ] **Step 4.2: Run RED once**

```bash
/Users/bob/GitHub/paeos/.venv/bin/python -m pytest -q \
  tests/model_router/test_provider_state_migration.py
```

Expected: the future-provider persistence case fails against enum-bound state APIs.

- [ ] **Step 4.3: Migrate state APIs to normalized string keys**

Keep the SQLite representation unchanged when it already stores text. Normalize and validate at
API boundaries, preserve old rows byte-for-byte, and update the probe harness to use registry
snapshots rather than a compiled provider list.

- [ ] **Step 4.4: Run GREEN**

```bash
/Users/bob/GitHub/paeos/.venv/bin/python -m pytest -q \
  tests/model_router/test_provider_state_migration.py \
  tests/model_router/test_state_and_aimd.py
```

- [ ] **Step 4.5: Commit**

```bash
git add paeos/model_router/state.py paeos/model_router/observability.py \
  paeos/model_router/probe_harness.py tests/model_router/test_provider_state_migration.py \
  tests/model_router/test_state_and_aimd.py
git commit -m "refactor(routing): persist open provider keys compatibly"
```

---

## Task 5: Deduplicate Audit Mapping and Prove Core Independence

**Files:**

- Modify: `paeos/model_router/a08_enforcer.py`
- Modify: `paeos/model_router/audit.py`
- Create: `tests/model_router/test_provider_architecture.py`
- Modify: `tests/model_router/test_a08_integration.py`
- Modify: `tests/model_router/test_generic_decorrelation.py`

- [ ] **Step 5.1: Write RED architecture and A-08 tests**

Add an AST test prohibiting built-in provider names and `ProviderId` branches in router, policy,
transport, coordinator, lifecycle, and audit-policy modules. Register a synthetic provider whose
observed model family is known and prove A-08 uses family inequality rather than provider identity.
Register the same provider with unknown or conflicting family evidence and prove it is ineligible.

- [ ] **Step 5.2: Run RED once**

```bash
/Users/bob/GitHub/paeos/.venv/bin/python -m pytest -q \
  tests/model_router/test_provider_architecture.py \
  tests/model_router/test_a08_integration.py
```

Expected: architecture checks fail on remaining hard-coded provider branches or duplicated auditor
mapping.

- [ ] **Step 5.3: Centralize family decorrelation policy and remove remaining core branches**

Keep one canonical family-decorrelation mapping in A-08 and make audit consume it. Remove
provider-name decisions from core modules while preserving explicit built-in descriptor assembly.
Do not weaken unknown-family, opaque-alias, TTL, or conflicting-receipt rejection.

- [ ] **Step 5.4: Run the full model-router suite and architecture scan**

```bash
/Users/bob/GitHub/paeos/.venv/bin/python -m pytest -q tests/model_router
/Users/bob/GitHub/paeos/.venv/bin/python -m ruff check paeos/model_router tests/model_router
/Users/bob/GitHub/paeos/.venv/bin/python -m pyright paeos/model_router
git diff --check
```

Expected: all checks pass. The synthetic provider participates in routing but cannot enter a
protected role without verified physical-family evidence.

- [ ] **Step 5.5: Commit**

```bash
git add paeos/model_router/a08_enforcer.py paeos/model_router/audit.py \
  tests/model_router/test_provider_architecture.py \
  tests/model_router/test_a08_integration.py \
  tests/model_router/test_generic_decorrelation.py
git commit -m "test(routing): prove provider plug-in independence"
```

---

## Task 6: L13, L14, and L17 Migration Gate

**Files:**

- Create: `reviews/tasks/PAEOS_PROVIDER_ADAPTER_REGISTRY_review.md`
- Modify: `PAEOS_HALLUCINATION_CHECKER_NOTEBOOK.md`
- Modify: `MessyChangesNeedsReview.md` only for unresolved migration debt

- [ ] **Step 6.1: Run fresh applicable verification**

```bash
/Users/bob/GitHub/paeos/.venv/bin/python -m pytest -q tests/model_router tests/runtime
/Users/bob/GitHub/paeos/.venv/bin/python -m pytest -q
/Users/bob/GitHub/paeos/.venv/bin/python -m ruff check .
/Users/bob/GitHub/paeos/.venv/bin/python -m pyright
git diff --check
```

- [ ] **Step 6.2: Run discriminative baseline/candidate proof**

Run the synthetic-provider contract against the parent commit and candidate. The parent must fail
because it requires core enum/table edits; the candidate must pass through descriptor registration.
Preserve both raw outputs and hashes.

- [ ] **Step 6.3: Obtain physically decorrelated L14 audit**

The auditor reviews the registry boundary, compatibility migration, secret exclusion, A-08
non-regression, and AST checks from a sealed evidence bundle. The auditor family must differ from
the builder family and must not have authored the migration.

- [ ] **Step 6.4: Record L17 without activating a live new provider**

Record exact Court counts, remands, remediations, compatibility debt, and the approved built-in
descriptor snapshot hash. This gate proves extensibility; adding or enabling a live provider still
requires its own policy, credential, physical-identity, canary, and admission evidence.

- [ ] **Step 6.5: Commit review records**

```bash
git add PAEOS_HALLUCINATION_CHECKER_NOTEBOOK.md MessyChangesNeedsReview.md \
  reviews/tasks/PAEOS_PROVIDER_ADAPTER_REGISTRY_review.md
git commit -m "docs(review): record provider registry migration disposition"
```
