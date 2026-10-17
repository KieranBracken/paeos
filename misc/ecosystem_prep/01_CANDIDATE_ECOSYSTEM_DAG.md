# Candidate Ecosystem Dependency DAG — v0.1

**Status:** Candidate Architecture Graph  
**Domain:** Cross-System Directed Dependency Mapping  

---

## 1. Candidate Ecosystem Dependency Graph

```text
                 ┌────────────────────────────────┐
                 │             PAEOS              │
                 │ (Constitutional Execution OS)  │
                 └───────────────┬────────────────┘
                                 │
                   governs self-construction
                                 │
         ┌───────────────────────┴───────────────────────┐
         │                                               │
         ▼                                               ▼
  ┌─────────────┐                                 ┌─────────────┐
  │    SAKG     │                                 │ Concept OS  │
  │(Causal Graph│                                 │ (Discovery  │
  │ Substrate)  │                                 │  Substrate) │
  └──────┬──────┘                                 └──────┬──────┘
         │                                               │
  queries laws &                                  queries concept
   constraints                                       topology
         │                                               │
         └───────────────────────┬───────────────────────┘
                                 │
                                 ▼
                         ┌───────────────┐
                         │ Orca-strator  │
                         │(Multi-Agent   │
                         │ Council GUI)  │
                         └───────┬───────┘
                                 │
                        routes execution
                                 │
                                 ▼
                         ┌───────────────┐
                         │Sentium Core & │
                         │Paper Trading  │
                         └───────────────┘
```

---

## 2. Explicit Directed Edge Semantics

1. `PAEOS --GOVERNS_EXECUTION--> SAKG`
   - PAEOS enforces constitutional verifier rules over SAKG graph modifications.
2. `PAEOS --GOVERNS_EXECUTION--> Concept OS`
   - PAEOS provides execution governance for discovery searches executed by Concept OS.
3. `Orca-strator --QUERIES--> SAKG`
   - Orca-strator agent councils query SAKG for causal engineering constraints and architectural laws.
4. `Orca-strator --QUERIES--> Concept OS`
   - Orca-strator agent councils query Concept OS for concept proximity, analogies, and semantic blending.
5. `Orca-strator --ROUTES_EXECUTION--> Sentium Trading`
   - Orca-strator routes multi-agent strategy evaluations to Sentium's paper-trading engine.
