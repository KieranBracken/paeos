# Builder bootstrap security remediation checkpoint

**Status:** implementation and focused verification complete; fresh read-only Security Review pending. This is a recovery checkpoint, not a release, Court adjudication, or qualification.

## Preserved review record

The original Security Review examined `fdf7b29e5a4ec19513d05c4c55775dcc084477fa` against `codex/pre-p3-clean-recovery-20261017`. Its three findings remain exactly as recorded in `reviews/tasks/PAEOS_BUILDER_ROOT_BINDING_20261017/security-review.json` (SHA-256 `6235d412d625b0e4bf4194d7ad21c9b43245bb2c85d960f752e2ec1ba7e5064b`). That file and its companion report were not edited. This checkpoint records remediation evidence separately and does not change the original findings or disposition.

## Changes and evidence

- **P1 — bundle startup:** the bundle now contains the 13-file local import closure identified by the static AST walk. The checked modules contained no dynamic-import or package-resource loading patterns. A subprocess test runs the actual supervisor with only the temporary bundle on `PYTHONPATH`, verifies a signed identity, confirms the process stays alive, and proves a missing `kernel/types.py` causes import failure. The test uses an empty temporary queue and makes no provider request.
- **P2 — source containment:** source files are opened relative to the selected source root through directory descriptors with `O_NOFOLLOW`; symlinked ancestors and final-file links fail closed. A temporary outside-root sentinel remains unchanged when an ancestor symlink is rejected.
- **P2 — runtime containment:** derived runtime paths are checked for symlinked components, and request/public-key reads and creates use no-follow descriptor traversal. Existing request-key identity is preserved. The expected final `.venv/bin/python3` symlink is allowed only when its target is a regular executable; its parent directories still must be real directories. Tests cover symlinked runtime ancestors, final key links, and worker queue/workspace links.

The installer API remains backward compatible: omitted roots still bind source and runtime to the repository root; explicit `source_root` and `runtime_root` remain separate. The main checkout, its untracked bootstrap files, host keys, LaunchAgent, running supervisor, and queue were not modified by this code/test checkpoint.

## Verification

- Installer and trusted transport/readiness/client tests: **53 passed**.
- Ruff lint and format checks: passed.
- Python compile and `git diff --check`: passed.
- The post-generation secret scan covered 29 UTF-8 files in the branch diff and remediation package, including the final manifest and scan receipt; zero patterns matched.
- The single `uv run pytest` attempt failed during collection with **22 import errors**, including missing `contracts.adapters`, `runtime.autonomy.authority`, `runtime.candidate_materialization`, and `runtime.court.completeness_firewall`. One collected test, `tests/runtime/test_builder_transport_gate.py`, was pre-existing and untracked in this worktree; it was not changed or included in the checkpoint. No second full-suite attempt was made.

The original findings JSON hash was checked before and after implementation. A fresh read-only Security Review of the final code diff against `codex/pre-p3-clean-recovery-20261017` is the next gate. Host installation and the one authorized fresh-ID `gpt-5.6-sol` qualification request remain held until that review is clean and the queue/process/identity/hash preflight passes. No provider call, qualification request, PAEOS admission, receiver start, Court adjudication, or P3 promotion occurred in this checkpoint.
