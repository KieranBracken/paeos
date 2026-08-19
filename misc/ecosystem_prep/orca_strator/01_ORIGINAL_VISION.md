# Orca-strator Archaeology — 01 Original Vision

**System:** Orca-strator (Orca Multi-Agent Council & Orchestration Cockpit)  
**Location:** `/Users/bob/GitHub/orca-strator`  

---

## 1. Primary Purpose & Definition

Orca-strator was designed as an **orchestration cockpit and local multi-agent council system**. It provides:
- Multi-provider model routing (DeepSeek Direct, Qwen/OpenRouter, Hermes CLI, Antigravity Route).
- Interactive GUI & Command Dashboard (FastAPI + React/Vite).
- Agent Council ensemble configurations and cost circuit breakers.
- Active multi-agent conversation threads and project context injection.

---

## 2. Key Unresolved Questions for PAEOS

1. **User-Land Orchestration vs Execution Governance**: Does Orca-strator serve as the **user-facing interactive cockpit / multi-agent collaboration environment**, while PAEOS owns the **constitutional execution governance, verification court, and CAS state**?
2. **Duplication of Model Routing**: Orca-strator has vendor routing in Python/FastAPI (`backend/app/providers`), while PAEOS has `runtime/integrations/hybrid.py`. Should PAEOS expose an API driver that Orca-strator consumes?
3. **Integration Boundary**: Orca-strator is an application-level multi-agent engine, whereas PAEOS is the core autonomous OS substrate.
