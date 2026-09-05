"""Run engine. Executes both arms over a seeded batch and persists everything."""
from __future__ import annotations
import uuid
from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit import writer
from app.core.clock import FrozenClock
from app.db.models import Case, CaseEvent, ConstraintEvaluation, Attempt, Run
from app.domain.constraints.kernel import constraint_version
from app.domain.models.enums import Arm, CaseStatus, Decision, RunStatus, MONEY_MOVING
from app.domain.policy.engine import policy_version
from app.domain.taxonomy.loader import taxonomy_version, get_class
from app.executors.base import ExecutorBase
from app.executors.circuit_breaker import Breaker
from app.executors.idempotency import STORE
from app.executors.mock_psp import MockPSP
from app.graph import nodes as N
from app.graph.build import build_graph
from app.recon.reconciler import Reconciler
from app.sentinel import IssuerSentinel
from app.simulation import arm_control
from app.simulation.generator import generate

#: classes where dunnflow's timing choice is materially better than a blind retry
WELL_TIMED = {"INSUFFICIENT_FUNDS", "TEMPORARY_HOLD", "ISSUER_DECLINE", "SOFT_DECLINE",
              "NETWORK_ERROR", "GATEWAY_ERROR"}

_GRAPH = build_graph()


async def execute_run(session: AsyncSession, run: Run, *, progress=None) -> dict:
    cases = generate(run.seed, run.n)
    clock = FrozenClock()
    psp = MockPSP(seed=run.seed)
    breaker = Breaker(clock=clock)
    metrics = {
        "cases": run.n, "recovered": 0, "amount_recovered_minor": 0,
        "network_attempts": 0, "duplicate_charges": 0, "compliance_violations": 0,
        "escalated": 0, "refusals": 0, "hard_class_retries": 0,
        "tiers": {"T1": 0, "T2": 0, "T3": 0, "T4": 0},
        "status_counts": {}, "series": [], "duplicate_charge_prevented": 0,
        # cases deferred to the next credit cycle by the policy/constraint layer -
        # counted explicitly so they never silently vanish from the totals
        "deferred": 0, "deferred_amount_minor": 0,
    }

    if run.arm == Arm.CONTROL:
        return await _run_control(session, run, cases, psp, metrics, progress)
    return await _run_dunnflow(session, run, cases, psp, breaker, clock, metrics, progress)


async def _run_control(session, run, cases, psp, metrics, progress):
    metrics["compliance_violations"] = None      # no constraint layer exists
    for i, sc in enumerate(cases, 1):
        r = arm_control.run_case(psp, sc)
        metrics["network_attempts"] += r["attempts"]
        metrics["hard_class_retries"] += r["hard_class_retries"]
        if r["recovered"]:
            metrics["recovered"] += 1
            metrics["amount_recovered_minor"] += r["amount_minor"]
        if r["duplicate_charge"]:
            metrics["duplicate_charges"] += 1
        st = r["status"]
        metrics["status_counts"][st] = metrics["status_counts"].get(st, 0) + 1
        session.add(Case(
            run_id=run.id, case_ref=sc.case_ref, merchant_id=sc.merchant_id,
            obligation_ref=sc.obligation_ref, failure_class=sc.failure_class,
            failure_family=sc.failure_family, amount_minor=sc.amount_minor,
            status=st, rule_id="BLIND_FIXED_INTERVAL", classifier_tier=None,
            attempt_count=r["attempts"],
            resolved_at=datetime.now(timezone.utc),
        ))
        if i % 50 == 0:
            metrics["series"].append({"processed": i, "recovered": metrics["recovered"]})
            await session.flush()
            if progress:
                await progress(i, metrics)
    metrics["series"].append({"processed": run.n, "recovered": metrics["recovered"]})
    return metrics


async def _run_dunnflow(session, run, cases, psp, breaker, clock, metrics, progress):
    reconciler = Reconciler(psp)
    executor = ExecutorBase(psp, breaker)
    sentinel = IssuerSentinel()
    r = await STORE.client()
    await r.flushdb()

    for i, sc in enumerate(cases, 1):
        N.set_context(clock=clock, attempts={}, breaker=breaker, executor=executor,
                      reconciler=reconciler, sentinel=sentinel, kill_switch=False,
                      network_calls=0, attempt_rows=[], violations=0)
        state = {
            "run_id": str(run.id), "case_ref": sc.case_ref, "merchant_id": sc.merchant_id,
            "obligation_ref": sc.obligation_ref, "amount_minor": sc.amount_minor,
            "case_key": f"{run.id}:{sc.case_ref}",
            "raw_error": sc.raw_error, "events": [], "refusals": [], "node_errors": [],
            "well_timed": sc.failure_class in WELL_TIMED,
        }
        try:
            final = await _GRAPH.ainvoke(state, {"recursion_limit": 40})
        except Exception as exc:
            final = {**state, "status": CaseStatus.NEEDS_HUMAN,
                     "events": state["events"] + [{"seq": 99, "node": "error",
                                                   "state_to": "NEEDS_HUMAN",
                                                   "note": f"{type(exc).__name__}: {exc}"}]}

        ex_ = final.get("execution")
        if ex_ is not None:
            from app.domain.models.enums import Outcome as _O
            sentinel.observe(sc.failure_class, ex_.outcome == _O.SUCCEEDED)

        await _persist_case(session, run, sc, final, metrics)
        metrics["network_attempts"] += N._CTX.get("network_calls", 0)

        if i % 50 == 0:
            metrics["series"].append({"processed": i, "recovered": metrics["recovered"]})
            await session.flush()
            if progress:
                await progress(i, metrics)
        clock.advance(seconds=1)

    metrics["series"].append({"processed": run.n, "recovered": metrics["recovered"]})
    metrics["issuer_health"] = sentinel.snapshot()
    return metrics


async def _persist_case(session, run, sc, final, metrics):
    status = str(final.get("status", CaseStatus.TERMINATED))
    directive = final.get("directive")
    cls = final.get("classification")
    tier = final.get("classifier_tier")
    if tier:
        metrics["tiers"][tier] = metrics["tiers"].get(tier, 0) + 1

    case = Case(
        run_id=run.id, case_ref=sc.case_ref, merchant_id=sc.merchant_id,
        obligation_ref=sc.obligation_ref, failure_class=cls.code if cls else sc.failure_class,
        failure_family=sc.failure_family, amount_minor=sc.amount_minor, status=status,
        rule_id=directive.rule_id if directive else None,
        classifier_tier=tier, classifier_conf=float(cls.confidence) if cls else None,
        attempt_count=len(N._CTX.get("attempt_rows", [])),
        resolved_at=datetime.now(timezone.utc),
    )
    session.add(case)
    await session.flush()

    for e in final.get("events", []):
        session.add(CaseEvent(case_id=case.id, seq=e["seq"], node=e["node"],
                              state_from=e.get("state_from"), state_to=e.get("state_to"),
                              rule_id=e.get("rule_id"), note=e.get("note"), flags=e.get("flags")))

    for row in N._CTX.get("attempt_rows", []):
        ex = final.get("execution")
        session.add(Attempt(
            case_id=case.id, attempt_index=row["attempt_index"], action=row["action"],
            idempotency_key=row["idempotency_key"],
            outcome=str(ex.outcome) if ex else "FAILED",
            amount_minor=sc.amount_minor,
            gateway_ref=ex.gateway_ref if ex else None,
            error_raw=ex.error_raw if ex else None,
            settled_at=datetime.now(timezone.utc)))

    for rf in final.get("refusals", []):
        if rf["decision"] == "DENY":
            metrics["refusals"] += 1
        session.add(ConstraintEvaluation(
            case_id=case.id, run_id=run.id, position=rf["position"],
            constraint_id=rf["constraint_id"], decision=rf["decision"],
            reason=rf["reason"], reschedule_at=rf.get("reschedule_at"),
            proposed_action=rf["proposed_action"], rule_id=rf["rule_id"],
            failure_class=rf.get("failure_class"),
            unverified=rf["unverified"], constraint_version=constraint_version()))

    # audit: one DECISION row (model_id NULL) + terminal OUTCOME row
    if directive:
        await writer.append(session, entry_type="DECISION", run_id=run.id, case_id=case.id,
                            case_ref=sc.case_ref, node="policy", rule_id=directive.rule_id,
                            policy_version=directive.policy_version, model_id=None,
                            classifier_tier=tier, amount_minor=sc.amount_minor,
                            state_to="POLICY_SELECTED",
                            output_snapshot={"action": str(directive.action),
                                             "rationale": directive.rationale_code})
    ex = final.get("execution")
    await writer.append(session, entry_type="OUTCOME", run_id=run.id, case_id=case.id,
                        case_ref=sc.case_ref, node="audit", state_to=status,
                        rule_id=directive.rule_id if directive else None,
                        idempotency_key=ex.idempotency_key if ex else None,
                        amount_minor=sc.amount_minor, outcome=status, model_id=None)

    if status == str(CaseStatus.RECOVERED):
        metrics["recovered"] += 1
        metrics["amount_recovered_minor"] += sc.amount_minor
    elif status == str(CaseStatus.DUPLICATE_CHARGE_PREVENTED):
        metrics["duplicate_charge_prevented"] += 1
        metrics["recovered"] += 1
        metrics["amount_recovered_minor"] += sc.amount_minor
        await writer.append(session, entry_type="DUPLICATE_CHARGE_PREVENTED", run_id=run.id,
                            case_id=case.id, case_ref=sc.case_ref, node="reconcile",
                            amount_minor=sc.amount_minor, model_id=None,
                            idempotency_key=ex.idempotency_key if ex else None)
    if status == str(CaseStatus.NEEDS_HUMAN):
        metrics["escalated"] += 1
    if status == str(CaseStatus.DEFERRED_TO_CREDIT_CYCLE):
        metrics["deferred"] += 1
        metrics["deferred_amount_minor"] += sc.amount_minor

    # violations are counted at the execute node, where the governing verdict is known
    metrics["compliance_violations"] += N._CTX.get("violations", 0)
    if directive is not None and directive.action in MONEY_MOVING and ex is not None:
        if get_class(cls.code).terminality in ("HARD", "PROHIBITED"):
            metrics["hard_class_retries"] += 1

    metrics["status_counts"][status] = metrics["status_counts"].get(status, 0) + 1
