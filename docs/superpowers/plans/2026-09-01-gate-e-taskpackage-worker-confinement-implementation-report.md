bash: warning: setlocale: LC_ALL: cannot change locale (C.UTF-8): Bad file descriptor
bash: warning: setlocale: LC_ALL: cannot change locale (C.UTF-8): Bad file descriptor
bash: warning: setlocale: LC_ALL: cannot change locale (C.UTF-8): Bad file descriptor
bash: warning: setlocale: LC_ALL: cannot change locale (C.UTF-8): Bad file descriptor
bash: warning: setlocale: LC_ALL: cannot change locale (C.UTF-8): Bad file descriptor
bash: warning: setlocale: LC_ALL: cannot change locale (C.UTF-8): Bad file descriptor
bash: warning: setlocale: LC_ALL: cannot change locale (C.UTF-8): Bad file descriptor
bash: warning: setlocale: LC_ALL: cannot change locale (C.UTF-8): Bad file descriptor
bash: warning: setlocale: LC_ALL: cannot change locale (C.UTF-8): Bad file descriptor
bash: warning: setlocale: LC_ALL: cannot change locale (C.UTF-8): Bad file descriptor
bash: warning: setlocale: LC_ALL: cannot change locale (C.UTF-8): Bad file descriptor
bash: warning: setlocale: LC_ALL: cannot change locale (C.UTF-8): Bad file descriptor
bash: warning: setlocale: LC_ALL: cannot change locale (C.UTF-8): Bad file descriptor
bash: warning: setlocale: LC_ALL: cannot change locale (C.UTF-8): Bad file descriptor
# Gate E TaskPackage Worker Confinement — Implementation Report

- **Stage:** IMPLEMENT (BUILDER), run `r-da5d7dad`, 2026-09-01.
- **Objective (received):** Gate E current-candidate remediation — complete the frozen
  TaskPackage worker-confinement contract in `kernel/sandbox.py` /
  `kernel/sandbox_backend.py`: fail-closed enforcement of every requested boundary,
  no weaker fallback, without changing lifecycle authority or enabling production
  execution routing.
- **Governing authority:** the frozen plan
  `docs/superpowers/plans/2026-08-26-paeos-taskpackage-worker-confinement.md` (Task 5)
  governs on every divergence; the planner chain (RE_DERIVE → IDEATE → RESEARCH →
  TRADEOFF → MITIGATION → DESIGN → CRITIQUE → ADVERSARIAL_REVIEW → PLAN) supplies the
  defaults in its silence.

## 1. What was implemented

### 1.1 The defect, fixed

`PortableSandboxBackend.supports` answered `profile.cpu_seconds > 0 and
profile.memory_bytes > 0` — it asserted CPU+memory only, silently ignoring
process-count, disk, network, executable-hash, workspace-write, timeout-group, and
output-size requests. It is now a **thin boolean view of a total fail-closed
negotiation** derived from an 11-dimension taxonomy; any requested dimension the
backend cannot *enforce* yields a typed
`UnsupportedDimension(dimension, missing_mechanism, caveat)` refusal,
`supports()` is False, `run()` raises the typed stop
`SandboxProfileUnavailable` ("SANDBOX_PROFILE_UNAVAILABLE: …"), and **no execution
occurs at all**. There is no weaker fallback anywhere: no alternate-backend walk, no
"closest profile", no default-argument downgrade, no `getattr` capability lookup.

### 1.2 Negotiation architecture (the chain's Candidate-B backbone)

- **Dimension taxonomy** (`kernel/sandbox_backend.Dimension`): CPU, MEMORY,
  OPEN_FILES, FILE_SIZE, DISK, PROCESS_COUNT, NETWORK, EXECUTABLE_HASH,
  WORKSPACE_WRITE, WALLCLOCK_GROUP, OUTPUT_SIZE — the identity source for
  negotiation, refusal entries, and report facts. `requested_dimensions()` is
  derived from the profile fields (present/constraining ⇒ requested; absent ⇒
  unbounded-by-explicit-choice — never an invented default).
- **Single claim registry** consumed by *both* `supports()` and `run()` (inspected ==
  enforced). An import-time and construction-time taxonomy⇔registry bijection
  assertion (`assert_registry_covers`) fails loudly on an unclaimed dimension.
- **Probe-backed claims.** Cheap per-call probes (rlimit set/get round-trips to the
  inherited value) plus process-lifetime-cached empirical probes for the
  heavyweight mechanisms (RLIMIT_AS enforcement, Seatbelt network/write
  enforcement) — bounded sacrificial children, loopback/ephemeral resources only,
  fail-closed on any probe error ("probe did not complete … treated as
  unavailable"). No enforcement mechanism is ever dry-run inside `run()`'s worker
  path.
- **Two-terminal result**: `ENFORCE | REFUSE`; REFUSE enumerates *every*
  requested-but-unavailable `(dimension, missing_mechanism, caveat)`; deterministic
  and re-runnable; monotone by construction (proven by the property test).
- **Registry injectability** for tests (crippled registries, stubbed-absent probes);
  a probe error refuses naming the dimension — never a pass-through.

### 1.3 Execution machinery (the only execution path)

- **Shell-free invocation**: explicit argv lists; `Popen(shell=False)` by
  construction.
- **Exact PATH/executable binding**: the *kernel* resolves argv[0] — bare names
  resolve against the allowlisted PATH only; explicit paths bind to
  `os.path.realpath` (symlink residue eliminated); the child's environment PATH is
  never consulted for binding.
- **Executable-hash double check**: when the profile pins
  `(executable, sha256)` pairs, the resolved file must be pinned and its digest
  must match **pre-fork** (fast refusal, no child ever created) *and* is re-checked
  **inside the pre-exec hook** (the enforcement — mismatch aborts before exec via
  a sentinel exit, reported as `ENFORCEMENT_FAILURE` naming path + observed/expected
  digests). No path substitution, no alternate-path fallback.
- **Ordered pre-exec plan**: `setpgrp` (dedicated group, self-verified), rlimits
  (soft=hard=cap, set/get round-trip self-verified, abort-before-exec on failure),
  then the hash recheck. Children inherit every boundary.
- **Wallclock deadline + teardown ladder**: supervisor deadline; on expiry (and
  after normal completion) the *whole group* is killed (`killpg` SIGKILL), reaped,
  and **confirm-empty** (ESRCH on a `killpg(pgid, 0)` probe, grace-bounded loop) —
  a `COMPLETION` fact is emitted only after group-confirmed-empty; cleanup errors
  are `CLEANUP_ERROR` facts, never swallowed.
- **Capped reader**: bounded per-stream capture; at the cap the stream is probed
  once for clean EOF, else severed (writer sees EPIPE) with a `TRUNCATION` fact
  (observed bytes vs cap, which stream). No unbounded buffering.
- **Conservative reporting** (`kernel/sandbox.FactKind`/`RunFact`, new):
  REFUSAL / CAP_FIRED / TRUNCATION / CLEANUP_ERROR / ENFORCEMENT_FAILURE /
  COMPLETION — mechanism-observed facts only (SIGXCPU, SIGXFSZ, errno classes,
  digests, byte counts, ESRCH). Worker-emitted text is opaque payload, never
  parsed, never laundered into a fact. `SandboxResult` gained defaulted
  `stderr`/`facts` fields — backward compatible with the legacy court seam
  (`run_sandboxed`/`sandbox_runner` are untouched and their tests stay green).

### 1.4 darwin Seatbelt backend

`SeatbeltSandboxBackend` (exact-path `/usr/bin/sandbox-exec`) with a **generated
deny-default profile**: `network*` denied when forbidden (explicitly re-allowed when
the profile leaves it unbounded by choice), writes confined to the resolved
workspace subpath (re-allowed globally when unrequested), `process-exec` restricted
to the pinned executable paths when hashes are pinned, plus the minimal
read/fork/mach/signal/sysctl allows. Its claims are earned only by an empirical
cached probe: a sacrificial child under the generated profile must observe loopback
connect **EPERM** (not ECONNREFUSED) and out-of-workspace write **EPERM**.
`/usr/bin/sandbox-exec` is bound by exact absolute path; profile literals use
resolved real paths (macOS `/var` → `/private/var` residue).

## 2. Probe results on this host (darwin, Apple Silicon) — probes, not recall

| Dimension | Mechanism | Probed result on this host | Claim |
|---|---|---|---|
| CPU | `rlimit_cpu` | round-trip verified; sacrificial busy-loop killed by SIGXCPU (−24) at the hard cap | CLAIM |
| MEMORY | `rlimit_as` | **setrlimit of a constraining value is rejected** (`ValueError: current limit exceeds maximum limit`); the empirical probe refuses | **REFUSE** (strong form) |
| OPEN_FILES | `rlimit_nofile` | round-trip verified; sacrificial `open` loop fails with EMFILE (24) at the cap; ceiling guard refuses soft > inherited hard | CLAIM |
| FILE_SIZE | `rlimit_fsize` | round-trip verified; write past the cap fails at OS level (EFBIG) | CLAIM |
| DISK | `aggregate_disk_quota` | no portable aggregate-quota primitive exists | **REFUSE** |
| PROCESS_COUNT | `rlimit_nproc` | round-trip works but NPROC applies **per real-uid** — not a per-worker boundary | **REFUSE** (caveated) |
| NETWORK (forbidden) | `sandbox_exec_net` | loopback connect under the generated deny-network profile: EPERM (1) vs control ECONNREFUSED (61) | CLAIM (seatbelt only) |
| EXECUTABLE_HASH | `exec_double_check` | pre-fork + pre-exec recheck available (U9: no `fexecve` reachable from Python stdlib — residual window named) | CLAIM |
| WORKSPACE_WRITE | `sandbox_exec_file_write` | out-of-workspace write under the generated profile: EPERM; inside-workspace write succeeds | CLAIM (seatbelt only) |
| WALLCLOCK_GROUP | `process_group_deadline` | `setpgrp`/`killpg` POSIX-universal | CLAIM |
| OUTPUT_SIZE | `capped_reader` | bounded in-process reader with severing | CLAIM |

The strong-form refusals (MEMORY, DISK, PROCESS_COUNT on this host; portable
NETWORK/WORKSPACE_WRITE) are **expected outcomes, not workarounds** — they are what
fail-closed means when the primitive cannot enforce the requested boundary.

## 3. Evidence (re-runnable)

Focus gate (the plan's Task 5 command, adapted to this workspace's interpreter):

```
/Users/bob/GitHub/paeos/.venv/bin/python -m pytest -q \
  tests/kernel/test_sandbox.py tests/kernel/test_sandbox_confinement.py
# 33 passed
```

`ruff check` on the four touched files: all checks passed. The suite contains the
14-row discriminative matrix (rows 1–12 as real adversarial subprocesses; rows
13–14 as fast negotiation rows), per-row authoring-time negation evidence
(negation toggles live only in test code: overridden `_make_preexec`,
`_teardown_group`, monkeypatched `_sha256_file`, crippled registries), plus
structural rows: taxonomy⇔registry bijection, monotonicity property, refusal
honesty (injected probe errors refuse, never pass through), caveat visibility
(per-uid NPROC; seatbelt deprecation).

Pre-existing workspace truncation, unchanged by this work: this session workspace
has no `runtime/` package, no `cli`, and no git repository, so `tests/runtime/*`
collection errors and `tests/test_smoke.py::test_skeleton_imports` failures
pre-date the candidate (verified: the only other consumer of `kernel.sandbox`,
`tests/runtime/test_architectural_assurance.py`, passes 8/8).

## 4. Divergence log (plan governs; every divergence recorded)

1. **U3 (open-file/file-size distinct)** — implemented as distinct dimensions with
   distinct mechanisms, per the chain; the plan's Task 5 interface keeps the
   distinct fields, no divergence.
2. **U5 (PROCESS_COUNT)** — plan: "Apply RLIMIT_NPROC where supported". Ruling
   recorded: RLIMIT_NPROC is per-real-uid on every host we can verify (probed
   round-trip; per-uid semantics), so it cannot enforce a *per-worker* count;
   fail-closed refusal with the per-uid caveat. Setting it would also risk
   breaking the whole test session's uid.
3. **U6 (disk primitive)** — plan: broker quota monitor kills the group on
   aggregate overrun. Ruling: a quota *monitor* is not an OS-enforcement primitive
   and this session must not touch the broker; fail-closed refusal naming
   `(DISK, aggregate_disk_quota)`; FSIZE-as-disk and polling are rejected weaker
   substitutes (test-enforced).
4. **U7 (hash algorithm/field)** — `allowed_exec_hashes` entries are
   `(executable, sha256-hex)`; the executable may be bare (kernel-resolved against
   the allowlisted PATH) or absolute (realpath-bound). sha256 chosen: stdlib,
   offline.
5. **U8/U10 (network primitive)** — plan mandates the pinned, hash-verified
   `/usr/bin/sandbox-exec` deny-default backend on macOS: implemented via the
   `SeatbeltSandboxBackend`, exact-path bound. The *digest pinning of the
   sandbox-exec binary itself* has no offline reference digest; the binding is
   exact-path + X_OK and the pin hook is explicit (`sandbox_exec` constructor
   argument). Recorded as a residual, not silently skipped.
6. **U9 (fexecve)** — probed: not reachable from the Python standard library; the
   pre-fork + pre-exec double check stands with the residual window named in the
   claim caveat (AR-2).
7. **U12 / plan Task 5 interface** — the plan's frozen `SandboxProfile` has 9
   fields; the remediation objective requires workspace-write and output-size
   requirements to be *expressible* so the backend can answer unsupported for
   them. Added `workspace_root: str | None = None` and `output_bytes: int = 0`
   (absent ⇒ unrequested — never an invented default). `SandboxResult` gained
   defaulted `stderr`/`facts`. Both extensions are backward compatible; recorded.
8. **C-F5 (run() precondition)** — `run()` re-negotiates internally and raises the
   typed `SandboxProfileUnavailable` on REFUSE (fail-closed
   negotiate-and-refuse); an un-negotiated call is a typed stop, never a weaker run.
9. **H5 vs H18 (probe spawning)** — the chain forbids probes spawning processes
   from `supports()` *and* requires observable enforcement for MEMORY/NETWORK.
   Resolution: cheap probes are per-call and side-effect-free; the empirical
   MEMORY/Seatbelt probes are bounded sacrificial children **cached per process
   lifetime** (the chain's own NETWORK-row pattern), outside the worker execution
   path, fail-closed on error.
10. **Deny-default profile scope** — the plan's generated profile is deny-default;
    implemented as deny-default with every *unrequested* boundary class explicitly
    re-allowed (`(allow network*)`, `(allow file-write*)`), so
    unbounded-by-explicit-choice stays exactly that. Exec-path restriction applies
    when hashes are pinned (tested: pinned child cannot exec `/bin/echo`).
11. **`setsid`** — Python exposes `os.setpgrp` (not `setsid`); the dedicated group
    is created via `setpgrp` in the pre-exec hook and self-verified
    (`getpgrp() == getpid()`, abort-before-exec otherwise).
12. **Sentinel exit codes** — pre-exec aborts use sentinel exits 96/97/98 (documented
    range); a worker legitimately exiting with such a code is reported as an
    enforcement failure (conservative direction) — fail-closed by design.
13. **Isolated branch** — this session workspace is **not a git repository**
    (verified `git status` fails: "not a git repository"), so no branch could be
    created; no git operations of any kind were performed (none are permitted);
    the working tree of this session-scoped workspace *is* the isolated candidate.
    `backlog/research/` does not exist in this workspace and was not consulted.

## 5. Acceptances / residual risks

- **AR-1 (CPU honest minimum)**: CPU claim earned by round-trip; enforcement
  behavior proven by the real SIGXCPU row.
- **AR-2 (TOCTOU residual)**: pre-fork + pre-exec double check narrows the window;
  named in the claim caveat; fexecve upgrade unavailable (U9 probe).
- **AR-4 (threads)**: the seam is **thread-free** — a selector loop supervises the
  deadline and both streams; no threads are spawned by the backend. The pre-exec
  hook does minimal work (rlimit round-trips + one file hash read); the exec
  trampoline remains the named structural upgrade.
- **AR-6 (strong-form refusals)**: MEMORY/DISK/PROCESS_COUNT refusals on darwin
  are passes, not workarounds (row 5/8 tests).
- **AR-7 (probe-verify or refuse)**: every [KNOWLEDGE] platform caveat was probed
  live before this report (section 2 records the results).
- **C-F7 (setsid escape)**: an adversarial grandchild that calls `setsid()` itself
  escapes the group; the report facts remain group-scoped (never claim
  tree-wide), and the confirm-empty loop verifies the *group* is empty. Accepted
  residual, named here.
- **No production execution routing / lifecycle authority**: no runtime,
  lifecycle, router, governance, or SAKG file was touched; the seam contains no
  route/promote/dispatch vocabulary (grep-verified); nothing here selects or runs
  production work — callers negotiate explicitly.
- **No internet, credentials, browser, clipboard, AppleScript, git operations,
  merge, push, or promotion** occurred in this session; all network fixtures are
  loopback-only.

## 6. Recovery verification and candidate binding

The original worker workspace was removed after the fail-closed budget stop. The
four allowed source/test files were reconstructed from the preserved successful
editor transcript, then independently reviewed and corrected for a transcript
replay artifact (a duplicated `__all__` tail), static typing, and lint quality.
The resulting candidate is committed locally as
`f0b134d509f6e09e2c45a07af25226a4146e09b9` on the isolated recovery branch. No
governance, runtime, router, or production-dispatch files were included in that
commit.

Recovery verification from the candidate worktree:

```
focused Gate E tests: 33 passed (exit 0)
full non-gateway suite: 1,140 passed (exit 0)
Ruff (four changed files): all checks passed
Pyright (four changed files): 0 errors, 0 warnings, 0 informations
git diff --check: clean
```

Host-level permission was required for the focused and full runs because the
Seatbelt/loopback rows are intentionally OS-discriminative. These results remain
implementation evidence only; they do not constitute L13/L14/L17 or a Gate E
Court seal. The worker orchestration itself halted with `source-exhausted` after
the recorded budget breach, and that failure remains preserved separately.


