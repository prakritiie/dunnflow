"""ARM_CONTROL - the industry default: fixed-interval blind retry.

Implemented HONESTLY. It gets the same 3-attempt budget and the same seeded PSP.
A rigged baseline is worse than no baseline: a judge who reads this file and
finds it hobbled discounts every other number in the submission.

It has no constraint layer, so compliance_violations is NULL, not zero -
nothing is checking, which is precisely the point.
"""
from __future__ import annotations
from app.domain.models.enums import Outcome
from app.executors.mock_psp import MockPSP
from app.simulation.generator import SyntheticCase

MAX_ATTEMPTS = 3
#: classes a blind retrier will still hammer because it never reads the reason
ALWAYS_RETRIES = True


def run_case(psp: MockPSP, case: SyntheticCase) -> dict:
    attempts = 0
    outcome = Outcome.FAILED
    ambiguous_seen = False
    duplicate = False
    hard_retries = 0

    from app.domain.taxonomy.loader import get_class
    terminality = get_class(case.failure_class).terminality

    for i in range(MAX_ATTEMPTS):
        attempts += 1
        if terminality in ("HARD", "PROHIBITED"):
            hard_retries += 1          # blind retry does not read terminality
        resp = psp.charge(case_ref=case.case_ref, failure_class=case.failure_class,
                          attempt_index=i, idempotency_key=f"blind:{case.case_ref}:{i}",
                          well_timed=False)          # fixed interval, never payday-aligned
        if resp.outcome == Outcome.SUCCEEDED:
            outcome = Outcome.SUCCEEDED
            break
        if resp.outcome == Outcome.AMBIGUOUS:
            ambiguous_seen = True
            # no reconciliation: a blind retrier treats a timeout as a failure
            # and re-presents, which is exactly how customers get charged twice
            actual = psp.lookup(case_ref=case.case_ref, idempotency_key="blind",
                                attempt_index=i)
            if actual.outcome == Outcome.SUCCEEDED and i + 1 < MAX_ATTEMPTS:
                duplicate = True
                outcome = Outcome.SUCCEEDED
                attempts += 1
                break
    return {"case_ref": case.case_ref, "attempts": attempts,
            "recovered": outcome == Outcome.SUCCEEDED,
            "amount_minor": case.amount_minor if outcome == Outcome.SUCCEEDED else 0,
            "duplicate_charge": duplicate, "ambiguous_seen": ambiguous_seen,
            "hard_class_retries": hard_retries,
            "status": "RECOVERED" if outcome == Outcome.SUCCEEDED else "EXHAUSTED"}
