"""Clock protocol. Domain code must never call datetime.now() directly -
an injected clock is what makes the policy engine deterministic and replayable."""
from __future__ import annotations
from datetime import datetime, timedelta, timezone
from typing import Protocol


class Clock(Protocol):
    def now(self) -> datetime: ...


class RealClock:
    def now(self) -> datetime:
        return datetime.now(timezone.utc)


class FrozenClock:
    def __init__(self, at: datetime | None = None) -> None:
        self._at = at or datetime(2025, 1, 15, 3, 53, 41, tzinfo=timezone.utc)

    def now(self) -> datetime:
        return self._at

    def advance(self, **kw) -> None:
        self._at = self._at + timedelta(**kw)
