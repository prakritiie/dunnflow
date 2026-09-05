from __future__ import annotations
import asyncio, json, uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import rate_limit_write, require_token
from app.api.schemas import ApproveIn, CaseIntakeIn, KillSwitchIn, RejectIn, RunCreate
from app.audit.verify import chain_status, verify_chain
from app.chaos.faults import FAULTS
from app.chaos.injector import CHAOS
from app.core.config import settings
from app.core.exceptions import Conflict, Forbidden, NotFound
from app.db.models import (
    Attempt, AuditLog, Case, CaseEvent, ChaosInjection, ConstraintEvaluation,
    ExceptionDecision, Run,
)
from app.db.session import SessionLocal, get_session
from app.domain.constraints.kernel import all_constraints, constraint_version
from app.domain.models.enums import RunStatus
from app.domain.policy.engine import all_rules, policy_version
from app.domain.taxonomy.loader import load_taxonomy, taxonomy_version

router = APIRouter(prefix="/api/v1")
_STATE = {"kill_switch": False}
_PROGRESS: dict[str, dict] = {}
#: Strong references to in-flight background runs. asyncio.create_task returns a
#: task the event loop only weakly references: without this set the task can be
#: garbage-collected mid-run and its exception is never retrieved.
_TASKS: set = set()


def _spawn(coro, run_id):
    task = asyncio.create_task(coro)
    _TASKS.add(task)

    def _done(t: asyncio.Task):
        _TASKS.discard(t)
        if t.cancelled():
            return
        exc = t.exception()
        if exc is not None:
            from app.core.logging import log
            log.error("run_task_failed", run_id=str(run_id),
                      error=type(exc).__name__, message=str(exc))
    task.add_done_callback(_done)
    return task


# ───────────────────────── runs / simulation ─────────────────────────

async def _execute_background(run_id: uuid.UUID):
    from app.simulation.runner import execute_run
    async with SessionLocal() as s:
        run = await s.get(Run, run_id)
        run.status = RunStatus.RUNNING
        await s.commit()
        try:
            async def progress(i, m):
                _PROGRESS[str(run_id)] = {"processed": i, "total": run.n,
                                          "recovered": m["recovered"],
                                          "amount_minor": m["amount_recovered_minor"],
                                          "violations": m["compliance_violations"],
                                          "duplicates": m["duplicate_charges"]}
            m = await execute_run(s, run, progress=progress)
            run.metrics = m
            run.status = RunStatus.COMPLETE
            run.completed_at = datetime.now(timezone.utc)
            _PROGRESS[str(run_id)] = {"processed": run.n, "total": run.n,
                                      "recovered": m["recovered"],
                                      "amount_minor": m["amount_recovered_minor"],
                                      "violations": m["compliance_violations"],
                                      "duplicates": m["duplicate_charges"], "done": True}
            await s.commit()
        except Exception as exc:
            await s.rollback()
            from app.core.logging import log
            log.error("run_failed", run_id=str(run_id), error=type(exc).__name__, message=str(exc))
            run = await s.get(Run, run_id)
            if run is not None:
                run.status, run.error = RunStatus.FAILED, f"{type(exc).__name__}: {exc}"
                await s.commit()
            raise


@router.post("/runs", status_code=202, dependencies=[Depends(require_token), Depends(rate_limit_write)])
async def create_run(body: RunCreate, request: Request, s: AsyncSession = Depends(get_session),
                     idempotency_key: str | None = None):
    key = request.headers.get("Idempotency-Key")
    if key:
        prior = (await s.execute(select(Run).where(Run.idempotency_key == key))).scalar_one_or_none()
        if prior:
            return {"run_id": str(prior.id), "status": prior.status, "idempotent_replay": True}
    # The graph engine (app/graph/nodes.py) passes per-case execution context
    # through a module-level dict, not through the graph state itself. Two
    # batches executing concurrently in this one process interleave writes to
    # that shared dict and corrupt each other's attempt counters - which
    # surfaces downstream as a duplicate idempotency-key collision. Until the
    # engine carries its context through the graph state (or a contextvar),
    # only one run may be in flight at a time, regardless of seed or arm.
    active = (await s.execute(select(Run).where(
        Run.status.in_([RunStatus.QUEUED, RunStatus.RUNNING])))).scalar_one_or_none()
    if active:
        raise Conflict("Another run is already in progress - only one batch executes at a time",
                       {"run_id": str(active.id)})
    run = Run(seed=body.seed, arm=body.arm, n=body.n, status=RunStatus.QUEUED,
              policy_version=policy_version(), taxonomy_version=taxonomy_version(),
              constraint_version=constraint_version(), llm_mode=body.llm_mode,
              idempotency_key=key)
    s.add(run)
    await s.commit()
    _spawn(_execute_background(run.id), run.id)
    return {"run_id": str(run.id), "status": run.status, "idempotent_replay": False}


def _run_out(r: Run) -> dict:
    return {"id": str(r.id), "seed": r.seed, "arm": r.arm, "n": r.n, "status": r.status,
            "policy_version": r.policy_version, "taxonomy_version": r.taxonomy_version,
            "constraint_version": r.constraint_version, "llm_mode": r.llm_mode,
            "metrics": r.metrics, "error": r.error,
            "started_at": r.started_at, "completed_at": r.completed_at,
            "duration_seconds": int((r.completed_at - r.started_at).total_seconds())
                                 if r.completed_at else None}


@router.post("/cases/intake")
async def intake_case(body: CaseIntakeIn, s: AsyncSession = Depends(get_session)):
    """Dry-run diagnostic preview: classify + policy-evaluate a hand-entered case.

    This deliberately does NOT invoke the executor, the constraint kernel, or
    the PSP - no attempt is made and no money moves. It exists so an operator
    can see what the engine WOULD do before a case is ever ingested for real.
    Because no attempt occurs, "recovered" must always be false here; claiming
    otherwise would mean reporting money recovered with no execution behind it.
    """
    from app.domain.models.core import CaseView
    from app.domain.models.enums import CaseStatus
    from app.domain.policy.engine import evaluate
    from app.domain.taxonomy.loader import get_class
    from app.llm.classifier import classify

    now = datetime.now(timezone.utc)
    case_ref = f"CASE-{now.strftime('%Y%m%d%H%M%S')}-{abs(hash(body.obligation_ref)) % 10000:04d}"
    classification, meta = classify(
        error_source=body.failure_source,
        error_step=body.failure_step,
        error_reason=body.failure_reason,
        error_description=body.error_description,
        customer_tokens=body.customer_tokens,
    )
    case_view = CaseView(
        case_ref=case_ref,
        merchant_id=body.merchant_id,
        obligation_ref=body.obligation_ref,
        amount_minor=body.amount_minor,
        status=CaseStatus.RECEIVED,
        attempt_count=body.retry_count,
        failure_class=classification.code,
    )
    directive = evaluate(
        classification=classification,
        case=case_view,
        history=(),
        issuer_health={"issuer": "issuer", "ewma_success_rate": 0.87, "samples": 42},
        now=now,
    )

    run = Run(
        seed=abs(hash(body.obligation_ref)) % 10_000_000,
        arm="ARM_DUNNFLOW",
        n=1,
        status=RunStatus.COMPLETE,
        policy_version=policy_version(),
        taxonomy_version=taxonomy_version(),
        constraint_version=constraint_version(),
        llm_mode=settings.LLM_MODE,
        metrics={
            "cases": 1,
            # no attempt occurred in a dry run - recovered is always false here,
            # regardless of which directive the policy engine would have chosen
            "recovered": 0,
            "amount_recovered_minor": 0,
            "network_attempts": 0,
            "duplicate_charges": 0,
            "compliance_violations": 0,
            "escalated": int(directive.requires_human_approval),
            "hard_class_retries": 0,
            "duplicate_charge_prevented": 0,
            "deferred": 0,
            "deferred_amount_minor": 0,
            "tiers": {str(classification.tier): 1},
            "status_counts": {str(CaseStatus.POLICY_SELECTED): 1},
        },
        started_at=now,
        completed_at=now,
    )
    s.add(run)
    await s.commit()

    failure_family = get_class(classification.code).family
    case = Case(
        run_id=run.id,
        case_ref=case_ref,
        merchant_id=body.merchant_id,
        obligation_ref=body.obligation_ref,
        failure_class=classification.code,
        failure_family=failure_family,
        amount_minor=body.amount_minor,
        status=str(CaseStatus.POLICY_SELECTED),
        rule_id=directive.rule_id,
        classifier_tier=str(classification.tier),
        classifier_conf=float(classification.confidence),
        attempt_count=body.retry_count,
        money_locked=False,
    )
    s.add(case)
    await s.flush()

    s.add_all([
        CaseEvent(case_id=case.id, seq=1, node="ingest", state_from=None, state_to=str(CaseStatus.RECEIVED),
                 rule_id=None, note="manual intake accepted for review", flags={"manual": True}),
        CaseEvent(case_id=case.id, seq=2, node="classify", state_from=str(CaseStatus.RECEIVED),
                 state_to=str(CaseStatus.CLASSIFIED), rule_id=directive.rule_id,
                 note=f"{classification.code} classified with confidence {classification.confidence:.2f}", flags={"confidence": round(float(classification.confidence), 4)}),
        CaseEvent(case_id=case.id, seq=3, node="policy", state_from=str(CaseStatus.CLASSIFIED),
                 state_to=str(CaseStatus.POLICY_SELECTED), rule_id=directive.rule_id,
                 note=f"policy selected {directive.action}", flags={"action": str(directive.action), "requires_human_approval": directive.requires_human_approval}),
    ])

    # Recorded in the hash chain so a dry-run preview is never invisible to the
    # audit trail just because it took a thinner code path than a batch run.
    from app.audit import writer
    await writer.append(
        s, entry_type="INTAKE_DRY_RUN", run_id=run.id, case_id=case.id,
        case_ref=case_ref, node="intake", rule_id=directive.rule_id,
        policy_version=directive.policy_version, model_id=None,
        classifier_tier=str(classification.tier), amount_minor=body.amount_minor,
        state_to=str(CaseStatus.POLICY_SELECTED),
        output_snapshot={"action": str(directive.action), "rationale": directive.rationale_code,
                         "dry_run": True, "executed": False},
    )
    await s.commit()

    action_value = str(directive.action)
    summary = (
        f"{classification.code} classified as {classification.tier} "
        f"with {classification.confidence:.2f} confidence; policy would select {action_value} via {directive.rule_id} "
        "(dry run - no attempt executed)."
    )
    return {
        "case_ref": case_ref,
        "status": "DRY_RUN_PREVIEW",
        "dry_run": True,
        "summary": summary,
        "llm_mode": settings.LLM_MODE,
        "classification": {
            "code": classification.code,
            "confidence": round(float(classification.confidence), 4),
            "tier": str(classification.tier),
            "taxonomy_version": classification.taxonomy_version,
            "evidence_span": classification.evidence_span,
        },
        "decision": {
            "action": action_value,
            "rule_id": directive.rule_id,
            "policy_version": directive.policy_version,
            "rationale_code": directive.rationale_code,
            "requires_human_approval": directive.requires_human_approval,
            "scheduled_at": directive.scheduled_at.isoformat() if directive.scheduled_at else None,
            "attempts_remaining": directive.attempts_remaining,
        },
        "sanitizer": {
            "masked_text": meta.get("masked_text", ""),
            "sanitizer_summary": meta.get("sanitizer", {}),
        },
        "taxonomy": {
            "terminality": get_class(classification.code).terminality,
            "recoverable": get_class(classification.code).recoverable,
        },
    }


@router.get("/runs")
async def list_runs(limit: int = Query(20, ge=1, le=100), s: AsyncSession = Depends(get_session)):
    rows = (await s.execute(select(Run).order_by(Run.started_at.desc()).limit(limit))).scalars().all()
    return {"items": [_run_out(r) for r in rows]}


@router.get("/runs/latest")
async def latest_run(arm: str = "ARM_DUNNFLOW", s: AsyncSession = Depends(get_session)):
    # n=1 rows are dry-run intake previews (see intake_case) - they satisfy the
    # Case->Run FK but are not a batch run and must never be picked as "latest".
    r = (await s.execute(select(Run).where(
            Run.arm == arm, Run.status == RunStatus.COMPLETE, Run.n > 1)
         .order_by(Run.started_at.desc()).limit(1))).scalar_one_or_none()
    if not r:
        raise NotFound("No completed run for this arm")
    return _run_out(r)


async def _get_run(s, run_id) -> Run:
    try:
        r = await s.get(Run, uuid.UUID(str(run_id)))
    except ValueError:
        raise NotFound("Run not found")
    if not r:
        raise NotFound("Run not found")
    return r


@router.get("/runs/{run_id}")
async def get_run(run_id: str, s: AsyncSession = Depends(get_session)):
    return _run_out(await _get_run(s, run_id))


@router.get("/runs/{run_id}/comparison")
async def comparison(run_id: str, s: AsyncSession = Depends(get_session)):
    run = await _get_run(s, run_id)
    other_arm = "ARM_CONTROL" if run.arm == "ARM_DUNNFLOW" else "ARM_DUNNFLOW"
    other = (await s.execute(select(Run).where(
        Run.seed == run.seed, Run.arm == other_arm, Run.status == RunStatus.COMPLETE)
        .order_by(Run.started_at.desc()).limit(1))).scalar_one_or_none()
    def pack(r):
        if r is None or not r.metrics:
            return None
        m = r.metrics
        return {"arm": r.arm, "run_id": str(r.id), "cases": m["cases"],
                "recovered": m["recovered"], "recovery_rate": m["recovered"] / max(m["cases"], 1),
                "amount_recovered_minor": m["amount_recovered_minor"],
                "network_attempts": m["network_attempts"],
                "duplicate_charges": m["duplicate_charges"],
                "compliance_violations": m["compliance_violations"],
                "hard_class_retries": m.get("hard_class_retries", 0),
                "escalated": m.get("escalated", 0),
                "duplicate_charge_prevented": m.get("duplicate_charge_prevented", 0),
                "deferred": m.get("deferred", 0),
                "deferred_amount_minor": m.get("deferred_amount_minor", 0),
                "attempt_efficiency_minor_per_call":
                    m["amount_recovered_minor"] / max(m["network_attempts"], 1),
                "tiers": m.get("tiers", {})}
    a, b = (run, other) if run.arm == "ARM_DUNNFLOW" else (other, run)
    return {"seed": run.seed, "dunnflow": pack(a), "control": pack(b)}


@router.get("/runs/{run_id}/distribution")
async def distribution(run_id: str, s: AsyncSession = Depends(get_session)):
    run = await _get_run(s, run_id)
    rows = (await s.execute(
        select(Case.failure_class, Case.failure_family, func.count())
        .where(Case.run_id == run.id).group_by(Case.failure_class, Case.failure_family)
        .order_by(func.count().desc()))).all()
    tax, _fams, _v, _sha = load_taxonomy()
    total = sum(r[2] for r in rows) or 1
    return [{"code": c, "family": f, "count": n, "pct": n / total,
             "recoverable": tax[c].recoverable if c in tax else False} for c, f, n in rows]


@router.get("/runs/{run_id}/series")
async def series(run_id: str, s: AsyncSession = Depends(get_session)):
    run = await _get_run(s, run_id)
    other_arm = "ARM_CONTROL" if run.arm == "ARM_DUNNFLOW" else "ARM_DUNNFLOW"
    other = (await s.execute(select(Run).where(
        Run.seed == run.seed, Run.arm == other_arm, Run.status == RunStatus.COMPLETE)
        .order_by(Run.started_at.desc()).limit(1))).scalar_one_or_none()
    def pts(r):
        if not r or not r.metrics:
            return []
        return r.metrics.get("series", [])
    a, b = (run, other) if run.arm == "ARM_DUNNFLOW" else (other, run)
    labels = [str(p["processed"]) for p in pts(a)] or [str(p["processed"]) for p in pts(b)]
    return {"labels": labels,
            "dunnflow": [p["recovered"] for p in pts(a)],
            "control": [p["recovered"] for p in pts(b)]}


@router.get("/runs/{run_id}/tiers")
async def tiers(run_id: str, s: AsyncSession = Depends(get_session)):
    run = await _get_run(s, run_id)
    t = (run.metrics or {}).get("tiers", {}) or {}
    total = sum(t.values()) or 1
    no_model = (t.get("T1", 0) + t.get("T2", 0)) / total
    return {"tiers": t, "total": total, "no_model_pct": no_model,
            "note": "T1 and T2 resolve without any model call"}


@router.get("/runs/{run_id}/stream")
async def stream(run_id: str):
    async def gen():
        last = None
        for _ in range(1200):
            p = _PROGRESS.get(str(run_id))
            if p and p != last:
                yield f"event: progress\ndata: {json.dumps(p)}\n\n"
                last = dict(p)
                if p.get("done"):
                    yield f"event: complete\ndata: {json.dumps(p)}\n\n"
                    return
            await asyncio.sleep(0.25)
        yield "event: error\ndata: {\"code\":\"STREAM_TIMEOUT\"}\n\n"
    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


# ───────────────────────── cases ─────────────────────────

def _case_out(c: Case) -> dict:
    return {"id": str(c.id), "case_ref": c.case_ref, "merchant_id": c.merchant_id,
            "obligation_ref": c.obligation_ref, "failure_class": c.failure_class,
            "failure_family": c.failure_family, "amount_minor": c.amount_minor,
            "status": c.status, "rule_id": c.rule_id, "classifier_tier": c.classifier_tier,
            "classifier_conf": float(c.classifier_conf) if c.classifier_conf is not None else None,
            "attempts": c.attempt_count, "created_at": c.created_at, "resolved_at": c.resolved_at}


@router.get("/runs/{run_id}/cases")
async def list_cases(run_id: str, status: str | None = None, failure_class: str | None = None,
                     limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0),
                     s: AsyncSession = Depends(get_session)):
    run = await _get_run(s, run_id)
    q = select(Case).where(Case.run_id == run.id)
    if status:
        q = q.where(Case.status == status)
    if failure_class:
        q = q.where(Case.failure_class == failure_class)
    total = (await s.execute(select(func.count()).select_from(q.subquery()))).scalar_one()
    rows = (await s.execute(q.order_by(Case.case_ref).offset(offset).limit(limit))).scalars().all()
    return {"items": [_case_out(c) for c in rows], "total": total,
            "limit": limit, "offset": offset}


async def _get_case(s, case_id, run_id: str | None = None) -> Case:
    """Resolve by UUID, or by case_ref scoped to a run.

    case_ref repeats across runs - CASE-0001 exists in every batch - so a bare
    ref is ambiguous. Without a run it resolves within the most recent completed
    ARM_DUNNFLOW run, which is what the console is displaying.
    """
    try:
        c = await s.get(Case, uuid.UUID(str(case_id)))
        if c:
            return c
    except ValueError:
        pass
    q = select(Case).where(Case.case_ref == str(case_id))
    if run_id:
        try:
            q = q.where(Case.run_id == uuid.UUID(run_id))
        except ValueError:
            raise NotFound("Run not found")
    else:
        latest = (await s.execute(select(Run.id).where(
            Run.arm == "ARM_DUNNFLOW", Run.status == RunStatus.COMPLETE)
            .order_by(Run.started_at.desc()).limit(1))).scalar_one_or_none()
        if latest:
            q = q.where(Case.run_id == latest)
    c = (await s.execute(q.order_by(Case.created_at.desc()).limit(1))).scalar_one_or_none()
    if not c:
        raise NotFound("Case not found")
    return c


@router.get("/cases/{case_id}")
async def get_case(case_id: str, run_id: str | None = None, s: AsyncSession = Depends(get_session)):
    return _case_out(await _get_case(s, case_id, run_id))


@router.get("/cases/{case_id}/timeline")
async def case_timeline(case_id: str, run_id: str | None = None, s: AsyncSession = Depends(get_session)):
    c = await _get_case(s, case_id, run_id)
    rows = (await s.execute(select(CaseEvent).where(CaseEvent.case_id == c.id)
                            .order_by(CaseEvent.seq))).scalars().all()
    return [{"seq": e.seq, "node": e.node, "state_from": e.state_from, "state_to": e.state_to,
             "rule_id": e.rule_id, "note": e.note, "flags": e.flags or {},
             "occurred_at": e.occurred_at} for e in rows]


@router.get("/cases/{case_id}/constraints")
async def case_constraints(case_id: str, run_id: str | None = None, s: AsyncSession = Depends(get_session)):
    c = await _get_case(s, case_id, run_id)
    rows = (await s.execute(select(ConstraintEvaluation)
                            .where(ConstraintEvaluation.case_id == c.id)
                            .order_by(ConstraintEvaluation.position))).scalars().all()
    return [{"position": r.position, "constraint_id": r.constraint_id, "decision": r.decision,
             "reason": r.reason, "unverified": r.unverified} for r in rows]


@router.get("/cases/{case_id}/attempts")
async def case_attempts(case_id: str, run_id: str | None = None, s: AsyncSession = Depends(get_session)):
    c = await _get_case(s, case_id, run_id)
    rows = (await s.execute(select(Attempt).where(Attempt.case_id == c.id)
                            .order_by(Attempt.attempt_index))).scalars().all()
    return [{"attempt_index": a.attempt_index, "action": a.action, "outcome": a.outcome,
             "idempotency_key": a.idempotency_key, "gateway_ref": a.gateway_ref,
             "amount_minor": a.amount_minor, "error_raw": a.error_raw,
             "started_at": a.started_at, "settled_at": a.settled_at} for a in rows]


# ───────────────────────── refusals ─────────────────────────

@router.get("/runs/{run_id}/refusals")
async def refusals(run_id: str, constraint_id: str | None = None, rule_id: str | None = None,
                   limit: int = Query(100, ge=1, le=500), s: AsyncSession = Depends(get_session)):
    run = await _get_run(s, run_id)
    q = (select(ConstraintEvaluation, Case.case_ref)
         .join(Case, Case.id == ConstraintEvaluation.case_id)
         .where(ConstraintEvaluation.run_id == run.id, ConstraintEvaluation.decision == "DENY"))
    if constraint_id:
        q = q.where(ConstraintEvaluation.constraint_id == constraint_id)
    if rule_id:
        q = q.where(ConstraintEvaluation.rule_id == rule_id)
    rows = (await s.execute(q.order_by(ConstraintEvaluation.evaluated_at).limit(limit))).all()
    return [{"case_ref": ref, "constraint_id": r.constraint_id, "rule_id": r.rule_id,
             "failure_class": r.failure_class, "reason": r.reason,
             "proposed_action": r.proposed_action, "unverified": r.unverified,
             "evaluated_at": r.evaluated_at} for r, ref in rows]


@router.get("/runs/{run_id}/refusals/summary")
async def refusals_summary(run_id: str, s: AsyncSession = Depends(get_session)):
    run = await _get_run(s, run_id)
    rows = (await s.execute(
        select(ConstraintEvaluation.constraint_id, func.count())
        .where(ConstraintEvaluation.run_id == run.id, ConstraintEvaluation.decision == "DENY")
        .group_by(ConstraintEvaluation.constraint_id))).all()
    counts = {c: n for c, n in rows}
    # every constraint is listed, including zero-count ones - a partial list
    # invites the question of what is missing
    return [{"constraint_id": c["id"], "position": c["position"],
             "refusals": counts.get(c["id"], 0), "unverified": bool(c.get("unverified", False)),
             "description": c["description"]}
            for c in sorted(all_constraints(), key=lambda x: x["position"])]


# ───────────────────────── exceptions ─────────────────────────

@router.get("/runs/{run_id}/exceptions")
async def exceptions(run_id: str, s: AsyncSession = Depends(get_session)):
    run = await _get_run(s, run_id)
    rows = (await s.execute(select(Case).where(Case.run_id == run.id,
                                               Case.status == "NEEDS_HUMAN")
                            .order_by(Case.amount_minor.desc()))).scalars().all()
    out = []
    for c in rows:
        dec = (await s.execute(select(ExceptionDecision)
                               .where(ExceptionDecision.case_id == c.id))).scalar_one_or_none()
        ev = (await s.execute(select(CaseEvent).where(CaseEvent.case_id == c.id)
                              .order_by(CaseEvent.seq.desc()).limit(1))).scalar_one_or_none()
        out.append({**_case_out(c), "reason": ev.note if ev else None,
                    "decided": dec.decision if dec else None})
    return out


@router.post("/exceptions/{case_id}/approve",
             dependencies=[Depends(require_token), Depends(rate_limit_write)])
async def approve(case_id: str, body: ApproveIn, s: AsyncSession = Depends(get_session)):
    c = await _get_case(s, case_id)
    if c.status != "NEEDS_HUMAN":
        raise Conflict("Case is not awaiting human review", {"status": c.status})
    prior = (await s.execute(select(ExceptionDecision)
                             .where(ExceptionDecision.case_id == c.id))).scalar_one_or_none()
    if prior:
        raise Conflict("Case already decided", {"decision": prior.decision})
    # typed confirmation must match the case's own reference
    if body.confirmed_case_ref != c.case_ref:
        raise Conflict("Confirmation does not match case reference",
                       {"expected": c.case_ref, "received": body.confirmed_case_ref})
    if _STATE["kill_switch"]:
        raise Forbidden("Kill switch armed - money movement halted")
    s.add(ExceptionDecision(case_id=c.id, decision="APPROVED", actor=body.actor,
                            confirmed_case_ref=body.confirmed_case_ref))
    # approval resumes the graph at CONSTRAINED - it does NOT bypass constraints
    c.status = "CONSTRAINED"
    seq = (await s.execute(select(func.coalesce(func.max(CaseEvent.seq), 0))
                           .where(CaseEvent.case_id == c.id))).scalar_one()
    s.add(CaseEvent(case_id=c.id, seq=seq + 1, node="hitl", state_from="NEEDS_HUMAN",
                    state_to="CONSTRAINED", rule_id=c.rule_id,
                    note=f"approved by {body.actor} - constraints will re-run at execution"))
    from app.audit import writer
    await writer.append(s, entry_type="HITL_APPROVED", run_id=c.run_id, case_id=c.id,
                        case_ref=c.case_ref, node="hitl", state_from="NEEDS_HUMAN",
                        state_to="CONSTRAINED", model_id=None,
                        output_snapshot={"actor": body.actor})
    await s.commit()
    return {"case_ref": c.case_ref, "status": c.status, "decision": "APPROVED"}


@router.post("/exceptions/{case_id}/reject",
             dependencies=[Depends(require_token), Depends(rate_limit_write)])
async def reject(case_id: str, body: RejectIn, s: AsyncSession = Depends(get_session)):
    c = await _get_case(s, case_id)
    if c.status != "NEEDS_HUMAN":
        raise Conflict("Case is not awaiting human review", {"status": c.status})
    prior = (await s.execute(select(ExceptionDecision)
                             .where(ExceptionDecision.case_id == c.id))).scalar_one_or_none()
    if prior:
        raise Conflict("Case already decided", {"decision": prior.decision})
    s.add(ExceptionDecision(case_id=c.id, decision="REJECTED", actor=body.actor, reason=body.reason))
    c.status = "TERMINATED"
    c.resolved_at = datetime.now(timezone.utc)
    seq = (await s.execute(select(func.coalesce(func.max(CaseEvent.seq), 0))
                           .where(CaseEvent.case_id == c.id))).scalar_one()
    s.add(CaseEvent(case_id=c.id, seq=seq + 1, node="hitl", state_from="NEEDS_HUMAN",
                    state_to="TERMINATED", note=f"rejected by {body.actor}: {body.reason}"))
    from app.audit import writer
    await writer.append(s, entry_type="HITL_REJECTED", run_id=c.run_id, case_id=c.id,
                        case_ref=c.case_ref, node="hitl", state_from="NEEDS_HUMAN",
                        state_to="TERMINATED", model_id=None,
                        output_snapshot={"actor": body.actor, "reason": body.reason})
    await s.commit()
    return {"case_ref": c.case_ref, "status": c.status, "decision": "REJECTED"}


# ───────────────────────── audit ─────────────────────────

@router.get("/runs/{run_id}/audit")
async def audit_entries(run_id: str, entry_type: str | None = None,
                        limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0),
                        s: AsyncSession = Depends(get_session)):
    run = await _get_run(s, run_id)
    q = select(AuditLog).where(AuditLog.run_id == run.id)
    if entry_type:
        q = q.where(AuditLog.entry_type == entry_type)
    total = (await s.execute(select(func.count()).select_from(q.subquery()))).scalar_one()
    rows = (await s.execute(q.order_by(AuditLog.seq).offset(offset).limit(limit))).scalars().all()
    return {"total": total, "items": [
        {"seq": r.seq, "case_ref": r.case_ref, "entry_type": r.entry_type, "node": r.node,
         "rule_id": r.rule_id, "model_id": r.model_id, "state_to": r.state_to,
         "prev_hash": r.prev_hash[:8] + "...", "hash": r.entry_hash[:8] + "...",
         "occurred_at": r.occurred_at} for r in rows]}


@router.get("/audit/status")
async def audit_status(s: AsyncSession = Depends(get_session)):
    st = await chain_status(s)
    # the restraint claim, as a query
    n = (await s.execute(text(
        "SELECT count(*) FROM audit_log WHERE entry_type='DECISION' AND model_id IS NOT NULL"
    ))).scalar_one()
    st["decisions_with_model"] = n
    return st


@router.post("/audit/verify", dependencies=[Depends(require_token), Depends(rate_limit_write)])
async def audit_verify(s: AsyncSession = Depends(get_session)):
    return await verify_chain(s)


# ───────────────────────── chaos ─────────────────────────

@router.get("/chaos/faults")
async def chaos_faults():
    return [{**f, "state": CHAOS.state(f["id"])} for f in FAULTS]


@router.post("/chaos/{fault_id}/arm", dependencies=[Depends(require_token), Depends(rate_limit_write)])
async def chaos_arm(fault_id: str, s: AsyncSession = Depends(get_session)):
    CHAOS.arm(fault_id)
    s.add(ChaosInjection(fault_id=fault_id, state="ARMED",
                         armed_at=datetime.now(timezone.utc)))
    await s.commit()
    return {"fault_id": fault_id, "state": CHAOS.state(fault_id)}


@router.post("/chaos/{fault_id}/fire", dependencies=[Depends(require_token), Depends(rate_limit_write)])
async def chaos_fire(fault_id: str, s: AsyncSession = Depends(get_session)):
    CHAOS.fire(fault_id)          # 409 if not armed - two-step enforced server-side
    s.add(ChaosInjection(fault_id=fault_id, state="FIRED",
                         fired_at=datetime.now(timezone.utc)))
    await s.commit()
    return {"fault_id": fault_id, "state": CHAOS.state(fault_id)}


@router.post("/chaos/{fault_id}/disarm", dependencies=[Depends(require_token)])
async def chaos_disarm(fault_id: str):
    CHAOS.disarm(fault_id)
    return {"fault_id": fault_id, "state": CHAOS.state(fault_id)}


@router.get("/chaos/injections")
async def chaos_injections(s: AsyncSession = Depends(get_session)):
    rows = (await s.execute(select(ChaosInjection)
                            .order_by(ChaosInjection.id.desc()).limit(50))).scalars().all()
    return [{"fault_id": r.fault_id, "state": r.state,
             "armed_at": r.armed_at, "fired_at": r.fired_at} for r in rows]


# ───────────────────────── policy ─────────────────────────

@router.get("/policy/taxonomy")
async def policy_taxonomy():
    classes, families, ver, sha = load_taxonomy()
    out: dict[str, list] = {f: [] for f in families}
    rules_by_class: dict[str, str] = {}
    for r in all_rules():
        cl = r.get("match", {}).get("class")
        if cl and cl not in rules_by_class:
            rules_by_class[cl] = r["rule_id"]
    for c in classes.values():
        out[c.family].append({
            "code": c.code, "terminality": c.terminality,
            "retry_eligible": c.retry_eligible,
            "hard_class": c.terminality == "HARD",
            "prohibited": c.terminality == "PROHIBITED",
            "max_attempts": c.default_max_attempts, "backoff": c.default_backoff,
            "rule_id": rules_by_class.get(c.code), "recoverable": c.recoverable})
    return {"version": taxonomy_version(),
            "families": [{"family": f, "description": families[f], "classes": out[f]}
                         for f in families if out[f]]}


@router.get("/policy/rules")
async def policy_rules():
    return {"version": policy_version(), "rules": all_rules()}


@router.get("/policy/constraints")
async def policy_constraints():
    return {"version": constraint_version(), "constraints": all_constraints()}


# ───────────────────────── system ─────────────────────────

@router.get("/health")
async def health(s: AsyncSession = Depends(get_session)):
    db = redis_ok = False
    try:
        await s.execute(text("SELECT 1")); db = True
    except Exception:
        pass
    try:
        from app.executors.idempotency import STORE
        r = await STORE.client(); await r.ping(); redis_ok = True
    except Exception:
        pass
    return {"status": "ok" if (db and redis_ok) else "degraded",
            "postgres": db, "redis": redis_ok}


@router.get("/system/status")
async def system_status(s: AsyncSession = Depends(get_session)):
    st = await chain_status(s)
    return {"kill_switch": _STATE["kill_switch"], "chain": st,
            "env": "local", "test_mode": True,
            "policy_version": policy_version(),
            "taxonomy_version": taxonomy_version(),
            "constraint_version": constraint_version()}


@router.post("/system/killswitch", dependencies=[Depends(require_token), Depends(rate_limit_write)])
async def killswitch(body: KillSwitchIn):
    _STATE["kill_switch"] = body.armed
    return {"kill_switch": _STATE["kill_switch"]}
