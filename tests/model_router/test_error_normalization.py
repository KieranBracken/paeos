"""
Adversarial Unit Tests: Normalized Error Engine
"""
from paeos.model_router.errors import normalize_error
from paeos.model_router.types import NormalizedErrorType, ProviderId


def test_context_overflow_returned_as_400():
    """Kilo/OpenAI returning 400 with 'context length' must be normalized to CONTEXT_EXCEEDED."""
    body = {
        "error": {
            "message": "This model maximum context length is 32768 tokens, however your request resulted in 45000 tokens.",
            "type": "invalid_request_error"
        }
    }
    err = normalize_error(http_status=400, body=body, provider_id=ProviderId.KILO, model_id="kilo-auto/free")
    assert err.error_type == NormalizedErrorType.CONTEXT_EXCEEDED
    assert "maximum context length" in err.message


def test_rate_limit_with_retry_after_header():
    """429 with Retry-After header must normalize to RATE_LIMITED with parsed duration."""
    err = normalize_error(
        http_status=429,
        body={"error": {"message": "Rate limit reached for requests per minute"}},
        headers={"retry-after": "25.5"},
        provider_id=ProviderId.GOOGLE,
    )
    assert err.error_type == NormalizedErrorType.RATE_LIMITED
    assert err.retry_after == 25.5


def test_rate_limit_with_body_text_retry_after():
    """429 with retry duration in message body string."""
    err = normalize_error(
        http_status=429,
        body="Please retry after 12.0s due to rate limits.",
        provider_id=ProviderId.NVIDIA,
    )
    assert err.error_type == NormalizedErrorType.RATE_LIMITED
    assert err.retry_after == 12.0


def test_quota_exhausted_402_and_kilo_503():
    """402 or Kilo 503 credit depletion must normalize to QUOTA_EXHAUSTED."""
    err1 = normalize_error(http_status=402, body="Monthly credit quota exceeded.", provider_id=ProviderId.OPENROUTER)
    assert err1.error_type == NormalizedErrorType.QUOTA_EXHAUSTED

    err2 = normalize_error(http_status=503, body="upstream credit allowance depleted", provider_id=ProviderId.KILO)
    assert err2.error_type == NormalizedErrorType.QUOTA_EXHAUSTED


def test_auth_failure_401():
    """401 status must normalize to AUTH_FAILED."""
    err = normalize_error(http_status=401, body="Invalid API key provided.", provider_id=ProviderId.CLINE)
    assert err.error_type == NormalizedErrorType.AUTH_FAILED


def test_bad_request_malformed_400():
    """Genuine 400 schema error must normalize to BAD_REQUEST (not CONTEXT_EXCEEDED)."""
    err = normalize_error(http_status=400, body="Invalid parameter: 'temperature' must be <= 2.0", provider_id=ProviderId.GOOGLE)
    assert err.error_type == NormalizedErrorType.BAD_REQUEST


def test_provider_outage_503():
    """Generic 503 service unavailable."""
    err = normalize_error(http_status=503, body="Service Unavailable", provider_id=ProviderId.NVIDIA)
    assert err.error_type == NormalizedErrorType.PROVIDER_UNAVAILABLE
    assert err.retry_after == 30.0
