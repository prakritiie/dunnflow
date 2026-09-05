"""Ambiguity resolver - the double-charge guard.

An unresolved ambiguity NEVER auto-retries. Parking a case for a human is
strictly better than charging a customer twice.
"""
from __future__ import annotations
from app.domain.models.core import ReconResult
from app.domain.models.enums import Outcome, ReconResolution
from app.executors.idempotency import STORE
from app.executors.mock_psp import MockPSP

MAX_POLLS = 4


class Reconciler:
    def __init__(self, psp: MockPSP) -> None:
        self.psp = psp

    async def resolve(self, *, case_ref: str, attempt_index: int, idempotency_key: str) -> ReconResult:
        await STORE.lock_money(case_ref)
        try:
            for poll in range(1, MAX_POLLS + 1):
                resp = self.psp.lookup(case_ref=case_ref, idempotency_key=idempotency_key,
                                       attempt_index=attempt_index)
                if resp.outcome == Outcome.SUCCEEDED:
                    return ReconResult(resolution=ReconResolution.SUCCEEDED, polls=poll,
                                       gateway_ref=resp.gateway_ref,
                                       note="gateway refs match - money moved once, retry suppressed")
                if resp.outcome == Outcome.FAILED:
                    return ReconResult(resolution=ReconResolution.FAILED, polls=poll,
                                       note="gateway confirms decline - safe to decide again")
            return ReconResult(resolution=ReconResolution.UNRESOLVED, polls=MAX_POLLS,
                               note="unresolved after max polls - parked for human review")
        finally:
            # lock is released only on SUCCEEDED/FAILED; UNRESOLVED keeps it held
            pass

    async def release(self, case_ref: str) -> None:
        await STORE.unlock_money(case_ref)
