"""
PAEOS Model Router — LiteLLM Transport Gateway Adapter
Strictly Transport Only: Autonomous retries, cooldowns, and fallbacks disabled.
"""
from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

import litellm
import requests

from paeos.model_router.credentials import CredentialStore
from paeos.model_router.errors import normalize_error
from paeos.model_router.types import (
    DataClass,
    ModelCatalogEntry,
    ModelFamily,
    NormalizedError,
    NormalizedErrorType,
    ProviderId,
    RouterResponse,
    TaskRequest,
)
from paeos.model_router.catalog import ModelCatalog
from paeos.model_router.a08_enforcer import derive_family_from_actual_model


litellm.num_retries = 0
litellm.telemetry = False
litellm.drop_params = True


PROVIDER_API_BASES: Dict[ProviderId, str] = {
    ProviderId.GOOGLE: "https://generativelanguage.googleapis.com/v1beta/openai/",
    ProviderId.CLINE: "https://api.cline.bot/api/v1",
    ProviderId.NVIDIA: "https://integrate.api.nvidia.com/v1",
    ProviderId.KILO: "https://api.kilo.ai/api/gateway",
    ProviderId.OPENROUTER: "https://openrouter.ai/api/v1",
}


class LiteLLMTransport:
    def __init__(self, credentials: CredentialStore, catalog: Optional[ModelCatalog] = None):
        self.credentials = credentials
        self.catalog = catalog or ModelCatalog()

    def dispatch(
        self,
        model_entry: ModelCatalogEntry,
        request: TaskRequest,
        timeout: float = 60.0,
    ) -> RouterResponse:
        """
        Dispatches request through transport layer to the physical provider.
        """
        api_key = self.credentials.get_key(model_entry.provider_id)
        if not api_key:
            raise NormalizedError(
                error_type=NormalizedErrorType.AUTH_FAILED,
                message=f"Missing API key for provider {model_entry.provider_id.value}",
                provider_id=model_entry.provider_id,
                model_id=model_entry.model_id,
            )

        api_base = PROVIDER_API_BASES.get(model_entry.provider_id)

        # Direct HTTP dispatch for Cline to handle Cline's {"data": {"choices": ...}} wire envelope
        if model_entry.provider_id == ProviderId.CLINE:
            return self._dispatch_cline(model_entry, request, api_key, api_base, timeout)

        litellm_model = f"openai/{model_entry.model_id}"
        # Sanitize messages for NVIDIA NIM (fails server-side if an assistant message has multiple parallel tool calls)
        cleaned_messages = request.messages
        if model_entry.provider_id == ProviderId.NVIDIA:
            cleaned_messages = []
            for m in request.messages:
                if m.get("role") == "assistant" and isinstance(m.get("tool_calls"), list) and len(m["tool_calls"]) > 1:
                    m_copy = dict(m)
                    m_copy["tool_calls"] = [m["tool_calls"][0]]
                    cleaned_messages.append(m_copy)
                else:
                    cleaned_messages.append(m)

        start_time = time.time()
        try:
            kwargs: Dict[str, Any] = {
                "model": litellm_model,
                "messages": cleaned_messages,
                "api_base": api_base,
                "api_key": api_key,
                "timeout": timeout,
                "num_retries": 0,
            }
            if request.max_tokens:
                kwargs["max_tokens"] = request.max_tokens
            if request.temperature is not None:
                kwargs["temperature"] = request.temperature
            if request.tools:
                kwargs["tools"] = request.tools
            if request.tool_choice:
                kwargs["tool_choice"] = request.tool_choice

            # Enforce ZDR (Zero Data Retention) headers for OpenRouter on CONFIDENTIAL tasks
            if model_entry.provider_id == ProviderId.OPENROUTER and request.data_class == DataClass.CONFIDENTIAL:
                kwargs["extra_body"] = {
                    "provider": {
                        "data_collection": "deny",
                        "zdr": True,
                    }
                }

            resp = litellm.completion(**kwargs)

            latency_ms = (time.time() - start_time) * 1000.0
            choice = resp.choices[0]
            msg = choice.message
            content = getattr(msg, "content", None) or ""
            if not content:
                content = getattr(msg, "reasoning", None) or getattr(msg, "reasoning_content", "") or ""

            # Extract tool calls if present
            tool_calls = None
            raw_tc = getattr(msg, "tool_calls", None)
            if raw_tc:
                tool_calls = []
                for tc in raw_tc:
                    if isinstance(tc, dict):
                        tool_calls.append(tc)
                    else:
                        fn = getattr(tc, "function", None)
                        tool_calls.append({
                            "id": getattr(tc, "id", f"call_{int(time.time()*1000)}"),
                            "type": getattr(tc, "type", "function"),
                            "function": {
                                "name": getattr(fn, "name", "") if fn else "",
                                "arguments": getattr(fn, "arguments", "{}") if fn else "{}",
                            },
                        })

            finish_reason = getattr(choice, "finish_reason", "stop") or ("tool_calls" if tool_calls else "stop")

            usage = getattr(resp, "usage", None)
            prompt_tokens = getattr(usage, "prompt_tokens", 0) if usage else 0
            completion_tokens = getattr(usage, "completion_tokens", 0) if usage else 0

            # Capture actual model from provider response for dynamic routes
            actual_model = getattr(resp, 'model', None) or model_entry.model_id
            actual_family = derive_family_from_actual_model(actual_model, self.catalog)
            
            return RouterResponse(
                content=content,
                model_id=model_entry.model_id,
                actual_model=actual_model,
                provider_id=model_entry.provider_id,
                family=model_entry.family,
                actual_family=actual_family,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=prompt_tokens + completion_tokens,
                latency_ms=latency_ms,
                tool_calls=tool_calls,
                finish_reason=finish_reason,
                raw_response=resp,
            )

        except Exception as e:
            status_code = getattr(e, "status_code", getattr(e, "http_status", None))
            response_body = getattr(e, "response", getattr(e, "message", str(e)))
            headers = getattr(e, "headers", None)

            norm_err = normalize_error(
                http_status=status_code,
                body=response_body,
                headers=headers,
                provider_id=model_entry.provider_id,
                model_id=model_entry.model_id,
            )
            raise norm_err from e

    def _dispatch_cline(
        self,
        model_entry: ModelCatalogEntry,
        request: TaskRequest,
        api_key: str,
        api_base: Optional[str],
        timeout: float,
    ) -> RouterResponse:
        """Handles Cline API direct dispatch with proper envelope unwrapping."""
        start_time = time.time()
        url = f"{api_base.rstrip('/')}/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        payload: Dict[str, Any] = {
            "model": model_entry.model_id,
            "messages": request.messages,
            "temperature": request.temperature if request.temperature is not None else 0.7,
        }
        if request.max_tokens:
            payload["max_tokens"] = request.max_tokens
        if request.tools:
            payload["tools"] = request.tools
        if request.tool_choice:
            payload["tool_choice"] = request.tool_choice

        try:
            r = requests.post(url, headers=headers, json=payload, timeout=timeout)
            latency_ms = (time.time() - start_time) * 1000.0

            if r.status_code != 200:
                norm_err = normalize_error(
                    http_status=r.status_code,
                    body=r.text,
                    headers=dict(r.headers),
                    provider_id=ProviderId.CLINE,
                    model_id=model_entry.model_id,
                )
                raise norm_err

            res_json = r.json()
            data_env = res_json.get("data", res_json)
            choices = data_env.get("choices", [])
            if not choices:
                raise normalize_error(
                    http_status=500,
                    body=res_json,
                    provider_id=ProviderId.CLINE,
                    model_id=model_entry.model_id,
                )

            choice = choices[0]
            msg = choice.get("message", {})
            content = msg.get("content") or msg.get("reasoning") or ""
            tool_calls = msg.get("tool_calls")
            finish_reason = choice.get("finish_reason", "stop") or ("tool_calls" if tool_calls else "stop")

            usage = data_env.get("usage", {})
            p_tok = usage.get("prompt_tokens", 0)
            c_tok = usage.get("completion_tokens", 0)

            # Capture actual model from Cline response
            actual_model = res_json.get("model") or res_json.get("data", {}).get("model") or model_entry.model_id
            actual_family = derive_family_from_actual_model(actual_model, self.catalog)
            
            return RouterResponse(
                content=content,
                model_id=model_entry.model_id,
                actual_model=actual_model,
                provider_id=ProviderId.CLINE,
                family=model_entry.family,
                actual_family=actual_family,
                prompt_tokens=p_tok,
                completion_tokens=c_tok,
                total_tokens=p_tok + c_tok,
                latency_ms=latency_ms,
                tool_calls=tool_calls,
                finish_reason=finish_reason,
                raw_response=res_json,
            )

        except Exception as e:
            if isinstance(e, NormalizedError):
                raise e
            norm_err = normalize_error(
                http_status=getattr(e, "status_code", None),
                body=str(e),
                provider_id=ProviderId.CLINE,
                model_id=model_entry.model_id,
            )
            raise norm_err from e
