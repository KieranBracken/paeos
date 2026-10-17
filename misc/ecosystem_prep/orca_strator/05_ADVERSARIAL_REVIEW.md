# Orca-strator First-Principles Redesign — 05 Adversarial Review (Model C)

**Perspective:** Adversarial Architect (Flaw Identification & Bad Assumption Removal)  

---

## 1. Identified Flaws & Bad Assumptions

1. **Duplicated Model Provider Infrastructure**: Orca-strator implements provider routing in Python (`backend/app/providers`), duplicating PAEOS's model router (`runtime/integrations/hybrid.py`).
2. **Coupling to Full-Stack Web Monolith**: Orca-strator mixes agent orchestration logic with web UI server code, making it difficult to run headless under PAEOS governance.

---

## 2. Unresolved Design Space

- PAEOS must determine whether Orca-strator should be refactored into a decoupled client GUI that connects to PAEOS's core runtime driver API.
