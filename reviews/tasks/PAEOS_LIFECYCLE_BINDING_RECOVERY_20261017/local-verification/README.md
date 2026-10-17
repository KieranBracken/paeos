# Lifecycle-binding recovery evidence

This directory preserves exact local test receipts and the observed lifecycle gap. The PAEOS source-construction run in the adjacent free-pool task completed 12 provider-free tests and received one physical Court observation, while its initialization reported `worker_dispatches: 0`. That is not proof a separate receiver started.

The 17 focused lifecycle tests passed against recovery commit `5b1088a466dccdb8fe3799eb2e0df1d79d07d04e` with six byte-pinned, untracked import-support modules overlaid in the worktree; see the receipt for all source and support hashes. The 37 transport tests passed in the active dirty checkout, but four test files were untracked and are not included here. These are test results, not Court adjudication or qualification.

`binding-gap.json` identifies the concrete code path and the owner’s exact wake condition.
