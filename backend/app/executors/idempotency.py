"""Idempotency key derivation and locking.

The key derives ONLY from immutable facts. It contains no wall-clock component,
no request id, and no randomness: a key that changes across a restart is not an
idempotency key, it is a double-charge generator.
"""
from __future__ import annotations
import uuid
import redis.asyncio as aioredis
from app.core.config import settings
from app.core.exceptions import DunnflowError

NAMESPACE = uuid.UUID("6ba7b812-9dad-11d1-80b4-00c04fd430c8")
_LOCK_TTL_S = 86_400


def derive_key(*, case_key: str, action: str, attempt_index: int, policy_version: str) -> str:
    """case_key must uniquely identify the obligation.

    In production that is merchant_id:obligation_ref. In a simulation each run is
    a separate universe - CASE-0001 in run A is not the same obligation as
    CASE-0001 in run B - so the run id is part of the identity.
    """
    return str(uuid.uuid5(NAMESPACE, f"{case_key}:{action}:{attempt_index}:{policy_version}"))


class RedisUnavailable(DunnflowError):
    code, status = "REDIS_UNAVAILABLE", 503
    message = "Idempotency store unreachable - money movement halted (fail-closed)"


class IdempotencyStore:
    def __init__(self, url: str | None = None) -> None:
        self._url = url or settings.REDIS_URL
        self._r: aioredis.Redis | None = None

    async def client(self) -> aioredis.Redis:
        if self._r is None:
            self._r = aioredis.from_url(self._url, decode_responses=True)
        return self._r

    async def acquire(self, key: str) -> bool:
        """True if this caller now owns the key. False means it was already consumed.
        Raises RedisUnavailable rather than returning True - fail closed."""
        from app.chaos.injector import CHAOS
        if CHAOS.is_active("redis-down"):
            raise RedisUnavailable()
        try:
            r = await self.client()
            return bool(await r.set(f"idem:{key}", "1", nx=True, ex=_LOCK_TTL_S))
        except RedisUnavailable:
            raise
        except Exception as exc:
            raise RedisUnavailable(detail={"cause": type(exc).__name__}) from exc

    async def consumed(self, key: str) -> bool:
        from app.chaos.injector import CHAOS
        if CHAOS.is_active("redis-down"):
            raise RedisUnavailable()
        try:
            r = await self.client()
            return bool(await r.exists(f"idem:{key}"))
        except RedisUnavailable:
            raise
        except Exception as exc:
            raise RedisUnavailable(detail={"cause": type(exc).__name__}) from exc

    async def release(self, key: str) -> None:
        try:
            r = await self.client()
            await r.delete(f"idem:{key}")
        except Exception:
            pass

    # ---- case-level money lock: blocks ALL money actions on an ambiguous case ----
    async def lock_money(self, case_ref: str, ttl_s: int = 900) -> bool:
        r = await self.client()
        return bool(await r.set(f"money_lock:{case_ref}", "1", nx=True, ex=ttl_s))

    async def money_locked(self, case_ref: str) -> bool:
        try:
            r = await self.client()
            return bool(await r.exists(f"money_lock:{case_ref}"))
        except Exception:
            return True                      # fail closed
    async def unlock_money(self, case_ref: str) -> None:
        r = await self.client()
        await r.delete(f"money_lock:{case_ref}")

    async def close(self) -> None:
        if self._r is not None:
            await self._r.aclose()
            self._r = None


STORE = IdempotencyStore()
