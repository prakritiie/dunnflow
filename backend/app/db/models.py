from __future__ import annotations
import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    BigInteger, Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer,
    Numeric, String, Text, UniqueConstraint, func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


def _uuid() -> uuid.UUID:
    return uuid.uuid4()


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Run(Base):
    __tablename__ = "runs"
    id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=_uuid)
    seed: Mapped[int] = mapped_column(BigInteger, nullable=False)
    arm: Mapped[str] = mapped_column(String(32), nullable=False)
    n: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="QUEUED")
    policy_version: Mapped[str] = mapped_column(Text, nullable=False)
    taxonomy_version: Mapped[str] = mapped_column(Text, nullable=False)
    constraint_version: Mapped[str] = mapped_column(Text, nullable=False)
    llm_mode: Mapped[str] = mapped_column(String(16), nullable=False, default="STUB")
    faults_enabled: Mapped[dict | None] = mapped_column(JSONB)
    metrics: Mapped[dict | None] = mapped_column(JSONB)
    idempotency_key: Mapped[str | None] = mapped_column(Text, unique=True)
    error: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        CheckConstraint("arm in ('ARM_CONTROL','ARM_DUNNFLOW')", name="ck_run_arm"),
        CheckConstraint("n > 0 and n <= 2000", name="ck_run_n"),
        Index("ix_runs_status_started", "status", "started_at"),
        # prevents two concurrent runs corrupting a comparison
        Index("uq_runs_active", "seed", "arm", unique=True,
              postgresql_where=(status.in_(("QUEUED", "RUNNING")))),
    )


class Case(Base):
    __tablename__ = "cases"
    id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=_uuid)
    run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("runs.id", ondelete="CASCADE"), nullable=False)
    case_ref: Mapped[str] = mapped_column(String(32), nullable=False)
    merchant_id: Mapped[str] = mapped_column(String(64), nullable=False)
    obligation_ref: Mapped[str] = mapped_column(String(64), nullable=False)
    failure_class: Mapped[str] = mapped_column(String(48), nullable=False)
    failure_family: Mapped[str] = mapped_column(String(32), nullable=False)
    amount_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    rule_id: Mapped[str | None] = mapped_column(String(48))
    classifier_tier: Mapped[str | None] = mapped_column(String(4))
    classifier_conf: Mapped[float | None] = mapped_column(Numeric(4, 3))
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    money_locked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    attempts = relationship("Attempt", back_populates="case", cascade="all, delete-orphan")
    __table_args__ = (
        UniqueConstraint("run_id", "case_ref", name="uq_case_run_ref"),
        UniqueConstraint("run_id", "obligation_ref", name="uq_case_run_obligation"),
        CheckConstraint("amount_minor > 0", name="ck_case_amount_positive"),
        CheckConstraint("classifier_tier in ('T1','T2','T3','T4')", name="ck_case_tier"),
        Index("ix_cases_run_status", "run_id", "status"),
        Index("ix_cases_run_class", "run_id", "failure_class"),
        Index("ix_cases_cursor", "run_id", "created_at", "id"),
    )


class Attempt(Base):
    __tablename__ = "attempts"
    id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=_uuid)
    case_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"), nullable=False)
    attempt_index: Mapped[int] = mapped_column(Integer, nullable=False)
    action: Mapped[str] = mapped_column(String(32), nullable=False)
    # DB-level double-charge backstop, independent of Redis
    idempotency_key: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    outcome: Mapped[str] = mapped_column(String(16), nullable=False)
    amount_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    gateway_ref: Mapped[str | None] = mapped_column(String(64))
    error_raw: Mapped[dict | None] = mapped_column(JSONB)   # PII-masked before persistence
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    settled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    case = relationship("Case", back_populates="attempts")
    __table_args__ = (
        UniqueConstraint("case_id", "attempt_index", name="uq_attempt_case_index"),
        CheckConstraint("outcome in ('IN_FLIGHT','SUCCEEDED','FAILED','AMBIGUOUS')", name="ck_attempt_outcome"),
        Index("ix_attempts_case", "case_id", "attempt_index"),
    )


class CaseEvent(Base):
    __tablename__ = "case_events"
    id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=_uuid)
    case_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"), nullable=False)
    seq: Mapped[int] = mapped_column(Integer, nullable=False)
    node: Mapped[str] = mapped_column(String(32), nullable=False)
    state_from: Mapped[str | None] = mapped_column(String(32))
    state_to: Mapped[str | None] = mapped_column(String(32))
    rule_id: Mapped[str | None] = mapped_column(String(48))
    note: Mapped[str | None] = mapped_column(Text)
    flags: Mapped[dict | None] = mapped_column(JSONB)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    __table_args__ = (
        UniqueConstraint("case_id", "seq", name="uq_event_case_seq"),
        Index("ix_events_case_seq", "case_id", "seq"),
    )


class ConstraintEvaluation(Base):
    __tablename__ = "constraint_evaluations"
    id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=_uuid)
    case_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"), nullable=False)
    run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("runs.id", ondelete="CASCADE"), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    constraint_id: Mapped[str] = mapped_column(String(48), nullable=False)
    decision: Mapped[str] = mapped_column(String(8), nullable=False)
    reason: Mapped[str | None] = mapped_column(Text)
    reschedule_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    proposed_action: Mapped[str] = mapped_column(String(32), nullable=False)
    rule_id: Mapped[str | None] = mapped_column(String(48))
    failure_class: Mapped[str | None] = mapped_column(String(48))
    unverified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    constraint_version: Mapped[str] = mapped_column(Text, nullable=False)
    evaluated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    __table_args__ = (
        CheckConstraint("decision in ('ALLOW','DENY','SKIPPED')", name="ck_ce_decision"),
        Index("ix_ce_run_denies", "run_id", "constraint_id", postgresql_where=(decision == "DENY")),
        Index("ix_ce_case_pos", "case_id", "position"),
        Index("ix_ce_run_decision", "run_id", "decision"),
    )


class AuditLog(Base):
    __tablename__ = "audit_log"
    seq: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    entry_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), unique=True, default=_uuid)
    run_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("runs.id", ondelete="CASCADE"))
    case_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True))
    case_ref: Mapped[str | None] = mapped_column(String(32))
    entry_type: Mapped[str] = mapped_column(String(40), nullable=False)
    node: Mapped[str | None] = mapped_column(String(32))
    state_from: Mapped[str | None] = mapped_column(String(32))
    state_to: Mapped[str | None] = mapped_column(String(32))
    rule_id: Mapped[str | None] = mapped_column(String(48))
    policy_version: Mapped[str | None] = mapped_column(Text)
    # NULL on every DECISION row is the queryable proof of AI restraint
    model_id: Mapped[str | None] = mapped_column(Text)
    classifier_tier: Mapped[str | None] = mapped_column(String(4))
    idempotency_key: Mapped[str | None] = mapped_column(Text)
    amount_minor: Mapped[int | None] = mapped_column(BigInteger)
    outcome: Mapped[str | None] = mapped_column(String(32))
    input_snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    output_snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    prev_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    entry_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    __table_args__ = (
        Index("ix_audit_case", "case_id", "seq"),
        Index("ix_audit_type", "entry_type", "occurred_at"),
        Index("ix_audit_run", "run_id", "seq"),
    )


class ScheduledAction(Base):
    __tablename__ = "scheduled_actions"
    id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=_uuid)
    case_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"), nullable=False)
    run_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    directive: Mapped[dict] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="PENDING")
    claimed_by: Mapped[str | None] = mapped_column(String(64))
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    __table_args__ = (
        CheckConstraint("status in ('PENDING','CLAIMED','DONE','CANCELLED')", name="ck_sched_status"),
        Index("ix_sched_due", "run_at", postgresql_where=(status == "PENDING")),
    )


class ExceptionDecision(Base):
    __tablename__ = "exception_decisions"
    id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=_uuid)
    case_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"), nullable=False, unique=True)
    decision: Mapped[str] = mapped_column(String(16), nullable=False)
    actor: Mapped[str] = mapped_column(String(64), nullable=False)
    reason: Mapped[str | None] = mapped_column(Text)
    confirmed_case_ref: Mapped[str | None] = mapped_column(String(32))
    decided_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    __table_args__ = (CheckConstraint("decision in ('APPROVED','REJECTED')", name="ck_exdec"),)


class ChaosInjection(Base):
    __tablename__ = "chaos_injections"
    id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=_uuid)
    run_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True))
    fault_id: Mapped[str] = mapped_column(String(48), nullable=False)
    state: Mapped[str] = mapped_column(String(16), nullable=False)
    armed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    fired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    effect_summary: Mapped[dict | None] = mapped_column(JSONB)
    __table_args__ = (
        CheckConstraint("state in ('ARMED','FIRED','EXPIRED','DISARMED')", name="ck_chaos_state"),
        Index("ix_chaos_fault", "fault_id", "state"),
    )


class DeadLetter(Base):
    __tablename__ = "dead_letters"
    id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=_uuid)
    run_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True))
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    error: Mapped[str] = mapped_column(Text, nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
