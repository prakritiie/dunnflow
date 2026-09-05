"""Executor base. The idempotency lock is enforced HERE so no subclass can bypass it."""
from __future__ import annotations
from app.core.exceptions import IdempotencyNotHeld
from app.domain.models.core import Directive, ExecutionResult
from app.domain.models.enums import MONEY_MOVING, Outcome
from app.executors.circuit_breaker import Breaker
from app.executors.idempotency import STORE, derive_key
from app.executors.mock_psp import MockPSP


class ExecutorBase:
    def __init__(self, psp: MockPSP, breaker: Breaker) -> None:
        self.psp = psp
        self.breaker = breaker

    async def execute(self, *, case_ref: str, case_key: str, failure_class: str,
                      directive: Directive, well_timed: bool, on_attempt_row) -> ExecutionResult:
        key = derive_key(case_key=case_key, action=str(directive.action),
                         attempt_index=directive.attempt_index,
                         policy_version=directive.policy_version)

        if directive.action in MONEY_MOVING:
            if await STORE.money_locked(case_ref):
                raise IdempotencyNotHeld("Case money lock held - ambiguity unresolved")
            if not await STORE.acquire(key):
                return ExecutionResult(outcome=Outcome.FAILED, idempotency_key=key,
                                       error_raw={"reason": "idempotent_skip"})
            if not self.breaker.allows():
                await STORE.release(key)
                raise IdempotencyNotHeld("Circuit breaker OPEN")

        # attempt row is written BEFORE the network call: a crash mid-call must
        # still leave evidence that money may have moved
        await on_attempt_row(key, Outcome.IN_FLIGHT)

        resp = self.psp.charge(case_ref=case_ref, failure_class=failure_class,
                               attempt_index=directive.attempt_index,
                               idempotency_key=key, well_timed=well_timed)

        if resp.outcome == Outcome.SUCCEEDED:
            self.breaker.record_success()
        elif resp.outcome == Outcome.AMBIGUOUS:
            # transport-level, feeds the breaker
            self.breaker.record_failure()
        # A business decline (insufficient funds, issuer no) is NOT a gateway
        # health signal. Counting it would trip the breaker on healthy infra.

        return ExecutionResult(outcome=resp.outcome, idempotency_key=key,
                               gateway_ref=resp.gateway_ref, error_raw=resp.error,
                               amount_minor=directive.amount_minor)
