# PAEOS Model Router & Free Inference Mesh Specification
## Economy of Reasoning & Autonomous Model Routing Architecture

---

## 1. System Vision & Core Invariants

The PAEOS Model Router aggregates heterogeneous free and commercial inference providers into a unified, virtualized **Inference Mesh**. 

### 1.1 Invariant I: State Preservation (Local Canonical State)
> **Models are stateless, replaceable reasoning engines.**
> Neither Antigravity, Gemini, DeepSeek, nor any model provider owns canonical task state. 
> Canonical state (Task Graph, Conversation History, Tool Invocations, File Diffs, Evidence Tokens, Debt Ledger) is permanently owned and persisted locally by the **PAEOS Runtime Engine**.

```
                LOCAL PAEOS STATE (Canonical Ground Truth)
                                   │
      ┌────────────────────────────┼────────────────────────────┐
      ▼                            ▼                            ▼
  Gemini 3.7                   GLM-5.2                  DeepSeek / Laguna
 (Stateless)                  (Stateless)                  (Stateless)
```

### 1.2 Invariant II: Single Policy Authority (Separation of Concerns)
> **PAEOS is the sole decision-maker for routing, retries, cooldowns, and fallbacks.**
> LiteLLM acts strictly as a **Transport Layer** (API normalization, streaming, serialization, wire adaptation).
> LiteLLM's internal autonomous retry and cooldown features are disabled to prevent hidden sub-routing and preserve empirical telemetry integrity.

---

## 2. The 3-Tier Layered Architecture

```
┌────────────────────────────────────────────────────────────────────────┐
│ Layer 3: ANTIGRAVITY SUPERVISOR                                        │
│ • Decomposes job into atomic sub-tasks                                 │
│ • Labels task_class, criticality, data_class, context_size             │
│ • Requests independent heterogeneous review & audit                   │
└──────────────────────────────────┬─────────────────────────────────────┘
                                   │ { task_class, criticality, data_class, context_size, audit_required }
                                   ▼
┌────────────────────────────────────────────────────────────────────────┐
│ Layer 2: PAEOS INTELLIGENT ROUTER (paeos/model_router/)                │
│ • policy.py        → Multi-stage constraint filter & scoring engine    │
│ • catalog.py       → Validated model registry & dynamic capabilities   │
│ • state.sqlite3    → Concurrent SQLite WAL ledger (quotas, cooldowns)  │
│ • health.py        → Error normalization & health state machine        │
│ • aimd.py          → Deterministic AIMD admission controller           │
└──────────────────────────────────┬─────────────────────────────────────┘
                                   │ Logical Model Request (e.g. "paeos-code", "paeos-audit")
                                   ▼
┌────────────────────────────────────────────────────────────────────────┐
│ Layer 1: LiteLLM TRANSPORT GATEWAY (127.0.0.1:4000)                   │
│ • STRICTLY TRANSPORT ONLY (No autonomous retries/cooldowns)           │
│ • Normalizes provider APIs to OpenAI-compatible wire format            │
│ • Manages HTTP connection pooling, token serialization & streaming    │
│ • Bound exclusively to loopback (127.0.0.1) with local bearer auth    │
└──────────────────────────────────┬─────────────────────────────────────┘
                                   │
      ┌──────────────┬─────────────┼──────────────┬──────────────┐
      ▼              ▼             ▼              ▼              ▼
 1. Google      2. Cline      3. NVIDIA      4. Kilo        5. OpenRouter
 AI Studio         API           NIM          Gateway           Router
 (Gemini 3.7)  (Reg-Free)     (GLM-5.2)    (Auto Free/Hy3) (openrouter/free)
```

---

## 3. The Five Inference Providers & Endpoints

| Provider | Base Endpoint | Model Identifiers | Key Config / Notes |
|---|---|---|---|
| **1. Google AI Studio** | `https://generativelanguage.googleapis.com/v1beta/openai/` | `gemini-3.7-flash` | `GEMINI_API_KEY`<br>OpenAI-compatible wire endpoint. High reasoning & architectural analysis. |
| **2. Cline API** | `https://api.cline.bot/api/v1` | Explicit validated registry (e.g. `minimax/minimax-m2.5`, probed DeepSeek) | `CLINE_API_KEY`<br>OpenAI-compatible API. Requires explicit `provider/model-name` slugs from validated catalog. |
| **3. NVIDIA NIM** | `https://integrate.api.nvidia.com/v1` | `z-ai/glm-5.2` | `NVIDIA_API_KEY`<br>753B MoE model. 1M token context. High-capacity repo analysis. |
| **4. Kilo Gateway** | `https://api.kilo.ai/api/gateway` | `kilo-auto/free`, `tencent/hy3:free`, `poolside/laguna-s-2.1:free`, `nvidia/nemotron-3-ultra-550b-a55b:free` | `KILO_API_KEY`<br>Built-in router over verified free tiers. Governed by privacy policy gate. |
| **5. OpenRouter** | `https://openrouter.ai/api/v1` | `openrouter/free` | `OPENROUTER_API_KEY`<br>Zero-cost free pool router (~50 req/day limit). Overflow/emergency tier only. Invariant: `FREE_ONLY=true`. |

### OpenRouter Cost Invariant
```python
# Hard safety invariant to prevent unexpected commercial billing
if provider == "openrouter":
    assert model == "openrouter/free" or model.endswith(":free"), f"Non-free OpenRouter model rejected: {model}"
```

---

## 4. Multi-Stage Task Selection Pipeline

Instead of calculating a score first and hoping constraints match, selection executes as an **ordered constraint pipeline**:

```
                       INBOUND TASK REQUEST
                                 │
                                 ▼
                     1. Privacy Allowed? (Data Class vs Provider Policy)
                                 │
                                 ▼
                     2. Required Capability? (Tools, JSON schema, Reasoning)
                                 │
                                 ▼
                     3. Context Fits? (Input tokens < Model Context Limit)
                                 │
                                 ▼
                     4. Provider Healthy? (Not in COOLDOWN / EXHAUSTED / QUARANTINE)
                                 │
                                 ▼
                     5. Quota Available? (RPM, TPM, RPD & Reserve Partitions)
                                 │
                                 ▼
                     6. Economy of Reasoning Score (Optimize Value / Cost)
                                 │
                                 ▼
                     SELECTED MODEL ENDPOINT
```

---

## 5. First-Class Data Privacy Gating

Privacy is an **eligibility gate**, not a mathematical weight. Tasks are labeled with one of four data classifications:

| Data Class | Description | Permitted Provider Data Policies |
|---|---|---|
| `PUBLIC` | Open-source code, public benchmarks, documentation. | All providers (including public logging/training tiers). |
| `INTERNAL` | Standard project code, non-sensitive debt logs. | Providers guaranteeing non-retention or private routing (Gemini standard, NVIDIA direct, Cline). |
| `CONFIDENTIAL` | Proprietary designs, security patches, credentials. | Strictly no-training providers (`kilo-auto/free` disallowed; OpenRouter logging disallowed). |
| `SECRET` | Local signing keys, raw auth credentials. | **NEVER dispatched to any remote LLM** (handled by local AST / deterministic scripts). |

```python
def is_privacy_eligible(task_data_class: str, provider_policy: ProviderDataPolicy) -> bool:
    if task_data_class == "CONFIDENTIAL" and provider_policy.trains_on_inputs:
        return False
    if task_data_class == "SECRET":
        return False
    return True
```

---

## 6. Logical Model Abstractions (Exposed to Antigravity)

Antigravity interacts exclusively with 5 logical endpoints:

1. **`paeos-auto`**: Dynamic pipeline selection based on task constraints and the Economy of Reasoning score.
2. **`paeos-strong`**: High-reasoning tier for architecture, constitutional invariant checks, and root-cause analysis:
   $$\text{Gemini 3.7 Flash} \longrightarrow \text{GLM-5.2} \longrightarrow \text{Cline Validated Free} \longrightarrow \text{Hy3} \longrightarrow \text{OpenRouter Free}$$
3. **`paeos-code`**: High-throughput implementation tier for code refactoring, test fixes, and ceremony scripts:
   $$\text{Cline Validated Free} \longrightarrow \text{GLM-5.2} \longrightarrow \text{Hy3} \longrightarrow \text{Laguna S2.1} \longrightarrow \text{Gemini 3.7}$$
4. **`paeos-cheap`**: Quota-preservation tier for routine tasks, variable renames, and minor edits:
   $$\text{Kilo Free} \longrightarrow \text{OpenRouter Free} \longrightarrow \text{Weaker Cline Free}$$
5. **`paeos-audit`**: Adversarial Review tier. Family diversity is preferred for L09 and L10;
   same-family review is eligible only under the ratified C/D/F safeguards and K3 augmentation.
   Strict family inequality remains mandatory for L14 and every other constrained stage. The
   following provider/model combinations are illustrative routing guidance only; they establish
   no capability, qualification, health, or task eligibility:
   $$\text{Builder} = \text{DeepSeek/Minimax} \implies \text{Auditor} = \text{Gemini 3.7}$$
   $$\text{Builder} = \text{Gemini 3.7} \implies \text{Auditor} = \text{GLM-5.2}$$
   $$\text{Builder} = \text{GLM-5.2} \implies \text{Auditor} = \text{Gemini 3.7}$$

---

## 7. Central Admission Controller & Deterministic AIMD Rate Limiting

### 7.1 Operational Philosophy
> **"We care about not continually hitting rate limits, but we should not obsess over never seeing a 429."**
> Stay comfortably below known limits, and treat occasional 429s as empirical telemetry that informs available capacity.
> **Target:** `<1%` throttled request rate during steady state with instant failover.

### 7.2 Deterministic AIMD Rules
For elastic/unadvertised limits (NVIDIA NIM, Kilo, Cline):

- **Initial Concurrency:** `initial_concurrency = 2`
- **Floor / Ceiling:** `min_concurrency = 1`, `max_concurrency = provider_configured_max`
- **Additive Increase (+1):** Increment concurrency by `+1` after **60 consecutive seconds** meeting all criteria:
  1. Zero `429` errors observed.
  2. Error rate $< 1\%$.
  3. p95 latency $\le 150\%$ of baseline latency.
- **Multiplicative Decrease (x0.5):** On any `429 Too Many Requests`:
  $$\text{concurrency} = \max\left(1, \lfloor \text{concurrency} \times 0.5 \rfloor\right)$$
- **Cooldown & Re-entry:**
  - If `Retry-After` header is supplied: enforce specified duration.
  - If missing: set `cooldown = 30s`.
  - On re-entry: resume at `concurrency = 1`, then resume AIMD additive probing.

### 7.3 Starting Safety Matrix

| Provider | Initial Concurrency | Ceiling Strategy |
|---|:---:|---|
| **Google Gemini** | `2` | 80% ceiling of AI Studio RPM/TPM/RPD limits (20% headroom). |
| **NVIDIA NIM** | `2` | Adaptive AIMD (discover sustainable unadvertised throughput). |
| **Cline API** | `2` | Adaptive AIMD + consume dynamic catalog quota metadata. |
| **Kilo Gateway** | `2` | Adaptive AIMD + privacy data policy filter. |
| **OpenRouter** | `1–2` | Preserve scarce 50 req/day free allowance; overflow/emergency tier. |

### 7.4 Single-Retry with Jitter Policy
Repeatedly hammering a throttled provider in a tight loop is prohibited:
```
429 Received ──► Check Retry-After ──► Wait (Header or 1s+Jitter) ──► Retry ONCE ──► If 429: COOLDOWN & Reroute
```

### 7.5 Quota Partitioning for High-Reasoning Models
Gemini 3.7 enforces **hierarchical quota reservations**:
* **70% General Routing:** Standard tasks, implementation, test suites.
* **20% Important Work Reserve:** Architecture, invariant verification, refactoring.
* **10% Emergency Audit Reserve:** Court trials, remand recovery, adversarial audits.

---

## 8. Normalized Error Handling Engine

Providers frequently return heterogeneous HTTP status codes (e.g. Kilo returning 400 for context length overflow, or 503 for upstream credit exhaustion). The router parses both HTTP status and response JSON bodies into **normalized canonical error types**:

| Normalized Error | Detection Trigger | Router Policy Action |
|---|---|---|
| `CONTEXT_EXCEEDED` | `400` with "context length" or "maximum context" message. | **Do not retry on same model.** Escalate immediately to large-context tier (GLM-5.2 or Gemini). |
| `RATE_LIMITED` | `429` status or "rate limit exceeded". | Trigger AIMD backoff, retry once with jitter, then mark `COOLDOWN`. |
| `QUOTA_EXHAUSTED` | `402` status or `503` with "credit/allowance depleted". | Mark provider `EXHAUSTED` until next calendar reset window. |
| `AUTH_FAILED` | `401` status. | **Fail-Loud.** Quarantine provider, alert hypervisor, DO NOT rotate blindly. |
| `PROVIDER_UNAVAILABLE` | `503` / `504` status (genuine outage/timeout). | Mark `UNAVAILABLE`, backoff 60s, route to alternative ready pool. |
| `BAD_REQUEST` | `400` malformed JSON schema / parameter error. | **Fail-Loud.** Raise exception to worker runtime, do not rotate. |
| `CONTENT_POLICY` | `400` / `422` safety trigger. | Raise exception with policy violation details. |

---

## 9. Concurrent-Safe State Persistence (SQLite WAL)

Mutable router state is stored in a local SQLite database using **Write-Ahead Logging (WAL)**:
```
~/.local/share/paeos/model-router/state.sqlite3
```

### Database Schema

```sql
-- Provider operational health & configuration
CREATE TABLE providers (
    provider_id TEXT PRIMARY KEY,
    health_status TEXT NOT NULL,      -- HEALTHY, THROTTLED, COOLDOWN, EXHAUSTED, QUARANTINE
    current_concurrency INTEGER NOT NULL,
    max_concurrency INTEGER NOT NULL,
    cooldown_until REAL,
    last_error_type TEXT,
    last_error_time REAL
);

-- Sliding 1-minute and 1-day metering windows
CREATE TABLE provider_windows (
    provider_id TEXT NOT NULL,
    window_type TEXT NOT NULL,        -- 'minute' or 'day'
    window_start REAL NOT NULL,
    request_count INTEGER DEFAULT 0,
    token_count INTEGER DEFAULT 0,
    PRIMARY KEY (provider_id, window_type, window_start)
);

-- Validated Model Catalog (No assumed auto-discovery)
CREATE TABLE model_catalog (
    model_id TEXT PRIMARY KEY,
    provider_id TEXT NOT NULL,
    free_verified INTEGER NOT NULL,   -- 1 = verified free, 0 = paid
    context_window INTEGER NOT NULL,
    supports_tools INTEGER NOT NULL,
    supports_json INTEGER NOT NULL,
    verified_at REAL NOT NULL
);

-- Routing telemetry for empirical Economy of Reasoning scoring
CREATE TABLE routing_observations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp REAL NOT NULL,
    task_class TEXT NOT NULL,
    model_id TEXT NOT NULL,
    provider_id TEXT NOT NULL,
    latency_ms REAL NOT NULL,
    success INTEGER NOT NULL,
    normalized_error TEXT
);
```

---

## 10. Gateway & Credential Security

### 10.1 Loopback Isolation
LiteLLM is strictly bound to the loopback interface:
```bash
litellm --host 127.0.0.1 --port 4000 --config ~/.config/paeos/litellm_config.yaml
```
External network interfaces (`0.0.0.0`) are forbidden.

### 10.2 Secret Storage & Permissions
API credentials reside exclusively in:
```
~/.config/paeos/model-router.env (chmod 0600)
```

```bash
GEMINI_API_KEY=
CLINE_API_KEY=
NVIDIA_API_KEY=
KILO_API_KEY=
OPENROUTER_API_KEY=
```

### 10.3 Version Control Hygiene
`.gitignore` enforces clean exclusion of environment files while preserving example templates:
```gitignore
.env
.env.*
!.env.example
*.key
.config/
```

---

## 11. Phased Implementation Roadmap

- [ ] **Phase 1 (MVP — Transport Gateway & Loopback Security):** 
  - Install `litellm[proxy]` bound to `127.0.0.1:4000` with autonomous failovers disabled (transport only).
  - Register the 5 provider endpoints and connect secrets from `~/.config/paeos/model-router.env`.
  - Validate zero-cost probes on all 5 providers.
- [ ] **Phase 2 (Intelligent Router & SQLite State Engine):**
  - Implement `paeos/model_router/` (`policy.py`, `aimd.py`, `health.py`, `catalog.py`, `state.sqlite3`).
  - Implement the 5 logical aliases (`paeos-auto`, `paeos-strong`, `paeos-code`, `paeos-cheap`, `paeos-audit`).
  - Deploy normalized error parser and 80% known-limit / AIMD admission controller.
- [ ] **Phase 3 (Economy of Reasoning & Ensembles):**
  - Multi-stage constraint pipeline (Privacy $\rightarrow$ Capability $\rightarrow$ Context $\rightarrow$ Health $\rightarrow$ Quota $\rightarrow$ Score).
  - Quota partitioning (70/20/10) on Gemini 3.7.
  - Automated adversarial ensemble auditing with family diversity preferred for L09/L10; actual
    eligibility follows the ratified role/stage crosswalk and does not relax L07/L13/L14/L17/L18.

---

## 12. Pre-Prompt Anti-Drift Checkpoint Protocol

Before executing any prompt, dispatch, code modification, or architectural refactor, the Overseer/Hypervisor must verify:
1. **State Independence:** Is the task state persisted locally in PAEOS rather than relying on LLM context?
2. **Single Policy Authority:** Does PAEOS Router control all retries, fallbacks, and quotas, with LiteLLM functioning strictly as transport?
3. **Privacy Eligibility:** Does the task data class match the provider's data policy before calculating routing scores?
4. **Heterogeneous Audit Invariant:** For code-review stages where it applies, is code being
   reviewed by a distinct model family from the builder (`Builder != Auditor`)? This preserves
   the strict L14 rule and does not create an L09/L10 prerequisite for an L19 amendment.
5. **Cost Invariant:** Is OpenRouter restricted strictly to `openrouter/free` (`FREE_ONLY=true`)?
