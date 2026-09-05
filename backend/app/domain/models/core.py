from __future__ import annotations
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field, model_validator
from app.domain.models.enums import (
    ActionType, Backoff, CaseStatus, ClassifierTier, Decision, Outcome, ReconResolution,
)

_STRICT = ConfigDict(extra="forbid", frozen=True)


class FailureClass(BaseModel):
    model_config = _STRICT
    code: str
    family: str
    terminality: str
    retry_eligible: bool
    requires_customer_action: bool = False
    default_max_attempts: int = 0
    default_backoff: Backoff = Backoff.NONE
    confidence_floor: float = 0.0
    escalate_immediately: bool = False
    recoverable: bool = False


class Classification(BaseModel):
    model_config = _STRICT
    code: str
    confidence: float = Field(ge=0.0, le=1.0)
    tier: ClassifierTier
    evidence_span: str | None = None
    taxonomy_version: str


class CaseView(BaseModel):
    """Immutable snapshot handed to the pure policy engine."""
    model_config = _STRICT
    case_ref: str
    merchant_id: str
    obligation_ref: str
    amount_minor: int = Field(gt=0)
    status: CaseStatus
    attempt_count: int = Field(ge=0)
    failure_class: str | None = None


class AttemptView(BaseModel):
    model_config = _STRICT
    attempt_index: int
    action: ActionType
    outcome: Outcome
    started_at: datetime


class IssuerHealth(BaseModel):
    model_config = _STRICT
    issuer: str = "DEFAULT"
    ewma_success_rate: float = 1.0
    samples: int = 0


class Directive(BaseModel):
    """The output of the deterministic policy engine.

    rule_id + policy_version answer every future 'why did it do that?'.
    """
    model_config = _STRICT
    action: ActionType
    rule_id: str
    policy_version: str
    rationale_code: str
    backoff: Backoff = Backoff.NONE
    scheduled_at: datetime | None = None
    channel: str | None = None
    amount_minor: int | None = None
    attempt_index: int = 0
    attempts_remaining: int = 0
    requires_human_approval: bool = False

    @model_validator(mode="after")
    def _terminal_actions_carry_no_money(self):
        if self.action in (ActionType.TERMINATE, ActionType.ESCALATE_HUMAN) and self.backoff != Backoff.NONE:
            raise ValueError("terminal action must not carry a backoff")
        return self


class ConstraintResult(BaseModel):
    model_config = _STRICT
    position: int
    constraint_id: str
    decision: Decision
    reason: str | None = None
    reschedule_at: datetime | None = None
    unverified: bool = False


class ConstraintVerdict(BaseModel):
    model_config = _STRICT
    decision: Decision
    evaluated: tuple[ConstraintResult, ...]
    denied_by: str | None = None
    deny_reason: str | None = None
    reschedule_at: datetime | None = None
    constraint_version: str


class ExecutionResult(BaseModel):
    model_config = _STRICT
    outcome: Outcome
    idempotency_key: str
    gateway_ref: str | None = None
    error_raw: dict | None = None
    amount_minor: int | None = None


class ReconResult(BaseModel):
    model_config = _STRICT
    resolution: ReconResolution
    polls: int
    gateway_ref: str | None = None
    note: str = ""
