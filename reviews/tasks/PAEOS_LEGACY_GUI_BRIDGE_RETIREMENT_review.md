# Constitutional Implementation Review: LEGACY_GUI_BRIDGE_RETIREMENT

**Date**: 2026-08-31
**Task**: Retire the legacy browser/clipboard bridge control path (DEBT-0060 remediation)
**Reviewer Role**: Temporary Architect/Overseer — independent adversarial checkpoint

## Scope and evidence

The retired entrypoints are `ops/chatgpt_bridge/bridge.py`, `cron_bridge.sh`, and
`launch_chrome_debug.sh`.  The previous implementation polled a log, drove a browser debugging
endpoint, and pasted into the frontmost terminal.  That path had no transaction fencing or durable
response binding and could stall for long browser/response waits.  Each entrypoint now exits with
status `2` before parsing arguments, opening a network connection, launching a process, changing
the clipboard, or targeting a terminal.  `cline_wrapper.sh` remains output capture only and its
documentation explicitly says it is not a transport.

Evidence collected in the isolated recovery worktree:

- TDD RED: the new bridge test failed against the old argparse entrypoint (`--help` returned `0`).
- TDD GREEN: focused legacy-path and existing control-plane checks passed **23/23**, exit `0`.
- Full non-gateway suite passed **1,060/1,060**, exit `0`; the gateway-server fixture remains
  separately excluded because restricted loopback binding is not available in this environment.
- Ruff on changed Python files: **All checks passed**.
- Pyright on changed Python files: **0 errors, 0 warnings, 0 informations**.
- Direct launcher probes: all three retired entrypoints returned `2` and emitted only a
  fail-closed diagnostic. No provider, credential, browser, clipboard, or terminal activity was
  performed.
- Detached verifier `/private/tmp/paeos-l13-fa59117` independently reproduced the post-repair
  tree: **1,060/1,060** non-gateway tests passed, exit `0`. Raw log SHA-256 is
  `bbdcfafbf3fbec3e4686c37ffecf614031941853012be3dfe1602ea4aa2d1fc7`; exit-record SHA-256 is
  `9a271f2a916b0b6ee6cecb2426f0b3206ef074578be55d9bc94f6f3fe3ab86aa`.

## Summary of Findings

- **BLOCKER**: 0
- **MAJOR**: 0
- **MINOR**: 0
- **OBSERVATION**: 2

## Evaluation Checklist

### 1. Constitutional Compliance

**PASS.** The change is confined to the approved isolated recovery exception, preserves the
state-root-bound control plane, and does not alter lifecycle law, gate state, Court state, or
`main`/`trunk`. It strengthens the no-unbound-terminal and no-implicit-side-effect invariants.

### 2. Architectural Drift

**PASS.** No new architectural concept or protocol was introduced. The change removes an
underdetermined compatibility path and directs operators to already-existing protocol-backed
runtime components.

### 3. Duplication of Mechanisms

**PASS.** The retired code duplicated transport behavior outside `bridge_protocol.py` and the
state-root watchdog. Removing it reduces the number of active mechanisms rather than adding one.

### 4. Bypassing Mechanisms

**PASS.** The old browser, clipboard, and frontmost-terminal bypasses are no longer executable.
The canonical transaction store and watchdog remain the only supported control-plane paths.

### 5. Simpler Implementation Possible

**PASS.** A minimal fail-closed stub is the smallest safe replacement; retaining the old loop
behind a flag would leave an unsafe invocation surface.

### 6. Better Derivation

**PASS.** The implementation follows the existing state-root-bound watchdog and bridge protocol
contracts. It does not infer a new transport from the historical GUI behavior.

### 7. Hidden Technical Debt

**OBSERVATION.** `DEBT-0060` is materially mitigated at the legacy-entrypoint boundary but is not
closed until a canonical coordinator/transaction exercise proves end-to-end recovery. The
restricted gateway fixture also remains an environmental verification limitation.

### 8. Security Implications

**PASS.** Removing arbitrary browser automation and frontmost-terminal pasting eliminates a
   cross-window injection and misdelivery surface. The stubs perform no external I/O.

### 9. Runtime Implications

**PASS.** The retired path can no longer hang on polling, browser connection, or streaming waits.
The replacement exits deterministically with a non-success status that callers can detect.

### 10. Future Extensibility

**PASS.** Provider/model interchangeability remains in the router and protocol-backed adapters;
the retirement does not vendor-lock the architecture. Future transports must satisfy the same
transaction binding and evidence contracts rather than reintroduce GUI automation.

## Action Items & Proposals

- [x] Add discriminative regression coverage for all three retired entrypoints.
- [x] Update the bridge README and wrapper comments to prevent accidental reactivation.
- [ ] Keep `DEBT-0060` open until a coordinator-backed liveness/recovery transaction is
      independently reproduced and admitted by Court.
- [ ] Obtain a fresh candidate-bound L14/L17 audit for this post-change commit before any gate
      closure or SAKG resumption decision.

The attempted audit dispatch for this candidate was stopped before provider contact because the
execution boundary requires explicit authorization for this exact internal bundle and destination.
No workaround, fallback, or retry was attempted.

## Disposition

`IMPLEMENTATION_CHECKPOINT — READY FOR INDEPENDENT L13/L14/L16 RECONCILIATION`.

This review is not a gate seal, Court disposition, Founder ratification, or authorization to
resume SAKG.
