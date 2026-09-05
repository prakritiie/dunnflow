"""Explicit state-transition allow-list.

An illegal transition raises rather than silently passing. Two properties matter:
  * nothing leaves RECON_PENDING except the reconciler
  * no money-moving state is reachable from NEEDS_HUMAN without a human decision
"""
from __future__ import annotations
from app.core.exceptions import InvalidStateTransition
from app.domain.models.enums import CaseStatus as S

ALLOWED: dict[S, frozenset[S]] = {
    S.RECEIVED:        frozenset({S.HYDRATED}),
    S.HYDRATED:        frozenset({S.CLASSIFIED, S.RECON_PENDING, S.NEEDS_HUMAN}),
    S.CLASSIFIED:      frozenset({S.POLICY_SELECTED, S.NEEDS_HUMAN}),
    S.POLICY_SELECTED: frozenset({S.CONSTRAINED, S.NEEDS_HUMAN}),
    S.CONSTRAINED:     frozenset({S.IN_FLIGHT, S.DEFERRED_TO_CREDIT_CYCLE, S.NEEDS_HUMAN,
                                  S.TERMINATED, S.RECON_PENDING}),
    S.DEFERRED_TO_CREDIT_CYCLE: frozenset(),
    S.IN_FLIGHT:       frozenset({S.RECOVERED, S.RECON_PENDING, S.POLICY_SELECTED,
                                  S.EXHAUSTED, S.TERMINATED}),
    # only the reconciler moves a case out of RECON_PENDING
    S.RECON_PENDING:   frozenset({S.RECOVERED, S.DUPLICATE_CHARGE_PREVENTED,
                                  S.POLICY_SELECTED, S.NEEDS_HUMAN}),
    # a human decision is the only way out
    S.NEEDS_HUMAN:     frozenset({S.CONSTRAINED, S.TERMINATED}),
    S.RECOVERED:                  frozenset(),
    S.DUPLICATE_CHARGE_PREVENTED: frozenset(),
    S.EXHAUSTED:                  frozenset(),
    S.TERMINATED:                 frozenset(),
}


def can_transition(frm: S, to: S) -> bool:
    return to in ALLOWED.get(frm, frozenset())


def assert_transition(frm: S, to: S) -> None:
    if not can_transition(frm, to):
        raise InvalidStateTransition(
            f"Cannot transition {frm} -> {to}",
            {"state_from": str(frm), "state_to": str(to)},
        )
