from __future__ import annotations
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.audit.hashchain import GENESIS, chain_body, compute_hash
from app.db.models import AuditLog

_PAGE = 1000


async def verify_chain(session: AsyncSession) -> dict:
    """Walks the log recomputing every hash. Returns the first divergent seq or OK."""
    prev = GENESIS
    checked = 0
    last_seq = 0
    offset = 0
    while True:
        rows = (await session.execute(
            select(AuditLog).order_by(AuditLog.seq).offset(offset).limit(_PAGE)
        )).scalars().all()
        if not rows:
            break
        for r in rows:
            body = chain_body({
                "entry_id": r.entry_id, "run_id": r.run_id, "case_id": r.case_id,
                "case_ref": r.case_ref, "entry_type": r.entry_type, "node": r.node,
                "state_from": r.state_from, "state_to": r.state_to, "rule_id": r.rule_id,
                "policy_version": r.policy_version, "model_id": r.model_id,
                "classifier_tier": r.classifier_tier, "idempotency_key": r.idempotency_key,
                "amount_minor": r.amount_minor, "outcome": r.outcome,
                "input_snapshot": r.input_snapshot, "output_snapshot": r.output_snapshot,
                "occurred_at": r.occurred_at,
            })
            if r.prev_hash != prev or compute_hash(prev, body) != r.entry_hash:
                return {"ok": False, "first_divergent_seq": r.seq,
                        "verified_through": last_seq, "entries_checked": checked}
            prev, last_seq, checked = r.entry_hash, r.seq, checked + 1
        offset += _PAGE
    return {"ok": True, "first_divergent_seq": None,
            "verified_through": last_seq, "entries_checked": checked}


async def chain_status(session: AsyncSession) -> dict:
    total = (await session.execute(select(func.count(AuditLog.seq)))).scalar_one()
    head = (await session.execute(select(func.max(AuditLog.seq)))).scalar_one()
    return {"ok": True, "seq_head": head or 0, "total_entries": total}
