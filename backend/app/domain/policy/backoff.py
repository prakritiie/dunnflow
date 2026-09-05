"""Backoff computation. Pure: seeded jitter, injected clock, no randomness source
outside the supplied seed - so the same case yields the same schedule every run."""
from __future__ import annotations
import hashlib
from datetime import datetime, timedelta
from app.domain.models.enums import Backoff

_MAX_JITTER_S = 900


def _stable_jitter(key: str, ceiling: int) -> int:
    """Deterministic 'random' jitter derived from the case key, not from time."""
    h = hashlib.sha256(key.encode()).digest()
    return int.from_bytes(h[:4], "big") % max(ceiling, 1)


def compute(strategy: Backoff, *, now: datetime, attempt_index: int, key: str) -> datetime | None:
    if strategy == Backoff.NONE:
        return None
    if strategy == Backoff.FIXED_SHORT:
        return now + timedelta(minutes=20)
    if strategy == Backoff.EXPONENTIAL_JITTER:
        base = 2 ** max(attempt_index, 0) * 300           # 5m, 10m, 20m ...
        return now + timedelta(seconds=base + _stable_jitter(key, _MAX_JITTER_S))
    if strategy == Backoff.DEFER_CREDIT_CYCLE:
        # A 5-minute retry into an empty account is a guaranteed decline that
        # still consumes a network attempt. Defer toward the next credit date.
        days = 3 if attempt_index == 0 else 7
        target = (now + timedelta(days=days)).replace(hour=10, minute=30, second=0, microsecond=0)
        return target + timedelta(seconds=_stable_jitter(key, 1800))
    if strategy == Backoff.ISSUER_HEALTH_GATED:
        return now + timedelta(minutes=45) + timedelta(seconds=_stable_jitter(key, _MAX_JITTER_S))
    return None
