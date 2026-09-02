"""
PAEOS Model Router — Normalized Error Handling Engine
"""
from __future__ import annotations

import contextlib
import json
import re
from typing import Any

from paeos.model_router.types import NormalizedError, NormalizedErrorType, ProviderId


def parse_retry_after(headers: dict[str, Any] | None, body_str: str = "") -> float | None:
    """Extract Retry-After from HTTP headers or body text (e.g. 'Try again in 1h 29m' or 'retry after 15s')."""
    if headers:
        for k, v in headers.items():
            if k.lower() == "retry-after":
                try:
                    return float(v)
                except (ValueError, TypeError):
                    pass

    if body_str:
        # Match 'Try again in Xh Ym'
        m_hm = re.search(r"try again in\s+(?:(\d+)\s*h)?\s*(?:(\d+)\s*m)?", body_str.lower())
        if m_hm and (m_hm.group(1) or m_hm.group(2)):
            hours = int(m_hm.group(1)) if m_hm.group(1) else 0
            mins = int(m_hm.group(2)) if m_hm.group(2) else 0
            return float(hours * 3600 + mins * 60)

        # Match 'retry after Xs'
        m_s = re.search(r"retry after\s+([0-9\.]+)\s*s", body_str.lower())
        if m_s:
            try:
                return float(m_s.group(1))
            except Exception:
                pass

    return None


def normalize_error(
    http_status: int | None,
    body: Any | None,
    headers: dict[str, Any] | None = None,
    provider_id: ProviderId | None = None,
    model_id: str | None = None,
) -> NormalizedError:
    """
    Parses HTTP status + provider-specific error body into canonical NormalizedError.
    Never relies solely on raw HTTP status code.
    """
    raw_str = ""
    body_data: dict[str, Any] = {}

    if isinstance(body, dict):
        body_data = body
        raw_str = json.dumps(body)
    elif isinstance(body, str):
        raw_str = body
        with contextlib.suppress(Exception):
            body_data = json.loads(body)
    elif body is not None:
        raw_str = str(body)

    err_msg = ""
    err_code = ""
    if "error" in body_data:
        if isinstance(body_data["error"], dict):
            err_msg = body_data["error"].get("message", "")
            err_code = str(body_data["error"].get("code", ""))
        else:
            err_msg = str(body_data["error"])
    elif "message" in body_data:
        err_msg = str(body_data["message"])
    else:
        err_msg = raw_str

    lower_msg = (err_msg + " " + raw_str + " " + err_code).lower()
    retry_after = parse_retry_after(headers, raw_str)

    # 1. Daily Free Inference Cap / Quota Exhaustion
    if "inference_cap_error" in lower_msg or "daily free limit reached" in lower_msg:
        return NormalizedError(
            error_type=NormalizedErrorType.QUOTA_EXHAUSTED,
            message=err_msg or "Daily free model allowance exhausted (DAILY_FREE_QUOTA_EXHAUSTED)",
            provider_id=provider_id,
            model_id=model_id,
            http_status=http_status or 429,
            retry_after=retry_after or 3600.0,
            raw_response=raw_str,
        )

    # 2. Context Length Exceeded (can arrive as 400 on Kilo/OpenAI or 413)
    if (
        http_status in (400, 413)
        or "context" in lower_msg
        or "maximum context length" in lower_msg
        or "prompt is too long" in lower_msg
        or "token limit exceeded" in lower_msg
    ) and ("context" in lower_msg or "token" in lower_msg or "too long" in lower_msg or "exceeded" in lower_msg):
        return NormalizedError(
            error_type=NormalizedErrorType.CONTEXT_EXCEEDED,
            message=err_msg or "Context length exceeded maximum token limit",
            provider_id=provider_id,
            model_id=model_id,
            http_status=http_status,
            retry_after=retry_after,
            raw_response=raw_str,
        )

    # 3. Rate Limiting / 429
    if http_status == 429 or "rate limit" in lower_msg or "too many requests" in lower_msg:
        return NormalizedError(
            error_type=NormalizedErrorType.RATE_LIMITED,
            message=err_msg or "Rate limit exceeded",
            provider_id=provider_id,
            model_id=model_id,
            http_status=http_status,
            retry_after=retry_after,
            raw_response=raw_str,
        )

    # 4. Monetary Credit Balance Exhaustion (402 or explicit balance gate)
    if (
        http_status == 402
        or "insufficient_credits" in lower_msg
        or "insufficient balance" in lower_msg
        or "insufficient_quota" in lower_msg
        or (http_status == 503 and "credit" in lower_msg and provider_id == ProviderId.KILO)
    ):
        return NormalizedError(
            error_type=NormalizedErrorType.QUOTA_EXHAUSTED,
            message=err_msg or "Provider monetary credit balance exhausted (CREDIT_BALANCE_EXHAUSTED)",
            provider_id=provider_id,
            model_id=model_id,
            http_status=http_status,
            retry_after=retry_after,
            raw_response=raw_str,
        )

    # 5. Product Surface / Surface Auth Restriction (403 product surfaces)
    if http_status == 403 and "only available via cline product surfaces" in lower_msg:
        return NormalizedError(
            error_type=NormalizedErrorType.MODEL_UNAVAILABLE,
            message=err_msg or "Model restricted to Cline product surfaces / ClinePass subscription",
            provider_id=provider_id,
            model_id=model_id,
            http_status=http_status,
            retry_after=None,
            raw_response=raw_str,
        )

    # 6. Authentication / Authorization Failure (401 / 403 invalid key)
    if http_status == 401 or (http_status == 403 and "api key" in lower_msg) or "invalid api key" in lower_msg:
        return NormalizedError(
            error_type=NormalizedErrorType.AUTH_FAILED,
            message=err_msg or "Authentication failed: invalid or unauthorized API key",
            provider_id=provider_id,
            model_id=model_id,
            http_status=http_status,
            retry_after=None,
            raw_response=raw_str,
        )

    # 7. Model Unavailable / Disappeared (404)
    if http_status == 404 or "model not found" in lower_msg or "does not exist" in lower_msg:
        return NormalizedError(
            error_type=NormalizedErrorType.MODEL_UNAVAILABLE,
            message=err_msg or "Model identifier unavailable or retired",
            provider_id=provider_id,
            model_id=model_id,
            http_status=http_status,
            retry_after=None,
            raw_response=raw_str,
        )

    # 8. Safety / Content Policy (400 / 422)
    if "safety" in lower_msg or "content filter" in lower_msg or "policy violation" in lower_msg:
        return NormalizedError(
            error_type=NormalizedErrorType.CONTENT_POLICY,
            message=err_msg or "Request flagged by content safety filter",
            provider_id=provider_id,
            model_id=model_id,
            http_status=http_status,
            retry_after=None,
            raw_response=raw_str,
        )

    # 9. Bad Request / Malformed Schema (400)
    if http_status == 400 or "invalid parameter" in lower_msg or "bad request" in lower_msg:
        return NormalizedError(
            error_type=NormalizedErrorType.BAD_REQUEST,
            message=err_msg or "Malformed request or invalid parameters",
            provider_id=provider_id,
            model_id=model_id,
            http_status=http_status,
            retry_after=None,
            raw_response=raw_str,
        )

    # 10. Timeout (408 / 504)
    if http_status in (408, 504) or "timeout" in lower_msg or "timed out" in lower_msg:
        return NormalizedError(
            error_type=NormalizedErrorType.TIMEOUT,
            message=err_msg or "Provider gateway timeout",
            provider_id=provider_id,
            model_id=model_id,
            http_status=http_status,
            retry_after=retry_after or 5.0,
            raw_response=raw_str,
        )

    # 11. Provider Unavailable / Service Outage (500 / 502 / 503)
    if http_status in (500, 502, 503):
        return NormalizedError(
            error_type=NormalizedErrorType.PROVIDER_UNAVAILABLE,
            message=err_msg or f"Provider upstream service error (HTTP {http_status})",
            provider_id=provider_id,
            model_id=model_id,
            http_status=http_status,
            retry_after=retry_after or 30.0,
            raw_response=raw_str,
        )

    return NormalizedError(
        error_type=NormalizedErrorType.UNKNOWN,
        message=err_msg or f"Unclassified error (HTTP {http_status})",
        provider_id=provider_id,
        model_id=model_id,
        http_status=http_status,
        retry_after=retry_after,
        raw_response=raw_str,
    )
