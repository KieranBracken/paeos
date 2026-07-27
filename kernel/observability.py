"""Observability — structured JSON logging + a cost/trace meter (PAEOS-8 §10 B0.13 / §3).

Task B0.13. Two primitives the runtime uses to make every action visible and accountable:

  * **Structured logging** — `structlog` (§3-pinned) rendering one JSON object per event, through
    a **secret-scrubbing** processor so keys like `password`/`seed`/`signing_key`/`token` never
    reach the log sink. Content hashes (public addresses) are *not* scrubbed.
  * **Cost/trace meter** — a `Meter` that records one `MeterRow` per action (`tokens`,
    `wallclock_s`, `model_ver`), the raw material for budget governance (K11) and drift audit.

`traced(...)` wraps an action so it emits a start/end log *and* a meter row in one call — the
"every kernel call emits a structured log; the meter records a row per action" acceptance.
"""

from __future__ import annotations

import sys
import time
from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TextIO

import structlog
from structlog.typing import EventDict, WrappedLogger

__all__ = [
    "REDACTED",
    "Meter",
    "MeterRow",
    "configure_logging",
    "get_logger",
    "scrub_secrets",
    "traced",
]

REDACTED = "***REDACTED***"

# Keys whose values are secrets and must never be logged. Exact names + substrings; bare "token"
# is exact (so the meter's "tokens" count is NOT scrubbed) — precision matters here.
_SECRET_KEYS = frozenset({"token", "authorization", "auth", "cookie", "attestation"})
_SECRET_SUBSTRINGS = (
    "password",
    "passphrase",
    "secret",
    "seed",
    "signing_key",
    "private_key",
    "api_key",
    "credential",
)


def _is_secret(key: str) -> bool:
    k = key.lower()
    return k in _SECRET_KEYS or any(s in k for s in _SECRET_SUBSTRINGS)


def scrub_secrets(_logger: WrappedLogger, _method: str, event_dict: EventDict) -> EventDict:
    """structlog processor: redact secret-valued keys in place. Content hashes are left intact."""
    for key in list(event_dict.keys()):
        if _is_secret(key):
            event_dict[key] = REDACTED
    return event_dict


def configure_logging(stream: TextIO | None = None) -> None:
    """Configure structlog to emit scrubbed JSON to `stream` (stdout by default). Idempotent-safe:
    call again to redirect (e.g. in tests)."""
    structlog.configure(
        processors=[
            structlog.processors.add_log_level,
            scrub_secrets,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.JSONRenderer(sort_keys=True),
        ],
        logger_factory=structlog.WriteLoggerFactory(file=stream or sys.stdout),
        cache_logger_on_first_use=False,
    )


def get_logger(name: str = "paeos") -> structlog.stdlib.BoundLogger:
    """A bound logger. Emits scrubbed JSON once `configure_logging` has run."""
    return structlog.get_logger(name)


# ---- cost / trace meter ---------------------------------------------------


@dataclass(frozen=True, slots=True)
class MeterRow:
    """One metered action (PAEOS-8 §10: tokens, wallclock, model_ver per action)."""

    action: str
    tokens: int
    wallclock_s: float
    model_ver: str
    timestamp: str


class Meter:
    """Records one row per action. The source for cost governance (K11) and model-drift audit."""

    def __init__(self) -> None:
        self._rows: list[MeterRow] = []

    def record(
        self, action: str, *, tokens: int = 0, wallclock_s: float = 0.0, model_ver: str = "kernel"
    ) -> MeterRow:
        row = MeterRow(
            action=action,
            tokens=tokens,
            wallclock_s=wallclock_s,
            model_ver=model_ver,
            timestamp=datetime.now(UTC).isoformat(),
        )
        self._rows.append(row)
        return row

    @property
    def rows(self) -> tuple[MeterRow, ...]:
        return tuple(self._rows)

    def total_tokens(self) -> int:
        return sum(row.tokens for row in self._rows)


# ---- combined trace: one log + one meter row per action -------------------


@contextmanager
def traced(
    action: str,
    *,
    logger: structlog.stdlib.BoundLogger | None = None,
    meter: Meter | None = None,
    tokens: int = 0,
    model_ver: str = "kernel",
    **fields: object,
) -> Generator[None, None, None]:
    """Wrap an action so it emits a start/end structured log and (if a meter is given) one meter
    row with the measured wallclock. Extra `fields` are logged (and scrubbed)."""
    log = logger if logger is not None else get_logger()
    start = time.monotonic()
    log.info(action, phase="start", **fields)
    try:
        yield
    finally:
        elapsed = time.monotonic() - start
        log.info(action, phase="end", wallclock_s=elapsed, **fields)
        if meter is not None:
            meter.record(action, tokens=tokens, wallclock_s=elapsed, model_ver=model_ver)
