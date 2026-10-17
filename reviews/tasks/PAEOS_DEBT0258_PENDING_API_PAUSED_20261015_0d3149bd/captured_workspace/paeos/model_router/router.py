"""
PAEOS Model Router — Single Policy Authority Autonomous Router
"""
from __future__ import annotations

import random
import time
from dataclasses import replace

from paeos.model_router.aimd import AIMDController
from paeos.model_router.auditor_receipt import response_fingerprint
from paeos.model_router.catalog import ModelCatalog
from paeos.model_router.credentials import CredentialStore
from paeos.model_router.policy import RoutingPolicyEngine
from paeos.model_router.quota_tracker import (
    EconomyOfReasoningGovernor,
    QuotaTracker,
    RecommendedQuotaAction,
)
from paeos.model_router.state import RouterStateDB
from paeos.model_router.transport import LiteLLMTransport
from paeos.model_router.types import (
    DataClass,
    FailureScope,
    LogicalModel,
    ModelCatalogEntry,
    ModelFamily,
    NormalizedError,
    NormalizedErrorType,
    ProviderHealth,
    RetryPolicy,
    RouterResponse,
    TaskClass,
    TaskRequest,
)


class ModelRouter:
    def __init__(
        self,
        credentials: CredentialStore | None = None,
        catalog: ModelCatalog | None = None,
        state_db: RouterStateDB | None = None,
        transport: LiteLLMTransport | None = None,
    ):
        self.credentials = credentials or CredentialStore()
        self.catalog = catalog or ModelCatalog()
        self.state_db = state_db or RouterStateDB()
        self.aimd = AIMDController(self.state_db)
        self.policy = RoutingPolicyEngine(self.catalog, self.state_db, self.credentials, self.aimd)
        self.transport = transport or LiteLLMTransport(self.credentials, self.catalog)
        self.quota_tracker = QuotaTracker()
        self.reasoning_governor = EconomyOfReasoningGovernor()

    def route(self, request: TaskRequest) -> RouterResponse:
        """
        Main routing entry point.
        Executes the candidate chain with deterministic fallback and single-retry policy.
        """
        # Economy of reasoning tier evaluation (SCO-035)
        task_crit = (
            request.task_class.value
            if hasattr(request.task_class, "value")
            else str(request.task_class)
        )
        _reasoning_tier = self.reasoning_governor.select_model_tier(task_crit)

        candidates = self.policy.resolve_candidate_chain(request)
        if not candidates:
            raise NormalizedError(
                error_type=NormalizedErrorType.MODEL_UNAVAILABLE,
                message="No eligible models available matching task constraints, privacy rules, and provider health",
            )
        if not request.allow_fallback:
            candidates = candidates[:1]

        attempted_chain: list[str] = []
        last_error: NormalizedError | None = None

        for candidate in candidates:
            attempted_chain.append(f"{candidate.provider_id.value}:{candidate.model_id}")

            # Predictive quota velocity evaluation (SCO-033, SCO-034)
            quota_status = self.quota_tracker.evaluate_quota(
                provider_id=candidate.provider_id.value,
                model_id=candidate.model_id,
                estimated_tokens=request.max_tokens or 1000,
            )
            if quota_status.recommended_action == RecommendedQuotaAction.CHECKPOINT_AND_SUSPEND:
                continue

            admitted, _reason = self.aimd.check_admission(
                candidate.provider_id,
                model_id=candidate.model_id,
            )
            if not admitted:
                continue

            if not self.state_db.acquire_slot(candidate.provider_id):
                continue

            try:
                resp = self._dispatch_with_single_retry(candidate, request)
                resp.fallback_chain = attempted_chain
                if not resp.host_turn_uuid:
                    resp.host_turn_uuid = (
                        request.metadata.get("host_turn_uuid")
                        or request.metadata.get("turn_id")
                        or getattr(request, "host_turn_uuid", None)
                    )
                if not resp.external_generation_id:
                    gen_id = None
                    if hasattr(resp.raw_response, "id"):
                        gen_id = getattr(resp.raw_response, "id")
                    elif isinstance(resp.raw_response, dict):
                        gen_id = resp.raw_response.get("id")
                    resp.external_generation_id = str(gen_id) if gen_id else None
                # Record token usage in quota tracker (SCO-033)
                tokens_used = resp.total_tokens if resp.total_tokens else (request.max_tokens or 1000)
                self.quota_tracker.record_usage(
                    provider_id=candidate.provider_id.value,
                    model_id=candidate.model_id,
                    tokens=tokens_used,
                )
                # The router adds the definitive attempted-candidate chain after transport
                # returns; refresh the content-free response fingerprint before exposing it.
                resp.transport_response_sha256 = response_fingerprint(resp)
                return resp
            except NormalizedError as err:
                err = self._bind_error_to_candidate(candidate, err)
                last_error = err
                self._handle_dispatch_error(candidate, err)
            finally:
                self.state_db.release_slot(candidate.provider_id)

        raise last_error or NormalizedError(
            error_type=NormalizedErrorType.PROVIDER_UNAVAILABLE,
            message=f"All candidate routes exhausted: {', '.join(attempted_chain)}",
        )

    def _dispatch_with_single_retry(
        self,
        candidate: ModelCatalogEntry,
        request: TaskRequest,
    ) -> RouterResponse:
        """
        Dispatches request with single-retry with jitter on 429/transient timeout.
        """
        try:
            resp = self.transport.dispatch(candidate, request)
            self.state_db.record_usage(candidate.provider_id, resp.prompt_tokens, resp.completion_tokens)
            self.state_db.log_observation(
                task_class=request.task_class.value,
                logical_model=request.logical_model.value if request.logical_model else None,
                model_id=candidate.model_id,
                provider_id=candidate.provider_id,
                family=candidate.family,
                latency_ms=resp.latency_ms,
                prompt_tokens=resp.prompt_tokens,
                completion_tokens=resp.completion_tokens,
                success=True,
            )
            self.aimd.on_success(candidate.provider_id, resp.latency_ms)
            return resp

        except NormalizedError as e:
            if e.error_type == NormalizedErrorType.RATE_LIMITED:
                self.aimd.on_rate_limit(candidate.provider_id, e)
                # If short retry-after (< 3s), perform ONE bounded retry with jitter
                if (
                    request.retry_policy is RetryPolicy.SINGLE_RATE_LIMIT
                    and e.retry_after
                    and e.retry_after <= 3.0
                ):
                    time.sleep(e.retry_after + random.uniform(0.1, 0.5))
                    try:
                        resp = self.transport.dispatch(candidate, request)
                        # Explicitly clear cooldown and restore HEALTHY on retry success
                        self.state_db.set_health(candidate.provider_id, ProviderHealth.HEALTHY)
                        self.state_db.record_usage(candidate.provider_id, resp.prompt_tokens, resp.completion_tokens)
                        self.state_db.log_observation(
                            task_class=request.task_class.value,
                            logical_model=request.logical_model.value if request.logical_model else None,
                            model_id=candidate.model_id,
                            provider_id=candidate.provider_id,
                            family=candidate.family,
                            latency_ms=resp.latency_ms,
                            prompt_tokens=resp.prompt_tokens,
                            completion_tokens=resp.completion_tokens,
                            success=True,
                        )
                        self.aimd.on_success(candidate.provider_id, resp.latency_ms)
                        resp.attempts = 2
                        return resp
                    except NormalizedError as retry_err:
                        if retry_err.error_type == NormalizedErrorType.RATE_LIMITED:
                            self.aimd.on_rate_limit(candidate.provider_id, retry_err)
                        else:
                            self.aimd.on_error(candidate.provider_id, retry_err)
                        raise retry_err from e

            # Non-retryable error
            raise e

    def _handle_dispatch_error(self, candidate: ModelCatalogEntry, error: NormalizedError) -> None:
        self.state_db.log_observation(
            task_class="UNKNOWN",
            logical_model=None,
            model_id=candidate.model_id,
            provider_id=candidate.provider_id,
            family=candidate.family,
            latency_ms=0.0,
            prompt_tokens=0,
            completion_tokens=0,
            success=False,
            normalized_error=error.error_type.value,
            failure_scope=error.failure_scope,
            scope_key=error.scope_key,
        )
        if error.error_type == NormalizedErrorType.RATE_LIMITED:
            self.aimd.on_rate_limit(candidate.provider_id, error)
        else:
            self.aimd.on_error(candidate.provider_id, error)

    @staticmethod
    def _bind_error_to_candidate(
        candidate: ModelCatalogEntry,
        error: NormalizedError,
    ) -> NormalizedError:
        """Prevent a transport from applying scoped health to another candidate."""

        if (
            error.failure_scope in (FailureScope.MODEL, FailureScope.ENTITLEMENT)
            and error.scope_key != candidate.model_id
        ):
            return replace(
                error,
                provider_id=candidate.provider_id,
                model_id=candidate.model_id,
                failure_scope=FailureScope.PROVIDER,
                scope_key=None,
            )
        return replace(
            error,
            provider_id=candidate.provider_id,
            model_id=candidate.model_id,
        )

    def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        task_class: TaskClass = TaskClass.ROUTINE,
        data_class: DataClass = DataClass.INTERNAL,
        logical_model: LogicalModel | None = None,
        builder_family: ModelFamily | None = None,
        max_tokens: int | None = None,
        temperature: float = 0.7,
    ) -> RouterResponse:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        req = TaskRequest(
            messages=messages,
            task_class=task_class,
            data_class=data_class,
            logical_model=logical_model or LogicalModel.PAEOS_AUTO,
            builder_family=builder_family,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        return self.route(req)
