"""
PAEOS Model Router — Single Policy Authority Autonomous Router
"""
from __future__ import annotations

import random
import time
from typing import Any, Dict, List, Optional

from paeos.model_router.aimd import AIMDController
from paeos.model_router.catalog import ModelCatalog
from paeos.model_router.credentials import CredentialStore
from paeos.model_router.policy import RoutingPolicyEngine
from paeos.model_router.state import RouterStateDB
from paeos.model_router.transport import LiteLLMTransport
from paeos.model_router.types import (
    DataClass,
    LogicalModel,
    ModelCatalogEntry,
    ModelFamily,
    NormalizedError,
    NormalizedErrorType,
    ProviderHealth,
    ProviderId,
    RouterResponse,
    TaskClass,
    TaskRequest,
)


class ModelRouter:
    def __init__(
        self,
        credentials: Optional[CredentialStore] = None,
        catalog: Optional[ModelCatalog] = None,
        state_db: Optional[RouterStateDB] = None,
        transport: Optional[LiteLLMTransport] = None,
    ):
        self.credentials = credentials or CredentialStore()
        self.catalog = catalog or ModelCatalog()
        self.state_db = state_db or RouterStateDB()
        self.aimd = AIMDController(self.state_db)
        self.policy = RoutingPolicyEngine(self.catalog, self.state_db, self.credentials, self.aimd)
        self.transport = transport or LiteLLMTransport(self.credentials, self.catalog)

    def route(self, request: TaskRequest) -> RouterResponse:
        """
        Main routing entry point.
        Executes the candidate chain with deterministic fallback and single-retry policy.
        """
        candidates = self.policy.resolve_candidate_chain(request)
        if not candidates:
            raise NormalizedError(
                error_type=NormalizedErrorType.MODEL_UNAVAILABLE,
                message="No eligible models available matching task constraints, privacy rules, and provider health",
            )

        attempted_chain: List[str] = []
        last_error: Optional[NormalizedError] = None

        for candidate in candidates:
            attempted_chain.append(f"{candidate.provider_id.value}:{candidate.model_id}")

            admitted, reason = self.aimd.check_admission(candidate.provider_id)
            if not admitted:
                continue

            if not self.state_db.acquire_slot(candidate.provider_id):
                continue

            try:
                resp = self._dispatch_with_single_retry(candidate, request)
                resp.fallback_chain = attempted_chain
                return resp
            except NormalizedError as err:
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
                cooldown = self.aimd.on_rate_limit(candidate.provider_id, e)
                # If short retry-after (< 3s), perform ONE bounded retry with jitter
                if e.retry_after and e.retry_after <= 3.0:
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
        )
        if error.error_type == NormalizedErrorType.RATE_LIMITED:
            self.aimd.on_rate_limit(candidate.provider_id, error)
        else:
            self.aimd.on_error(candidate.provider_id, error)

    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        task_class: TaskClass = TaskClass.ROUTINE,
        data_class: DataClass = DataClass.INTERNAL,
        logical_model: Optional[LogicalModel] = None,
        builder_family: Optional[ModelFamily] = None,
        max_tokens: Optional[int] = None,
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
