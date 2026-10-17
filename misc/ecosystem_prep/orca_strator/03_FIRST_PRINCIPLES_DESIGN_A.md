# Orca-strator First-Principles Redesign — 03 Blind Architect (Model A)

**Perspective:** Blind Architect (Zero Knowledge of Existing Orca Codebase)  
**Objective:** Derive optimal multi-agent council cockpit and provider router from first principles.

---

## 1. Problem Formulation

A multi-agent council system must manage:
1. **Agent Ensemble Assemblies**: Dynamic formation of worker, critique, and judge agent councils for complex tasks.
2. **Provider Routing & Fallbacks**: Transparent model switching (DeepSeek, Qwen, OpenRouter, OpenAI, Local models) with rate-limit and cost safety controls.
3. **Interactive Control Plane**: Real-time streaming session feeds, project context injection, and user intervention controls.

---

## 2. Ideal First-Principles Architecture

- **Substrate Components**:
  - `CouncilOrchestrator` (Task decomposition & agent council assembly)
  - `ModelRouter` (Heterogeneous provider driver with cost circuit breakers)
  - `SessionStore` (Isolated agent conversation threads)
  - `ContextInjector` (Repository topology & document state injector)
