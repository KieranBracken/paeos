# 04_MACHINERY_CLASSIFICATION: Infrastructure Categorization

This document explicitly classifies all repository infrastructure into functional categories based on their relation to the canonical 19-layer execution doctrine.

## 1. Canonical PAEOS Machinery (The Frozen Kernel)
This is the core foundation that enforces the invariant rules. It is fully implemented and operational.
*   **Location**: `kernel/`
*   **Components**:
    *   `lifecycle.py`: The edge oracle, defines the exact sequence of 19 states.
    *   `types.py`: The constants (`StageId`, `Outcome`, `Role`, `WeightClass`).
    *   `gates.py`: The four-tuple transition contract enforcer.
    *   `capability.py`: The unforgeable capability token minter and verifier.
    *   `seal.py`: The final immutable seal authority.
    *   `ledger.py`, `cas.py`: The persistence layer.
*   **Status**: IMPLEMENTED & CANONICAL.

## 2. Transitional Implementation (The Vertical Slice)
This infrastructure orchestrates the build-verify-seal pipeline. It is intentionally partial, bypassing several cognitive layers to establish a working pipeline.
*   **Location**: `runtime/orchestrator/__init__.py`, `runtime/agents/__init__.py`
*   **Components**:
    *   `SoftLoop`: The phase-1 unattended runner. Hardcodes transitions from `L02` -> `L08` -> `L11` -> `L12` -> `L13` -> `L10/L14` -> `L16`.
    *   `StagePlaybook`: Invokes agent sessions for specific tasks.
    *   `Court`: The deterministic evidence runner (L13).
    *   `InformationBarrierManager`: The Z1/Z2 boundary enforcer for Adversarial Review (L10/L14).
*   **Status**: IMPLEMENTED but TRANSITIONAL (Incomplete against the full 19-layer specification).

## 3. Experimental / Work-In-Progress Infrastructure
This infrastructure is actively being developed to support the full 19-layer vision, but is not yet fully integrated or complete.
*   **Location**: `kernel/rcl.py`, `kernel/state.py`
*   **Components**:
    *   `Reasoning Continuity Layer (RCL)`: Designed to checkpoint intermediate cognitive state.
*   **Status**: EXPERIMENTAL (Paused pending construction of missing cognitive layers).

## 4. External / Tooling Infrastructure
This is the command-line and operational tooling used to invoke PAEOS.
*   **Location**: `ops/`, `cli/` (if any), `tests/`
*   **Components**:
    *   `autonomous_run.py`: The wrapper script to invoke the `SoftLoop`.
    *   Testing frameworks (`pytest`).
*   **Status**: IMPLEMENTED & OPERATIONAL.
