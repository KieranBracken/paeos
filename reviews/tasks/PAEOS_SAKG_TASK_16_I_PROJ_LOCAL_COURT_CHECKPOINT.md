# SAKG Task 16 [I-PROJ] — Local SoftLoop/Court Checkpoint

**Status:** `SUPERSEDED_LOCAL_HOLD` (see the qualified physical checkpoint)

## Candidate and source binding

- Recovery branch: `codex/control-plane-recovery-s1-clean-recovered`
- Candidate commit: `2cedea82da2d775a878055a6d8eb3dd05c929883`
- Evidence bundle: `/private/tmp/paeos-sakg-task-16-l14-l17-bundle-2cedea8.json`
- Evidence bundle SHA-256: `227e5f2e6528e16c70b92e86734c2ea187864da2c9019201ee5edc16e057e117`
- Audit prompt: `/private/tmp/paeos-sakg-task-16-l14-l17-prompt-2cedea8.md`
- Audit prompt SHA-256: `bf03d1e9c67a278f3897fae8ed413c1ba7e7c093a27f30fb6d536b32c8d299bc`

The bundle contains the actual repository bytes for `sakg/project.py`, the present projection
tests, and the projection schema. It does not substitute synthetic files for repository files.

## Hermetic execution evidence

- SoftLoop state root: `/private/tmp/paeos-iproj-actual-run-008`
- Run ID: `i-proj-trace-a-actual-008`
- Goal ID: `g-777f4d38a191`
- Red phase: exit `2` (`ModuleNotFoundError: sakg.project`, expected before implementation)
- Court evidence phase: exit `0`, 15 projection tests passed
- Local SoftLoop status: `SEALED`
- Local seal hash: `2645db5e6e23b1f76726a555ef5ee9d44a4835d7b12a7328c37eeb6054ce1a5b`
- Local artifact bundle: `31f658d7c00169139c87d4a3ef4f509845a19e635b3dec0df89878b755a03bb2`
- Local verdict reference: `5bc8d2b8d3bd0fcb7233390b942ce4508d3ef0fa46d0ff98477f8f2e9a2bc977`
- Local adversary reference: `db9ab3d16d3de1b175f1b54aad56bd081aa8bdd8d0c6dcc8bcdd6ca124d794d8`
- Local ledger head: `6fb6b833b6bffd716677621af520f856e725660f0fb608f3f39daafd3de315dc`

## Repository verification

- Projection tests: `15 passed`, exit `0`
- `pyright sakg/`: `0 errors, 0 warnings, 0 informations`, exit `0`
- `ruff check sakg/ tests/sakg/`: all checks passed, exit `0`

## Integrity hold

The canonical intake names `tests/sakg/test_projection.py`, but that file is absent at the
candidate. The repository contains `tests/sakg/test_sakg_projection.py` as the functional
equivalent. This filename drift is explicitly carried in the bundle and must be considered by
the physical auditor; it is not silently normalized. The local scripted runtime cannot establish
Builder != Auditor, so A-08 remains `UNPROVEN` until a qualified Gemini 3.7 physical receipt is
captured. No milestone increment or Gate/Court seal is claimed by this checkpoint.

## Authorized physical dispatch outcome

The one authorized Gemini 3.6 command (`l14-l17-sakg-task16-2cedea8-gemini36-001`, max tokens
4096, no fallback/retry) exited `2` with `AUDITOR_RECEIPT_FAILED:OperationalError`. No provider
receipt or report was created; the requested report and receipt paths remain absent. A read-only
router-state query also could not open the local SQLite database (`unable to open database file
(14)`), indicating a local control-plane storage failure before provider adjudication. The
identical command is not retried. Physical A-08 remains `NOT QUALIFIED` and strict progress
remains 21/48.

This local-only checkpoint is superseded by
`reviews/tasks/PAEOS_SAKG_TASK_16_I_PROJ_PHYSICAL_L14_L17_CHECKPOINT.md`, which records the
qualified Gemini 3.7 physical pair and Court seal. The earlier OperationalError remains preserved
as historical evidence.
