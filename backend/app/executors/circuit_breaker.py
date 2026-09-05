"""Per-gateway circuit breaker: CLOSED -> OPEN -> HALF_OPEN.

The breaker sits in the decision path, so it uses the SAME injected clock as the
policy engine. Using wall-clock time here would make behaviour depend on how fast
the batch happens to run, which is neither deterministic nor replayable.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from app.core.clock import Clock, RealClock


@dataclass
class Breaker:
    clock: Clock = field(default_factory=RealClock)
    threshold: int = 5
    window_s: float = 60.0
    cooldown_s: float = 45.0
    probe_budget: int = 2
    _failures: list[datetime] = field(default_factory=list)
    _opened_at: datetime | None = None
    _probes: int = 0

    def _now(self) -> datetime:
        return self.clock.now()

    @property
    def state(self) -> str:
        from app.chaos.injector import CHAOS
        if CHAOS.is_active("circuit-open"):
            return "OPEN"
        if self._opened_at is None:
            return "CLOSED"
        if (self._now() - self._opened_at).total_seconds() >= self.cooldown_s:
            return "HALF_OPEN"
        return "OPEN"

    def allows(self) -> bool:
        s = self.state
        if s == "CLOSED":
            return True
        if s == "HALF_OPEN":
            if self._probes < self.probe_budget:
                self._probes += 1
                return True
            # probe budget spent without success - reopen from now
            self._opened_at = self._now()
            self._probes = 0
            return False
        return False

    def record_success(self) -> None:
        self._failures.clear(); self._opened_at = None; self._probes = 0

    def record_failure(self) -> None:
        now = self._now()
        cutoff = now - timedelta(seconds=self.window_s)
        self._failures = [t for t in self._failures if t > cutoff]
        self._failures.append(now)
        if len(self._failures) >= self.threshold:
            self._opened_at = now
            self._probes = 0

    def reset(self) -> None:
        self._failures.clear(); self._opened_at = None; self._probes = 0
