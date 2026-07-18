# 06 — Security Review (Investigation 11)

Threat model: every agent is compromised (malicious model output, prompt-injected, or
simply wrong — the kernel cannot distinguish and must not need to). Adapters are
trusted-but-conformance-verified. The founder is sovereign (H2 — no defense exists or is
claimed; detection only). Trust boundary = the WRITE validator + syscall stamping.

## Attacks attempted, with outcomes AFTER the 01-register patches

| # | Attack | Pre-patch result | Post-patch defense |
|---|---|---|---|
| A1 | Forge execution Evidence ("tests passed") via ProposedWrites | **SUCCEEDS** — provenance is proposer-supplied | B-02 server-side stamping + H-03 `SIG` check: execution class requires kernel-stamped `actor: syscall` + valid Ed25519 over payload hash; agents cannot produce either |
| A2 | Forge provenance on any object (impersonate founder / another role) | **SUCCEEDS** | B-02: author fields rejected from proposers, stamped from spawn lease |
| A3 | Eternal verdict evidence (empty read-set) | **SUCCEEDS** | H-02 kernel-stamped minimum read-set {goal version, context manifest} |
| A4 | Self-promote goal status inside a proposed Goal version | **SUCCEEDS** (nobody owns status ⟹ nobody rejects it either) | B-01: status is kernel-maintained; proposed status = FORBIDDEN_CLASS |
| A5 | Mint budget by decomposition (child allocations) | blocked (K11) — but see A6 | conserve() at WRITE, two-phase leases (03) close the crash-leak variant |
| A6 | Leak budget via crashed SPAWNs (reserve, crash, repeat) | **SUCCEEDS** (unspecified) | 03 two-phase lease: unsettled reservations expire at boot |
| A7 | Smuggle a Policy (skill) via ProposedWrites, bypassing amendment | blocked: Policy versions legal only as effect of integrated amendment goals (§9.4) — validator check exists (K6/X-class); fixture pair REQUIRED in F-VAL (was missing — add) |
| A8 | Poison a sibling tournament candidate (read/overwrite its speculation) | blocked post-B-04/H-07: worktree isolation + C4; sequential adapters covered by A-16 conformance |
| A9 | Trigger-bomb: skill with trigger matching everything, bloating every context | partially open: triggers are workload/kernel-scoped policies that only enter via amendment ceremony — the ceremony is the defense; residual risk accepted (a bad amendment is an incident, falsifier reverts it) |
| A10 | Evidence-spec gaming by a compromised Decomposer | open by design at kernel level; defense is the (F,GOALSTRUCT) spec-sufficiency audit (A-11) — procedural, not mechanical. Documented residual |
| A11 | Forged classification (label irreversible work reversible ⟹ skip ceremony) | partially open: classification is SELECT-stance evidence; a lying classifier evades ceremony once. Defenses: classification expiry (A-14) + post-integration dependents index catches the reversibility lie late; earliness gap is REAL and accepted as residual — log as known limitation, mitigable by protocol-level second classification on guarded/irreversible candidates (evolution-layer, not kernel) |
| A12 | Tamper with store files directly (agent shells out, edits store/objects) | EXEC sandbox denies store paths (write-mask: worktree only — pin in sandbox contract, was implicit ⟹ **new pin**); BOOT-5 detects offline tampering; sovereign-founder tampering: detection only (H2) |
| A13 | Forge adapter signature (steal key) | key custody is adapter-host OS security — out of kernel scope; genesis trust roots allow key rotation via amendment (K4 §13.1); compromise = incident + rotation. Documented |
| A14 | Malicious genesis (tampered spec hashes) | BOOT-3 verifies against spec/ files — circular if both tampered; irreducible (parchment). The reproducible-constitution audit (PAEOS-3 §4 maturity) is the long-run detector |
| A15 | Prompt-injection via Artifact content into compiled context | REAL and unmitigated at kernel level: compiler includes linked artifact bodies verbatim; a hostile artifact can steer any agent that links it. Defenses: (a) provenance is visible in manifest (agents can be instructed to distrust — weak), (b) K1 means a steered agent still cannot promote without evidence, (c) the blast radius is bounded by mutation matrix + validator. Accept as **the** residual risk class of LLM-native systems; document prominently; do not pretend a kernel fix exists |

## New pins from this review
Sandbox write-mask = worktree only (A12) · F-VAL must include the A7 fixture pair ·
key-rotation-by-amendment procedure note (A13).

## Security verdict
With the 01-register patches, every *mechanical* forgery path found is closed (A1–A8).
Three residuals are real and must be stated in the constitution's threat-model preamble
rather than hidden: early-misclassification (A11), evidence-spec gaming (A10), and
prompt-injection-via-artifact (A15). All three are bounded by K1 (no promotion without
evidence) — the kernel's last line holds even when judgment layers are steered, which is
exactly why K1 exists.
