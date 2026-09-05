"""Deterministic seeded mock PSP.

Seeding is what makes the dual-arm comparison valid: both arms see byte-identical
gateway behaviour for the same seed, so any difference in outcome is attributable
to the policy, not to luck.
"""
from __future__ import annotations
import hashlib
from dataclasses import dataclass
from app.chaos.injector import CHAOS
from app.domain.models.enums import Outcome


@dataclass(frozen=True)
class PSPResponse:
    outcome: Outcome
    gateway_ref: str | None = None
    error: dict | None = None


def _roll(seed: int, key: str) -> float:
    """Deterministic uniform draw in [0,1) from (seed, key)."""
    h = hashlib.sha256(f"{seed}:{key}".encode()).digest()
    return int.from_bytes(h[:6], "big") / float(1 << 48)


#: Probability a correctly-targeted intervention succeeds, per failure class.
#: HARD/PROHIBITED classes are absent - they are never retried at all.
LATENT_RECOVERY = {
    "INSUFFICIENT_FUNDS": 0.55,
    "TEMPORARY_HOLD":     0.70,
    "NETWORK_ERROR":      0.80,
    "GATEWAY_ERROR":      0.75,
    "ISSUER_DECLINE":     0.45,
    "SOFT_DECLINE":       0.60,
    "GATEWAY_TIMEOUT":    0.50,
}

#: A blind retry fired at the wrong moment succeeds far less often. This gap is
#: what the two arms are actually measuring.
BLIND_PENALTY = {
    "INSUFFICIENT_FUNDS": 0.18,   # retrying into an empty account
    "ISSUER_DECLINE":     0.40,
    "SOFT_DECLINE":       0.65,
    "TEMPORARY_HOLD":     0.35,
    "NETWORK_ERROR":      0.85,   # transient - timing matters least
    "GATEWAY_ERROR":      0.80,
    "GATEWAY_TIMEOUT":    0.50,
}


class MockPSP:
    def __init__(self, seed: int) -> None:
        self.seed = seed
        self.calls = 0

    def charge(self, *, case_ref: str, failure_class: str, attempt_index: int,
               idempotency_key: str, well_timed: bool) -> PSPResponse:
        self.calls += 1

        if CHAOS.is_active("gateway-timeout"):
            return PSPResponse(Outcome.AMBIGUOUS, error={"reason": "gateway_timeout", "injected": True})

        base = LATENT_RECOVERY.get(failure_class, 0.0)
        p = base if well_timed else base * BLIND_PENALTY.get(failure_class, 0.5)
        # each additional attempt is less likely to land
        p *= (0.82 ** attempt_index)

        r = _roll(self.seed, f"{case_ref}:{attempt_index}:charge")

        # a small slice of calls time out for real, independent of chaos
        if _roll(self.seed, f"{case_ref}:{attempt_index}:timeout") < 0.04:
            return PSPResponse(Outcome.AMBIGUOUS, error={"reason": "gateway_timeout"})

        if r < p:
            return PSPResponse(Outcome.SUCCEEDED, gateway_ref=f"pay_{abs(hash((case_ref, attempt_index))) % 10**10:010d}")
        return PSPResponse(Outcome.FAILED, error={"reason": failure_class.lower()})

    def lookup(self, *, case_ref: str, idempotency_key: str, attempt_index: int) -> PSPResponse:
        """Reconciliation probe. An AMBIGUOUS charge resolves to whatever actually
        happened on the gateway side - deterministically derived from the same seed."""
        r = _roll(self.seed, f"{case_ref}:{attempt_index}:actual")
        if r < 0.45:
            return PSPResponse(Outcome.SUCCEEDED, gateway_ref=f"pay_{abs(hash((case_ref, attempt_index))) % 10**10:010d}")
        if r < 0.92:
            return PSPResponse(Outcome.FAILED, error={"reason": "declined"})
        return PSPResponse(Outcome.AMBIGUOUS, error={"reason": "still_pending"})
