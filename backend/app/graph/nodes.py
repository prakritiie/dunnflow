"""Graph nodes. Each returns only its declared state keys.

Effects (PSP, Redis) are injected via state['_ctx'] so the graph itself stays
testable and the domain layer stays pure.
"""
from __future__ import annotations
from datetime import datetime, timezone
from app.core.exceptions import IdempotencyNotHeld
from app.domain.constraints.base import ConstraintContext
from app.domain.constraints.kernel import evaluate as kernel_eval, constraint_version
from app.domain.models.core import CaseView, IssuerHealth
from app.domain.models.enums import (
    ActionType, CaseStatus, Decision, MONEY_MOVING, Outcome, ReconResolution,
)
from app.domain.policy.engine import evaluate as policy_eval, policy_version
from app.domain.taxonomy.loader import get_class, is_known, taxonomy_version
from app.llm import classifier as clf

_CTX: dict = {}


def set_context(**kw) -> None:
    _CTX.clear(); _CTX.update(kw)


def _ev(state, node, to, note="", rule_id=None, **flags):
    return {"seq": len(state.get("events", [])) + 1, "node": node,
            "state_from": state.get("status"), "state_to": to,
            "rule_id": rule_id, "note": note, "flags": flags or None,
            "occurred_at": _CTX["clock"].now().isoformat()}


def ingest(state):
    return {"status": CaseStatus.RECEIVED,
            "policy_version": policy_version(),
            "taxonomy_version": taxonomy_version(),
            "constraint_version": constraint_version(),
            "events": [_ev(state, "ingest", CaseStatus.RECEIVED, "event accepted, deduplicated")]}


def hydrate(state):
    return {"status": CaseStatus.HYDRATED,
            "events": [_ev(state, "hydrate", CaseStatus.HYDRATED,
                           "obligation loaded, no prior RECON_PENDING")]}


def sanitize_node(state):
    from app.llm.sanitizer import sanitize
    from app.llm.pii import mask
    raw = state.get("raw_error", {}) or {}
    masked, _ = mask(raw.get("description", ""), raw.get("customer_tokens"))
    clean, rep = sanitize(masked)
    return {"sanitized_text": clean, "sanitizer_report": rep.__dict__,
            "events": [_ev(state, "sanitize", CaseStatus.HYDRATED,
                           f"PII masked, injection scrub, {len(clean)} chars")]}


def classify_node(state):
    raw = state.get("raw_error", {}) or {}
    c, meta = clf.classify(error_source=raw.get("source"), error_step=raw.get("step"),
                           error_reason=raw.get("reason"), error_description=raw.get("description"),
                           customer_tokens=raw.get("customer_tokens"))
    return {"classification": c, "classifier_tier": str(c.tier),
            "status": CaseStatus.CLASSIFIED,
            "events": [_ev(state, "classify", CaseStatus.CLASSIFIED,
                           f"{c.tier} {c.code} conf {c.confidence:.3f}")]}


def verify_node(state):
    c = state["classification"]
    ok, reason = clf.verify(c, state.get("sanitized_text", ""))
    if ok:
        return {"classification_rejected": None,
                "events": [_ev(state, "verify", CaseStatus.CLASSIFIED, "classification accepted")]}
    return {"classification_rejected": reason,
            "events": [_ev(state, "verify", CaseStatus.CLASSIFIED, f"rejected: {reason}")]}


def policy_node(state):
    c = state["classification"]
    cv = CaseView(case_ref=state["case_ref"], merchant_id=state["merchant_id"],
                  obligation_ref=state["obligation_ref"], amount_minor=state["amount_minor"],
                  status=CaseStatus.CLASSIFIED, attempt_count=_CTX["attempts"].get(state["case_ref"], 0),
                  failure_class=c.code)
    d = policy_eval(classification=c, case=cv, history=(),
                    issuer_health=_CTX["sentinel"].health(c.code),
                    now=_CTX["clock"].now())
    return {"directive": d, "status": CaseStatus.POLICY_SELECTED,
            "events": [_ev(state, "policy", CaseStatus.POLICY_SELECTED,
                           f"directive {d.action}", rule_id=d.rule_id)]}


def constrain_node(state):
    c, d = state["classification"], state["directive"]
    n = _CTX["attempts"].get(state["case_ref"], 0)
    cv = CaseView(case_ref=state["case_ref"], merchant_id=state["merchant_id"],
                  obligation_ref=state["obligation_ref"], amount_minor=state["amount_minor"],
                  status=CaseStatus(state.get("status", CaseStatus.POLICY_SELECTED)),
                  attempt_count=n, failure_class=c.code)
    instrument_valid = c.code not in ("CARD_EXPIRED", "LOST_OR_STOLEN", "INVALID_CVV")
    v = kernel_eval(ConstraintContext(
        case=cv, classification=c, directive=d,
        issuer_health=_CTX["sentinel"].health(c.code),
        now=_CTX["clock"].now(), attempts_24h=n,
        kill_switch_armed=_CTX.get("kill_switch", False),
        circuit_open=_CTX["breaker"].state == "OPEN",
        instrument_valid=instrument_valid,
        probe_allowed=_CTX["sentinel"].allow_probe(c.code) if d.action in MONEY_MOVING else False,
    ))
    refusals = [{"position": r.position, "constraint_id": r.constraint_id,
                 "decision": str(r.decision), "reason": r.reason,
                 "unverified": r.unverified, "rule_id": d.rule_id,
                 "proposed_action": str(d.action), "failure_class": c.code,
                 "reschedule_at": v.reschedule_at} for r in v.evaluated]
    allow = sum(1 for r in v.evaluated if r.decision == Decision.ALLOW)
    return {"verdict": v, "status": CaseStatus.CONSTRAINED, "refusals": refusals,
            "events": [_ev(state, "constrain", CaseStatus.CONSTRAINED,
                           f"{len(v.evaluated)} evaluated, {allow} ALLOW"
                           + (f", DENY by {v.denied_by}" if v.denied_by else ""),
                           rule_id=d.rule_id)]}


async def execute_node(state):
    d = state["directive"]
    ref = state["case_ref"]
    rows = []

    # Structural guard AND the correct measurement point for a compliance
    # violation: an execution is a violation only if the verdict governing THAT
    # attempt denied it. Inferring violations post-hoc from final state
    # misattributes an execution that merely preceded a later denial.
    v = state.get("verdict")
    if v is not None and str(v.decision) == "DENY":
        _CTX["violations"] = _CTX.get("violations", 0) + 1
        return {"execution": None, "status": CaseStatus.NEEDS_HUMAN,
                "node_errors": [{"node": "execute", "error": "CONSTRAINT_DENIED",
                                 "message": v.deny_reason or "denied"}],
                "events": [_ev(state, "execute", CaseStatus.NEEDS_HUMAN,
                               f"refused: constraint {v.denied_by} denied this action",
                               rule_id=d.rule_id)]}

    async def on_row(key, outcome):
        rows.append({"idempotency_key": key, "outcome": str(outcome),
                     "attempt_index": d.attempt_index, "action": str(d.action)})

    try:
        ex = await _CTX["executor"].execute(
            case_ref=ref, case_key=state.get("case_key", ref),
            failure_class=state["classification"].code, directive=d,
            well_timed=state.get("well_timed", True), on_attempt_row=on_row)
    except IdempotencyNotHeld as exc:
        return {"execution": None, "status": CaseStatus.NEEDS_HUMAN,
                "node_errors": [{"node": "execute", "error": exc.code, "message": exc.message}],
                "events": [_ev(state, "execute", CaseStatus.NEEDS_HUMAN,
                               f"execution refused: {exc.message}", rule_id=d.rule_id)]}
    except Exception as exc:
        return {"execution": None, "status": CaseStatus.NEEDS_HUMAN,
                "node_errors": [{"node": "execute", "error": type(exc).__name__, "message": str(exc)}],
                "events": [_ev(state, "execute", CaseStatus.NEEDS_HUMAN,
                               f"fail-closed: {type(exc).__name__}", rule_id=d.rule_id)]}

    _CTX["attempts"][ref] = _CTX["attempts"].get(ref, 0) + 1
    _CTX.setdefault("attempt_rows", []).extend(rows)
    _CTX["network_calls"] = _CTX.get("network_calls", 0) + 1
    return {"execution": ex, "status": CaseStatus.IN_FLIGHT,
            "events": [_ev(state, "execute", CaseStatus.IN_FLIGHT,
                           f"attempt written IN_FLIGHT before network call, outcome {ex.outcome}",
                           rule_id=d.rule_id, ambiguous=(ex.outcome == Outcome.AMBIGUOUS))]}


def observe_node(state):
    ex = state.get("execution")
    if ex is None:
        return {"events": [_ev(state, "observe", state.get("status"), "no execution result")]}
    return {"events": [_ev(state, "observe", state.get("status"), f"outcome {ex.outcome}")]}


async def reconcile_node(state):
    ref = state["case_ref"]
    ex = state.get("execution")
    key = ex.idempotency_key if ex else "n/a"
    idx = state["directive"].attempt_index if state.get("directive") else 0
    r = await _CTX["reconciler"].resolve(case_ref=ref, attempt_index=idx, idempotency_key=key)
    if r.resolution == ReconResolution.SUCCEEDED:
        await _CTX["reconciler"].release(ref)
        return {"recon": r, "status": CaseStatus.DUPLICATE_CHARGE_PREVENTED,
                "events": [_ev(state, "reconcile", CaseStatus.DUPLICATE_CHARGE_PREVENTED,
                               r.note, dcp=True)]}
    if r.resolution == ReconResolution.FAILED:
        await _CTX["reconciler"].release(ref)
        return {"recon": r, "status": CaseStatus.POLICY_SELECTED,
                "events": [_ev(state, "reconcile", CaseStatus.POLICY_SELECTED, r.note)]}
    return {"recon": r, "status": CaseStatus.NEEDS_HUMAN,
            "events": [_ev(state, "reconcile", CaseStatus.NEEDS_HUMAN, r.note)]}


def schedule_node(state):
    v = state["verdict"]
    return {"status": CaseStatus.DEFERRED_TO_CREDIT_CYCLE, "terminal": True,
            "events": [_ev(state, "schedule", CaseStatus.DEFERRED_TO_CREDIT_CYCLE,
                           f"deferred to next credit cycle: {v.deny_reason or 'backoff'} "
                           "— amount counted as deferred, not recovered or lost",
                           rule_id=state["directive"].rule_id)]}


def escalate_node(state):
    reason = state.get("classification_rejected") or (
        state["verdict"].deny_reason if state.get("verdict") else "requires human approval")
    return {"status": CaseStatus.NEEDS_HUMAN, "terminal": True,
            "events": [_ev(state, "escalate", CaseStatus.NEEDS_HUMAN, reason,
                           rule_id=state["directive"].rule_id if state.get("directive") else None)]}


def terminate_node(state):
    ex, rec = state.get("execution"), state.get("recon")
    d = state.get("directive")
    if rec is not None and rec.resolution == ReconResolution.SUCCEEDED:
        final = CaseStatus.DUPLICATE_CHARGE_PREVENTED
        note = "duplicate suppressed, money moved exactly once"
    elif ex is not None and ex.outcome == Outcome.SUCCEEDED:
        final = CaseStatus.RECOVERED
        note = "obligation collected"
    elif d is not None and d.action in (ActionType.REQUEST_NEW_INSTRUMENT, ActionType.NUDGE_CUSTOMER):
        final = CaseStatus.TERMINATED
        note = f"customer action requested via {d.channel or 'default channel'}"
    elif d is not None and d.action == ActionType.TERMINATE:
        final = CaseStatus.TERMINATED
        note = f"terminated: {d.rationale_code}"
    elif ex is not None and ex.outcome == Outcome.FAILED:
        final = CaseStatus.EXHAUSTED
        note = "attempts exhausted"
    else:
        final = CaseStatus.TERMINATED
        note = "closed"
    return {"status": final, "terminal": True,
            "events": [_ev(state, "audit", final, note,
                           rule_id=d.rule_id if d else None,
                           dcp=(final == CaseStatus.DUPLICATE_CHARGE_PREVENTED))]}
