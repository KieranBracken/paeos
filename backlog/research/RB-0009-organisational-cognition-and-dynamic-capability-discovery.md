# RB-0009 — Organisational Cognition & Dynamic Capability Discovery

**Status:** Research
**Priority:** High
**Origin:** Founder Observation
**Created:** August 2026

---

# Motivation

PAEOS currently possesses strong execution, verification, governance, debate, and self-hosting capabilities.

However, there is an open research question:

> **How should an autonomous engineering organisation recognise that it lacks a capability before producing poor work?**

Current behaviour is largely reactive:

```text
Plan

↓

Build

↓

Blocked

↓

Retry

↓

Remand

↓

Retry
```

This may encourage repeated failures or increasingly weak solutions when the correct response should instead be:

> "I cannot solve this with my current capabilities."

The objective is to investigate how an autonomous engineering organisation should recognise capability gaps, acquire assistance, and evolve organisational structure without compromising constitutional governance.

---

# Motivation Questions

* How does an engineering organisation recognise that it is missing knowledge?
* How should agents request assistance?
* Who decides what assistance is provided?
* How should specialist roles emerge?
* How should organisations prevent capability explosion?
* How should local optimisation be balanced against global objectives?
* How should new organisational structures be justified?

---

# Research Topics

## 1. Organisational Cognition

Investigate whether engineering organisations possess emergent cognition beyond the reasoning of individual agents.

Possible areas:

* distributed cognition
* organisational psychology
* engineering team structures
* collaborative reasoning
* knowledge distribution
* information asymmetry

---

## 2. Capability Discovery

Research mechanisms allowing agents to recognise:

* insufficient knowledge
* missing expertise
* hidden assumptions
* architectural uncertainty
* prerequisite gaps

before implementation begins.

---

## 3. Capability Requests

Investigate a general capability request mechanism.

Rather than requesting:

```text
Database Expert
```

agents request

```text
Capability:
Database optimisation
```

leaving organisational allocation separate from capability need.

---

## 4. Capability Broker

Research an organisational broker responsible for allocating assistance.

Possible responsibilities:

* specialist selection
* council formation
* model routing
* tool selection
* external knowledge retrieval
* human escalation

without allowing requesting agents to allocate resources themselves.

---

## 5. Local vs Global Optimisation

Each role possesses different motivations.

Examples:

Planner

* wants planning clarity

Builder

* wants implementation simplicity

Designer

* wants architectural elegance

Verifier

* wants certainty

Adversary

* wants falsification

Founder

* wants original intent preserved

Research how these competing motivations should be balanced.

---

## 6. Dynamic Specialists

Rather than maintaining hundreds of permanent specialist agents,

investigate whether specialists should emerge dynamically from capability requests.

Questions include:

* temporary specialists
* reusable specialists
* retirement
* capability evolution
* specialist merging

---

## 7. Dynamic Councils

Current debate structures are largely predefined.

Research:

* spontaneous council creation
* temporary review boards
* capability-specific councils
* weighted voting
* consensus mechanisms
* constitutional escalation

---

## 8. Engineering Friction & Blockage Analysis

Investigate engineering friction as a multi-signal diagnostic quantity rather than a rigid integer threshold.

Instead of a simple "N remands = research" rule, research a rich `BlockageAnalysis` that evaluates:

* repeated remands
* blockage type (implementation error vs planning gap vs architectural flaw)
* capability availability
* confidence trajectory

Possible diagnostic routing outputs:

* `RETRY` (local implementation bug)
* `RETURN_TO_PLANNER` (flawed plan)
* `RETURN_TO_DESIGNER` (architectural uncertainty)
* `REQUEST_CAPABILITY` (missing specialist or tool)
* `RESEARCH` (unknown domain knowledge)
* `PROPOSAL` (constitutional/TCB conflict)
* `FOUNDER` (ambiguous founder intent)

Can friction itself become an optimization signal?

---

## 9. Capability Demand Analytics

Over long periods PAEOS should observe:

```text
Capability Requested

↓

Frequency

↓

Success Rate

↓

Impact

↓

Recommendation
```

Questions:

When should frequently requested capabilities become permanent organisational machinery?

---

## 10. Safe Self-Improvement

Investigate how organisational evolution should occur safely.

Potential principles:

* constitutional review
* proposal generation
* debate
* adversarial challenge
* founder ratification
* staged deployment

rather than autonomous self-modification.

---

# Open Questions

* What constitutes a capability?
* How should capability requests be represented?
* Should requests be typed?
* Should requests be probabilistic?
* How should organisations recognise unknown unknowns?
* Can capability demand itself reveal missing architectural machinery?
* Should organisational structure evolve continuously?
* How are new capabilities retired?
* How should multiple competing capability recommendations be resolved?

---

# Possible Future Outputs

This research may eventually produce one or more proposals, including (illustrative only):

* Capability Discovery Framework
* Capability Broker
* Organisational Cognition Layer
* Dynamic Specialist Architecture
* Dynamic Council Formation
* Engineering Friction Analysis
* Capability Demand Analytics

No implementation is implied by this research backlog.
