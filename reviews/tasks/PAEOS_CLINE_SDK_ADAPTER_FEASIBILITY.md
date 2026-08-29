# PAEOS Cline SDK Admission Adapter — Public-Surface Feasibility Record

**Date:** 2026-08-29
**Lifecycle:** L12, Gate A remediation, Task 1
**Classification:** `UNADMITTED_BOOTSTRAP_CANDIDATE`
**Architectural baseline:** `d2c984b7a6d96b2e3e8ea0598bf779568de2116b`
**Frozen-plan commit:** `94112953ae6a388cbc2d824b719df826dcef810d`

## Scope

This record reports read-only qualification of the installed public Cline SDK surface. The
inspector did not start Cline, read a Cline profile, access Keychain, inspect a credential, contact
a provider, run a worker admission probe, or grant production authority.

## Qualified Tuple

- Cline package root: `/opt/homebrew/lib/node_modules/cline`
- Cline version: `3.0.60`
- `@cline/sdk`: `0.0.81`
- `@cline/core`: `0.0.81`
- Resolved Node version: `24.1.0`
- Backend qualification scope: explicit public `local` mode only
- Qualified public symbols: 19
- Content-hashed closure files: 26,450
- Canonical record size: 6,166,807 bytes
- Canonical record mode: `0600`

The qualified declarations include the public `ClineCore.create`, `start`, `subscribe`, `abort`,
and `stop` lifecycle; explicit provider/model/session configuration; local backend selection;
spawn, teams, tools, and MCP-settings controls; `toolPolicies`, `requestToolApproval`, and
`toolExecutors`; an injectable `fetch`; and returned manifest/message paths.

## Evidence

- External create-only record:
  `/Users/bob/.local/share/paeos/runtime-v2/adapter-qualification/cline-3.0.60-sdk-0.0.81-bd34e644.json`
- Qualification-record digest:
  `bd34e644dab3bc0812b351c1f0906ce2a9279b761e87a00a27678b7e020728aa`
- Serialized record-file SHA-256:
  `5c3a2a50e8e6bc61e72e703cfbbf3a85b24daa9dd13ba06575d8e695b3b5f5cc`
- Preflight and external record bytes were byte-identical.

The record contains paths, versions, byte counts, content hashes, required-symbol identifiers, and
its canonical digest. It contains no package source contents or credential/profile data.

## TDD Evidence and Findings

The initial focused test run failed during collection because the qualification module did not
exist. After the minimal implementation, eight negative cases exposed overly broad token matching;
the implementation was corrected to require identifier and method boundaries. The focused suite
then passed 18 tests.

The first real installed-tree preflight returned
`MISSING_DEPENDENCY,PACKAGE_ESCAPE`. Read-only inspection proved all 321 resolved packages were
present and showed no package symlinks. Two new regression tests then demonstrated the actual bug:
the inspector assumed every dependency was hoisted and misclassified a missing dependency as an
escape. Those tests failed before remediation. Node-compatible upward dependency resolution and
precise missing-dependency classification were implemented; the resulting focused suite passed
exactly **20/20**.

Final Task 1 verification:

- focused pytest: 20 passed, 0 failed;
- Ruff: all checks passed;
- Pyright: 0 errors, 0 warnings, 0 information messages;
- real public-surface inspection: `QUALIFIED_PUBLIC_SURFACE`;
- provider calls: 0;
- worker admission probes: 0.

The repository-wide baseline has two pre-existing failures in
`tests/ops/test_worker_admission_probe.py`: its subprocess helper hard-codes the obsolete
`/private/tmp/paeos-control-plane-recovery-s1-clean` worktree, where the Task 4 transport module is
absent. Task 7 of the frozen plan already owns that file. Four loopback-server errors observed in
the restricted sandbox disappear when the test process is allowed to bind its loopback-only test
port. Neither baseline condition is caused by Task 1.

## Disposition

**Task 1 public-surface qualification: PASS.** The precise installed tuple is eligible to proceed
to Task 2 contract implementation. This is not a claim that the runtime behavior is qualified:
Tasks 4–5 must still prove that the public callbacks actually prevent default tool execution and
expose complete attempt telemetry. Any failure there invalidates this tuple without fallback to
the legacy CLI or private APIs.

Worker admission remains exactly **Admitted: 0 | Rejected: 1 | Remediated: 0**. Gate A Court
accounting remains exactly **Sealed: 0 | Remanded: 0 | Remediated: 0**. DEBT-0058 remains open.
No L13 reproduction, L14 decorrelated audit, L17 constitutional review, Court seal, Founder
ratification, or Gate A closure is claimed.
