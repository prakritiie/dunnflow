"""Append-only, hash-chained audit writer.

Two invariants:
  * The audit write happens in the CALLER's transaction. If audit fails, the
    state transition does not happen.
  * A Postgres advisory lock serialises read-tail -> compute -> insert so
    concurrent writers cannot fork the chain.
"""
from __future__ import annotations
import uuid
from datetime import datetime, timezone
from typing import Any
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
from app.audit.hashchain import GENESIS, chain_body, compute_hash
from app.db.models import AuditLog

_CHAIN_LOCK_KEY = 918273645          # arbitrary but fixed


async def append(
    session: AsyncSession,
    *,
    entry_type: str,
    run_id: uuid.UUID | None = None,
    case_id: uuid.UUID | None = None,
    case_ref: str | None = None,
    node: str | None = None,
    state_from: str | None = None,
    state_to: str | None = None,
    rule_id: str | None = None,
    policy_version: str | None = None,
    model_id: str | None = None,
    classifier_tier: str | None = None,
    idempotency_key: str | None = None,
    amount_minor: int | None = None,
    outcome: str | None = None,
    input_snapshot: dict[str, Any] | None = None,
    output_snapshot: dict[str, Any] | None = None,
    occurred_at: datetime | None = None,
) -> AuditLog:
    # serialise chain extension across concurrent writers
    await session.execute(text("SELECT pg_advisory_xact_lock(:k)"), {"k": _CHAIN_LOCK_KEY})

    tail = (await session.execute(
        select(AuditLog.entry_hash).order_by(AuditLog.seq.desc()).limit(1)
    )).scalar_one_or_none()
    prev_hash = tail or GENESIS

    entry = {
        "entry_id": uuid.uuid4(),
        "run_id": run_id, "case_id": case_id, "case_ref": case_ref,
        "entry_type": entry_type, "node": node,
        "state_from": state_from, "state_to": state_to,
        "rule_id": rule_id, "policy_version": policy_version,
        "model_id": model_id, "classifier_tier": classifier_tier,
        "idempotency_key": idempotency_key, "amount_minor": amount_minor,
        "outcome": outcome,
        "input_snapshot": input_snapshot or {},
        "output_snapshot": output_snapshot or {},
        "occurred_at": occurred_at or datetime.now(timezone.utc),
    }
    row = AuditLog(**entry, prev_hash=prev_hash, entry_hash=compute_hash(prev_hash, chain_body(entry)))
    session.add(row)
    await session.flush()
    return row
