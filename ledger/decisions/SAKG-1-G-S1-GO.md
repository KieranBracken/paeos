schema: paeos.sakg.g-s1-go/v1
task_id: SAKG-1/G-S1-GO
title: FOUNDER GATE A4 — S1 go/no-go decision
decision: PROCEED
decision_scope: S1 semantic architectural knowledge graph slice
authority: Founder/Court disposition
recorded_at: 2026-09-02T12:00:00Z

## evidence

probe: reviews/spikes/sakg-s1-extraction-probe.md
probe_sha256: e953b9e3417ddb89992de1d40b1e1e404f228298e08b1e76e267beeba8f2c756
probe_verdict: NO-GO
loss_ratio: 0.503
field_total: 153
weighted_loss: 77.0

The S-PROBE falsified a lossless extractor from the three sealed Gate records alone.  The
Founder decision is therefore conditional: PROCEED means continue the S1 build only inside the
synthetic operating envelope below; it does not convert the NO-GO into a GO, promote frequency
into evidence, or authorize canonical SAKG knowledge.

## conditional synthetic operating envelope

- workflow: Strict Trace-A only
- reversibility: reversible changes only; no protected-ref or production actions
- concurrency: 1
- data_classification: INTERNAL
- evidence: typed capability broker, immutable CAS, reproducible Court command, physical A-08 audit
- provenance: every node and extraction result remains a candidate until independently verified
- promotion: evidence-gated only; frequency, authored confidence, and model assertion are not proof
- deletion: prohibited; supersession/refutation must retain the prior node
- audit: Builder != Auditor; a physical heterogeneous review is required before any constitutional seal

## scope and stop conditions

This decision authorizes the next S1 implementation tasks (including schema, bundle, fixture, and
extraction work) as experiments under the envelope. It does not authorize SAKG resumption, a Gate
seal, a merge/promotion, or a claim that SAEOS-1 §4.2 fields are recoverable from prose. Stop and
REVERT the S1 slice if a subsequent evidence-backed review confirms the loss ratio is fatal or if
any task requires widening the envelope.

## falsifier

An independent, candidate-bound audit may falsify this decision by showing that the required
envelope invariants cannot be enforced, that the evidence binding is non-reproducible, or that
the next task cannot remain reversible and INTERNAL under serial Trace-A execution.
