from __future__ import annotations
from enum import StrEnum


class Terminality(StrEnum):
    SOFT = "SOFT"
    HARD = "HARD"
    AMBIGUOUS = "AMBIGUOUS"
    PROHIBITED = "PROHIBITED"


class ActionType(StrEnum):
    RETRY_SAME_RAIL = "RETRY_SAME_RAIL"
    RETRY_ALT_RAIL = "RETRY_ALT_RAIL"
    REQUEST_NEW_INSTRUMENT = "REQUEST_NEW_INSTRUMENT"
    NUDGE_CUSTOMER = "NUDGE_CUSTOMER"
    RECONCILE = "RECONCILE"
    ESCALATE_HUMAN = "ESCALATE_HUMAN"
    HOLD = "HOLD"
    TERMINATE = "TERMINATE"


#: Actions that cause an irreversible outbound money movement.
MONEY_MOVING: frozenset[ActionType] = frozenset({ActionType.RETRY_SAME_RAIL, ActionType.RETRY_ALT_RAIL})
#: Actions that contact the customer but move no money.
COMMS_ACTIONS: frozenset[ActionType] = frozenset({ActionType.REQUEST_NEW_INSTRUMENT, ActionType.NUDGE_CUSTOMER})


class Backoff(StrEnum):
    NONE = "NONE"
    FIXED_SHORT = "FIXED_SHORT"
    EXPONENTIAL_JITTER = "EXPONENTIAL_JITTER"
    DEFER_CREDIT_CYCLE = "DEFER_CREDIT_CYCLE"
    ISSUER_HEALTH_GATED = "ISSUER_HEALTH_GATED"


class CaseStatus(StrEnum):
    RECEIVED = "RECEIVED"
    HYDRATED = "HYDRATED"
    CLASSIFIED = "CLASSIFIED"
    POLICY_SELECTED = "POLICY_SELECTED"
    CONSTRAINED = "CONSTRAINED"
    #: Deferred by the policy/constraint layer (e.g. issuer sentinel, circuit
    #: breaker, velocity limit) rather than executed now. Counted explicitly in
    #: run metrics so a deferred case never silently vanishes from the totals.
    DEFERRED_TO_CREDIT_CYCLE = "DEFERRED_TO_CREDIT_CYCLE"
    IN_FLIGHT = "IN_FLIGHT"
    RECON_PENDING = "RECON_PENDING"
    RECOVERED = "RECOVERED"
    DUPLICATE_CHARGE_PREVENTED = "DUPLICATE_CHARGE_PREVENTED"
    EXHAUSTED = "EXHAUSTED"
    TERMINATED = "TERMINATED"
    NEEDS_HUMAN = "NEEDS_HUMAN"


TERMINAL_STATUSES: frozenset[CaseStatus] = frozenset({
    CaseStatus.RECOVERED, CaseStatus.DUPLICATE_CHARGE_PREVENTED,
    CaseStatus.EXHAUSTED, CaseStatus.TERMINATED, CaseStatus.DEFERRED_TO_CREDIT_CYCLE,
})


class Outcome(StrEnum):
    IN_FLIGHT = "IN_FLIGHT"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    #: A timeout is NEVER a failure. Collapsing this into FAILED is the bug
    #: that double-charges customers.
    AMBIGUOUS = "AMBIGUOUS"


class ReconResolution(StrEnum):
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    UNRESOLVED = "UNRESOLVED"


class Decision(StrEnum):
    ALLOW = "ALLOW"
    DENY = "DENY"
    SKIPPED = "SKIPPED"


class ClassifierTier(StrEnum):
    T1_EXACT = "T1"
    T2_VECTOR = "T2"
    T3_LLM = "T3"
    T4_FALLBACK = "T4"


class Arm(StrEnum):
    CONTROL = "ARM_CONTROL"
    DUNNFLOW = "ARM_DUNNFLOW"


class RunStatus(StrEnum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    COMPLETE = "COMPLETE"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
