# NVIDIA 410 baseline discrimination

Read-only repository analysis; offline reproduction uses current real package imports, no substituted production classes, and three explicitly located temporary SQLite files. Python command and output are saved in command.txt, stdout.txt, stderr.txt and result.json. Script: reproduce.py. Successful execution exit code: 0. Actual imported package paths and SHA-256 values are in result.json; preimage hashes are source-pins.json. All preimage hashes were rechecked unchanged after reproduction.

Saved source: /private/tmp/paeos-debt0249-run-7df8fadd781147ffb563e97caa80b814/L07_ADVERSARY.receipt.json. This receipt preserves the exception message, not original HTTP response bytes. redacted-response.json retains only public error status/body/message and source receipt hash, omitting task/prompt/request envelope fields. The body is the saved NVIDIA problem-details shape: type about:blank, title Gone, status410, and detail that meta/llama-3.1-8b-instruct reached end of life and is no longer available.

Observed:
1. normalize_error returns UNKNOWN/PROVIDER/no scope key for the dict, JSON string, and exact saved exception string.
2. AIMDController.on_error on this actual UNKNOWN changes no health; failed model and sibling remain admitted after reopening.
3. Supplying MODEL_UNAVAILABLE with FailureScope.MODEL and the exact failed-model scope key independently also changes no health; both remain admitted.
4. Direct use of the existing RouterStateDB.set_scoped_health MODEL/UNAVAILABLE primitive excludes only the failed model. Provider and sibling remain HEALTHY; the exclusion survives reopening. The sibling identifier is an offline health-isolation control, not evidence that another catalog model is currently qualified or available.

Root causes and source references:
- paeos/model_router/errors.py:210-220 recognizes 404/model-not-found/does-not-exist but not this exact 410 retirement wording. Fallback UNKNOWN is at270-278.
- paeos/model_router/aimd.py:163-184 has AUTH_FAILED, QUOTA_EXHAUSTED and PROVIDER_UNAVAILABLE cases, but no MODEL_UNAVAILABLE branch.
- aimd.py:91-98 already rejects scoped UNAVAILABLE; state.py:192-253 already stores and reads model-scoped health.
- provider_transports.py:288-313 forwards exception.message as text with trusted candidate provider/model; router.py:205-247 records, dispatches to AIMD, and rebinds scoped errors to the selected candidate. Preserve this binding and the existing provider-wide quarantine/cooldown behavior.

Smallest proposed mutable repair closure (requires separate protected maintenance authority):
- paeos/model_router/errors.py
- paeos/model_router/aimd.py
- tests/model_router/test_model_retirement.py (new focused regression module)

Read-only implementation dependencies: state.py, types.py, providers.py, provider_transports.py and router.py. No state schema or type change is justified by this baseline. Existing targeted regression suites: tests/model_router/test_error_normalization.py, test_state_and_aimd.py, test_free_worker_pool_fallback.py, test_provider_transports.py. Extend scope only for a demonstrated integration failure, not preemptively.

Required future discriminators: exact saved wrapper+JSON/dict410 -> model retirement; unknown/provider-wide410 must not be mislabeled; missing/mismatched candidate identity must not poison another model; explicit MODEL_UNAVAILABLE affects only the bound model; sibling and provider health unchanged; reopen persists exclusion; pre-existing provider-wide AUTH/QUOTA/outage protections still dominate. No provider probe is necessary for these regressions.

Execution controls: bytecode disabled; network, DNS and child-process audit guards; writes and SQLite connections restricted to the new evidence directory. First attempt stopped before reproduction because an import tried the default temporary-directory write probe outside that directory; its command/stdout/stderr are preserved as attempt1-*. The successful command supplies a temporary TMPDIR and a copied existing public tokenizer cache whose known SHA is recorded in import-cache.json. A dependency attempted socket.getaddrinfo during import; audit blocked it before resolution/connection. No provider dispatch, subprocess or outbound connection was executed. Default production RouterStateDB was never instantiated.

No source repair, PAEOS runner, lifecycle advancement, role qualification, or debt closure is claimed. errors.py/aimd.py/state.py belong to the protected manifest and are outside the current DEBT-0249 Builder scope.
