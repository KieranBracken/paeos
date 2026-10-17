"""
Adversarial Unit Tests: Routing Policy Engine & Heterogeneous Audit
"""
from pathlib import Path

import pytest
from paeos.model_router.catalog import ModelCatalog
from paeos.model_router.credentials import CredentialStore
from paeos.model_router.router import ModelRouter
from paeos.model_router.state import RouterStateDB
from paeos.model_router.transport import LiteLLMTransport
from paeos.model_router.types import (
    DataClass,
    LogicalModel,
    ModelFamily,
    NormalizedError,
    NormalizedErrorType,
    ProviderHealth,
    ProviderId,
    RetryPolicy,
    RouterResponse,
    TaskClass,
    TaskRequest,
)


class MockTransport(LiteLLMTransport):
    def __init__(self, credentials: CredentialStore):
        super().__init__(credentials)
        self.responses = {}
        self.call_history = []
        self.attempt_counts = {}

    def dispatch(self, model_entry, request, timeout=30.0):
        key = (model_entry.provider_id, model_entry.model_id)
        self.call_history.append(key)
        self.attempt_counts[key] = self.attempt_counts.get(key, 0) + 1

        if key in self.responses:
            action = self.responses[key]
            if isinstance(action, list):
                attempt_idx = min(self.attempt_counts[key] - 1, len(action) - 1)
                curr_act = action[attempt_idx]
                if isinstance(curr_act, Exception):
                    raise curr_act
                return curr_act
            elif isinstance(action, Exception):
                raise action
            return action

        return RouterResponse(
            content=f"Mock response from {model_entry.model_id}",
            model_id=model_entry.model_id,
            provider_id=model_entry.provider_id,
            family=model_entry.family,
            prompt_tokens=50,
            completion_tokens=25,
            total_tokens=75,
            latency_ms=45.0,
        )


@pytest.fixture
def mock_router(tmp_path: Path):
    db_file = tmp_path / "test_state.sqlite3"
    state_db = RouterStateDB(db_file)
    catalog = ModelCatalog()

    creds = CredentialStore(tmp_path / "mock.env")
    creds._keys = {
        "GEMINI_API_KEY": "mock-gemini-key",
        "CLINE_API_KEY": "mock-cline-key",
        "NVIDIA_API_KEY": "mock-nvidia-key",
        "KILO_API_KEY": "mock-kilo-key",
        "OPENROUTER_API_KEY": "mock-openrouter-key",
    }

    transport = MockTransport(creds)
    router = ModelRouter(
        credentials=creds,
        catalog=catalog,
        state_db=state_db,
        transport=transport,
    )
    return router, transport


def test_logical_model_paeos_strong(mock_router):
    """paeos-strong prefers Gemini 3.7 Flash -> NVIDIA Llama."""
    router, _transport = mock_router
    req = TaskRequest(
        messages=[{"role": "user", "content": "Analyze architecture"}],
        logical_model=LogicalModel.PAEOS_STRONG,
        task_class=TaskClass.ARCHITECTURE,
        data_class=DataClass.PUBLIC,
    )
    resp = router.route(req)
    assert resp.provider_id == ProviderId.GOOGLE
    assert resp.model_id == "gemini-3.6-flash"


def test_task_request_preserves_legacy_positional_metadata() -> None:
    request = TaskRequest(
        [{"role": "user", "content": "legacy"}],
        TaskClass.ROUTINE,
        DataClass.PUBLIC,
        None,
        None,
        None,
        False,
        False,
        None,
        None,
        False,
        None,
        0.1,
        {"legacy": True},
    )

    assert request.metadata == {"legacy": True}
    assert request.retry_policy is RetryPolicy.SINGLE_RATE_LIMIT
    assert request.allow_fallback is True


def test_retired_explicit_physical_model_fails_closed(mock_router):
    """A retired explicit physical model is rejected instead of dispatched."""
    router, _transport = mock_router
    req = TaskRequest(
        messages=[{"role": "user", "content": "Specific task"}],
        explicit_model="meta/llama-3.1-8b-instruct",
        data_class=DataClass.PUBLIC,
    )
    with pytest.raises(NormalizedError) as exc:
        router.route(req)
    assert exc.value.error_type == NormalizedErrorType.MODEL_UNAVAILABLE


def test_availability_gate_fails_closed(mock_router):
    """Requesting an unavailable model strictly fails closed and raises MODEL_UNAVAILABLE."""
    router, _transport = mock_router
    req = TaskRequest(
        messages=[{"role": "user", "content": "Test"}],
        explicit_model="z-ai/glm-5.2",  # available=False
        data_class=DataClass.PUBLIC,
    )
    with pytest.raises(NormalizedError) as exc:
        router.route(req)
    assert exc.value.error_type == NormalizedErrorType.MODEL_UNAVAILABLE


def test_heterogeneous_audit_builder_not_auditor(mock_router):
    """Invariant V: Builder family != Auditor family."""
    router, _transport = mock_router

    # DeepSeek builder -> Gemini or Llama auditor
    req1 = TaskRequest(
        messages=[{"role": "user", "content": "Audit code"}],
        logical_model=LogicalModel.PAEOS_AUDIT,
        builder_family=ModelFamily.DEEPSEEK,
        task_class=TaskClass.AUDIT,
        data_class=DataClass.PUBLIC,
    )
    resp1 = router.route(req1)
    assert resp1.family != ModelFamily.DEEPSEEK
    assert resp1.family in (ModelFamily.GEMINI, ModelFamily.LLAMA, ModelFamily.GLM)

    # Gemini builder -> Llama or DeepSeek auditor
    req2 = TaskRequest(
        messages=[{"role": "user", "content": "Audit code"}],
        logical_model=LogicalModel.PAEOS_AUDIT,
        builder_family=ModelFamily.GEMINI,
        task_class=TaskClass.AUDIT,
        data_class=DataClass.PUBLIC,
    )
    resp2 = router.route(req2)
    assert resp2.family != ModelFamily.GEMINI
    assert resp2.family in (ModelFamily.LLAMA, ModelFamily.GLM, ModelFamily.DEEPSEEK, ModelFamily.MINIMAX, ModelFamily.LAGUNA)


def test_provider_cooldown_and_failover(mock_router):
    """When primary provider returns 429, router marks COOLDOWN and immediately fails over to next candidate."""
    router, transport = mock_router

    transport.responses[(ProviderId.GOOGLE, "gemini-3.6-flash")] = NormalizedError(
        error_type=NormalizedErrorType.RATE_LIMITED,
        message="Too many requests",
        provider_id=ProviderId.GOOGLE,
        model_id="gemini-3.6-flash",
        http_status=429,
        retry_after=30.0,
    )

    req = TaskRequest(
        messages=[{"role": "user", "content": "Refactor"}],
        logical_model=LogicalModel.PAEOS_STRONG,
        data_class=DataClass.PUBLIC,
    )
    resp = router.route(req)

    assert resp.provider_id != ProviderId.GOOGLE
    assert resp.model_id != "meta/llama-3.1-8b-instruct"

    st = router.state_db.get_provider_state(ProviderId.GOOGLE)
    assert st["health_status"] == ProviderHealth.COOLDOWN.value


def test_aimd_retry_success_clears_cooldown(mock_router):
    """When a 429 occurs with short retry-after, a successful second attempt clears COOLDOWN and restores HEALTHY."""
    router, transport = mock_router

    transport.responses[(ProviderId.GOOGLE, "gemini-3.6-flash")] = [
        NormalizedError(
            error_type=NormalizedErrorType.RATE_LIMITED,
            message="Rate limit 429",
            provider_id=ProviderId.GOOGLE,
            model_id="gemini-3.6-flash",
            http_status=429,
            retry_after=0.05,
        ),
        RouterResponse(
            content="Recovered after retry",
            model_id="gemini-3.6-flash",
            provider_id=ProviderId.GOOGLE,
            family=ModelFamily.GEMINI,
            latency_ms=30.0,
        ),
    ]

    req = TaskRequest(
        messages=[{"role": "user", "content": "Test inline retry"}],
        logical_model=LogicalModel.PAEOS_STRONG,
        data_class=DataClass.PUBLIC,
    )
    resp = router.route(req)

    assert resp.content == "Recovered after retry"
    assert resp.attempts == 2

    st = router.state_db.get_provider_state(ProviderId.GOOGLE)
    assert st["health_status"] == ProviderHealth.HEALTHY.value
    assert st["cooldown_until"] is None


def test_aimd_retry_non_429_failure_updates_error(mock_router):
    """When a 429 retry fails with 401 AUTH_FAILED, provider is quarantined, not treated as rate limited."""
    router, transport = mock_router

    transport.responses[(ProviderId.GOOGLE, "gemini-3.6-flash")] = [
        NormalizedError(
            error_type=NormalizedErrorType.RATE_LIMITED,
            message="Rate limit 429",
            provider_id=ProviderId.GOOGLE,
            model_id="gemini-3.6-flash",
            http_status=429,
            retry_after=0.05,
        ),
        NormalizedError(
            error_type=NormalizedErrorType.AUTH_FAILED,
            message="Key revoked on retry",
            provider_id=ProviderId.GOOGLE,
            model_id="gemini-3.6-flash",
            http_status=401,
        ),
    ]

    req = TaskRequest(
        messages=[{"role": "user", "content": "Test failure"}],
        logical_model=LogicalModel.PAEOS_STRONG,
        data_class=DataClass.PUBLIC,
    )
    resp = router.route(req)

    assert resp.provider_id == ProviderId.NVIDIA

    st = router.state_db.get_provider_state(ProviderId.GOOGLE)
    assert st["health_status"] == ProviderHealth.QUARANTINED.value


def test_no_retry_policy_stops_after_first_short_429(mock_router):
    """A one-shot request must not repeat a short-429 provider call."""

    router, transport = mock_router
    google_route = (ProviderId.GOOGLE, "gemini-3.6-flash")
    transport.responses[google_route] = [
        NormalizedError(
            error_type=NormalizedErrorType.RATE_LIMITED,
            message="short 429",
            provider_id=ProviderId.GOOGLE,
            model_id="gemini-3.6-flash",
            http_status=429,
            retry_after=0.05,
        ),
        RouterResponse(
            content="second call must never happen",
            model_id="gemini-3.6-flash",
            provider_id=ProviderId.GOOGLE,
            family=ModelFamily.GEMINI,
        ),
    ]
    request = TaskRequest(
        messages=[{"role": "user", "content": "one shot"}],
        logical_model=LogicalModel.PAEOS_STRONG,
        data_class=DataClass.PUBLIC,
    )
    request.retry_policy = RetryPolicy.NONE
    request.allow_fallback = False

    with pytest.raises(NormalizedError) as captured:
        router.route(request)

    assert captured.value.error_type is NormalizedErrorType.RATE_LIMITED
    assert transport.call_history == [google_route]


def test_no_fallback_stops_after_first_candidate_failure(mock_router):
    """A no-fallback request must not dispatch a second provider."""

    router, transport = mock_router
    google_route = (ProviderId.GOOGLE, "gemini-3.6-flash")
    transport.responses[google_route] = NormalizedError(
        error_type=NormalizedErrorType.RATE_LIMITED,
        message="no fallback",
        provider_id=ProviderId.GOOGLE,
        model_id="gemini-3.6-flash",
        http_status=429,
        retry_after=30.0,
    )
    request = TaskRequest(
        messages=[{"role": "user", "content": "one route"}],
        logical_model=LogicalModel.PAEOS_STRONG,
        data_class=DataClass.PUBLIC,
    )
    request.allow_fallback = False

    with pytest.raises(NormalizedError) as captured:
        router.route(request)

    assert captured.value.error_type is NormalizedErrorType.RATE_LIMITED
    assert transport.call_history == [google_route]
