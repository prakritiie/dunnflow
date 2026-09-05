"""Issuer health sentinel - EWMA success-rate tracker.

Deterministic statistics, no model. This is the correct altitude for an
infrastructure failure: a hundred cases failing against one issuer is ONE
incident, not a hundred independent decisions. Reasoning case-by-case would
retry into a dead issuer a hundred times and call it recovery.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from app.domain.models.core import IssuerHealth

ALPHA = 0.2          # EWMA smoothing
MIN_SAMPLES = 20     # do not act on thin evidence
PROBE_EVERY = 4      # release one probe per N denials so health can recover


@dataclass
class IssuerSentinel:
    _rate: dict[str, float] = field(default_factory=dict)
    _n: dict[str, int] = field(default_factory=dict)
    _denied: dict[str, int] = field(default_factory=dict)

    @staticmethod
    def issuer_of(failure_class: str) -> str:
        """Cases are grouped by the upstream they exercise."""
        return {
            "ISSUER_DECLINE": "ISSUER_A", "SOFT_DECLINE": "ISSUER_A",
            "NETWORK_ERROR": "GATEWAY", "GATEWAY_ERROR": "GATEWAY",
            "GATEWAY_TIMEOUT": "GATEWAY",
        }.get(failure_class, "DEFAULT")

    def observe(self, failure_class: str, succeeded: bool) -> None:
        k = self.issuer_of(failure_class)
        prev = self._rate.get(k, 1.0)
        self._rate[k] = (1 - ALPHA) * prev + ALPHA * (1.0 if succeeded else 0.0)
        self._n[k] = self._n.get(k, 0) + 1

    def allow_probe(self, failure_class: str) -> bool:
        """Recovery wave.

        A sentinel that only ever denies starves itself of samples: with no new
        traffic the EWMA can never rise, so the block becomes permanent. Release
        a jittered probe every PROBE_EVERY denials so health can recover - the
        same HALF_OPEN idea the circuit breaker uses.
        """
        k = self.issuer_of(failure_class)
        self._denied[k] = self._denied.get(k, 0) + 1
        if self._denied[k] % PROBE_EVERY == 0:
            return True
        return False

    def health(self, failure_class: str) -> IssuerHealth:
        k = self.issuer_of(failure_class)
        return IssuerHealth(issuer=k, ewma_success_rate=self._rate.get(k, 1.0),
                            samples=self._n.get(k, 0))

    def snapshot(self) -> dict:
        return {k: {"ewma": round(self._rate.get(k, 1.0), 3), "samples": self._n.get(k, 0),
                    "denied": self._denied.get(k, 0)}
                for k in set(self._rate) | set(self._n)}
