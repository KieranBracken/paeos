# PAEOS Implementation Atlas

> Living inventory of all PAEOS modules, Trusted Computing Base (TCB) components, and runtime execution surfaces.
> Governed by state **L15 (Documentation & Ledger)** — updated automatically upon task completion.

---

## Architecture & Trust Zones

| Trust Zone | Boundary | Isolation Mechanism | Permitted Mutations |
| :--- | :--- | :--- | :--- |
| **Zone 0** | Immutable Constitution ($Z_0$) | File system read-only / Aks-accessor | Amendment ceremony only (K7/§14.5) |
| **Zone 1** | Trusted Computing Base (`kernel/`) | Strict type checking (`pyright`), LOC Budget ($\le$ 20k LOC), CI TCB-diff gate | Single-threaded integration (`K8`/`I9`) |
| **Zone 2** | Untrusted Runtime & Agents (`runtime/`, `mcp/`, `cli/`) | Subprocess / Sandbox execution | Ephemeral execution per task lease |

---

## Living Component Inventory

| Component ID | Module Path | Constitutional Authority | Trust Zone | Status | Test Coverage | Review Reference |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **B0.0-TOOL** | [pyproject.toml](file:///Users/bob/GitHub/paeos/pyproject.toml) | PAEOS-8 §3, §8 | Zone 1 (TCB) | **Sealed** | 100% | `reviews/tasks/B0.0_review.md` |
| **B0.1-LEDGER**| [kernel/ledger.py](file:///Users/bob/GitHub/paeos/kernel/ledger.py) | PAEOS-4 §2 / PAEOS-7.6 §2 | Zone 1 (TCB) | **Sealed** | 100% (1,000-event property) | `reviews/tasks/B0.1_review.md` |
| **B0.2-CAS** | [kernel/cas.py](file:///Users/bob/GitHub/paeos/kernel/cas.py) | PAEOS-4 §2 / PAEOS-8 §10 | Zone 1 (TCB) | **Sealed** | 100% (10,000-blob scale) | `reviews/tasks/B0.2_review.md` |
| **B0.3-CONST** | [kernel/constitution.py](file:///Users/bob/GitHub/paeos/kernel/constitution.py) | PAEOS-4 §6 / PAEOS-7.6 §4 | Zone 0 (Read-Only) | **Sealed** | 100% | `reviews/tasks/B0.3_review.md` |
| **B0.4-TYPES** | [kernel/types.py](file:///Users/bob/GitHub/paeos/kernel/types.py) | PAEOS-7.6 §3–4 / IP-0002 | Zone 1 (TCB) | **Sealed** | 100% | `reviews/tasks/B0.4_review.md` |
| **B0.5-CYCLE** | `kernel/lifecycle.py` | PAEOS-7 §4.1 / IP-0003 | Zone 1 (TCB) | *In-Progress* | Pending | `reviews/tasks/B0.5_review.md` |

---

## Governance & Maintenance Protocol

1. **Mandatory L15 Update**: Every task reaching state **L15 (Documentation & Ledger)** MUST register or update its entry in this table.
2. **Provenance Traceability**: Every component entry MUST reference its constitutional authority (spec/clause reference) and its passing review report under `reviews/tasks/`.
3. **No Un-derived Components**: No component may be added to this inventory without explicit derivation from $Z_0$, `spec/`, or a ratified Improvement Proposal (`proposals/PAEOS-IP-NNNN.md`).
