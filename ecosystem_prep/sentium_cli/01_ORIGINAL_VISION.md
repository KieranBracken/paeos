# Sentium CLI Orchestrator Archaeology — 01 Original Vision

**System:** Sentium CLI Orchestrator & Operational Control Plane  
**Location:** `/Users/bob/GitHub/cli_orchestrator`  

---

## 1. Primary Purpose & Definition

`cli_orchestrator` was created as the **operational control plane, CLI launcher, and system orchestrator for Sentium**.

Key Features:
- `Start_Sentium.command`: Native macOS shell script launcher.
- `SENTIUM_INVENTORY_ATLAS.md`: Master inventory atlas (2.3 MB) tracking all files, systems, and capabilities in the Sentium workspace.
- Backend bridge logger, process lifecycle tracker (`orchestrator_pid.txt`), and SQLite ledger (`sentium_ledger.db`).

---

## 2. Key Unresolved Questions for PAEOS

1. **Relationship to Orca-strator**:
   - Both `cli_orchestrator` and `orca-strator` perform orchestration tasks.
   - *Question*: Is `cli_orchestrator` the **Sentium domain operational control plane**, while `orca-strator` is the **multi-agent GUI/council cockpit**, and PAEOS is the **constitutional OS substrate**?
2. **Inventory Atlas Integration**:
   - `cli_orchestrator` maintains `SENTIUM_INVENTORY_ATLAS.md`. How should PAEOS import or consume this inventory during ecosystem discovery?
