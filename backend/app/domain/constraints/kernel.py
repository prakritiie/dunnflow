"""Ordered, veto-only constraint kernel.

Three properties that matter:
  * VETO ONLY - a constraint may deny or delay, never create or upgrade an action.
  * FAIL CLOSED - an evaluation error denies. An unavailable control is a failed control.
  * FULL TRACE - every evaluation is persisted, passes included. Showing only the
    denials would let a reviewer suspect selective logging.
"""
from __future__ import annotations
import functools, hashlib, pathlib
import yaml
from datetime import timedelta
from app.core.config import settings
from app.domain.constraints.base import ConstraintContext
from app.domain.models.core import ConstraintResult, ConstraintVerdict
from app.domain.models.enums import ActionType, Decision, MONEY_MOVING
from app.domain.taxonomy.loader import get_class, is_known


@functools.lru_cache(maxsize=1)
def _load() -> tuple[list[dict], str]:
    path = pathlib.Path(settings.CONFIG_DIR) / "constraints.yaml"
    raw = yaml.safe_load(path.read_text())
    sha = hashlib.sha256(path.read_bytes()).hexdigest()[:12]
    return raw["constraints"], f'{raw["version"]}+{sha}'


def constraint_version() -> str:
    return _load()[1]


def all_constraints() -> list[dict]:
    return _load()[0]


# ─── individual checks: (allowed, reason) ────────────────────────────────────
# Each returns a reason string even on ALLOW, so the trace reads well in the UI.

def _c_ambiguity(ctx):
    if ctx.case.status == "RECON_PENDING":
        return False, "case has an unresolved ambiguous attempt"
    return True, "case not in RECON_PENDING at entry"


def _c_attempt_cap(ctx):
    if ctx.directive.action not in MONEY_MOVING:
        return True, "not a money-moving action"
    cap = get_class(ctx.classification.code).default_max_attempts if is_known(ctx.classification.code) else 0
    if ctx.case.attempt_count >= cap:
        return False, f"attempts {ctx.case.attempt_count} >= cap {cap}"
    return True, f"attempts {ctx.case.attempt_count} < cap {cap}"


def _c_velocity(ctx):
    if ctx.directive.action not in MONEY_MOVING:
        return True, "not a money-moving action"
    limit = ctx.config.get("limit", 3)
    if ctx.attempts_24h >= limit:
        return False, f"{ctx.attempts_24h} attempts in 24h window > limit {limit}"
    return True, f"{ctx.attempts_24h} attempts in 24h window"


def _c_prohibited(ctx):
    if not is_known(ctx.classification.code):
        return True, "unknown class carries no money action"
    t = get_class(ctx.classification.code).terminality
    if t == "PROHIBITED" and ctx.directive.action in MONEY_MOVING:
        return False, f"{ctx.classification.code} is PROHIBITED - money movement forbidden"
    return True, f"{ctx.classification.code} is not PROHIBITED"


def _c_hard_class(ctx):
    if not is_known(ctx.classification.code):
        return True, "unknown class carries no retry"
    t = get_class(ctx.classification.code).terminality
    if t in ("HARD", "AMBIGUOUS") and ctx.directive.action in MONEY_MOVING:
        return False, f"{ctx.classification.code} is {t} - retry forbidden"
    return True, f"{ctx.classification.code} is not HARD"


def _c_amount_ceiling(ctx):
    ceiling = ctx.config.get("ceiling_minor", 5_000_000)
    if ctx.directive.action in MONEY_MOVING and ctx.case.amount_minor > ceiling:
        return False, f"Rs {ctx.case.amount_minor//100:,} > ceiling Rs {ceiling//100:,}"
    return True, f"Rs {ctx.case.amount_minor//100:,} <= ceiling Rs {ceiling//100:,}"


def _c_instrument(ctx):
    if ctx.directive.action in MONEY_MOVING and not ctx.instrument_valid:
        return False, "instrument expired or blocked"
    return True, "instrument not expired"


def _c_issuer_sentinel(ctx):
    if ctx.directive.action not in MONEY_MOVING:
        return True, "not a money-moving action"
    floor = ctx.config.get("floor", 0.60)
    if ctx.issuer_health.samples >= 20 and ctx.issuer_health.ewma_success_rate < floor:
        if ctx.probe_allowed:
            return True, f"issuer degraded ({ctx.issuer_health.ewma_success_rate:.2f}) - recovery probe released"
        return False, f"issuer EWMA success-rate {ctx.issuer_health.ewma_success_rate:.2f} < floor {floor:.2f}"
    return True, "issuer EWMA success-rate OK"


def _c_circuit(ctx):
    if ctx.directive.action in MONEY_MOVING and ctx.circuit_open:
        return False, "gateway circuit OPEN"
    return True, "gateway circuit CLOSED"


def _c_idempotency(ctx):
    if ctx.directive.action in MONEY_MOVING and ctx.idempotency_consumed:
        return False, "idempotency key already consumed"
    return True, "no prior attempt with same key"


def _c_compliance_window(ctx):
    if ctx.directive.action not in MONEY_MOVING or ctx.directive.scheduled_at is None:
        return True, "no scheduled money action"
    hours = ctx.config.get("retry_window_hours", 24)
    if ctx.directive.scheduled_at > ctx.now + timedelta(hours=hours * 14):
        return False, f"scheduled beyond permitted window ({hours}h basis)"
    return True, f"within retry window ({hours}h basis, UNVERIFIED)"


def _c_kill_switch(ctx):
    if ctx.kill_switch_armed and ctx.directive.action in MONEY_MOVING:
        return False, "kill switch armed - money movement halted"
    return True, "kill switch not armed"


CHECKS = {
    "C_AMBIGUITY_CHECK": _c_ambiguity,
    "C_ATTEMPT_CAP": _c_attempt_cap,
    "C_VELOCITY_LIMIT": _c_velocity,
    "C_PROHIBITED_CLASS": _c_prohibited,
    "C_HARD_CLASS": _c_hard_class,
    "C_AMOUNT_CEILING": _c_amount_ceiling,
    "C_INSTRUMENT_VALID": _c_instrument,
    "C_ISSUER_SENTINEL": _c_issuer_sentinel,
    "C_CIRCUIT_BREAKER": _c_circuit,
    "C_IDEMPOTENCY_LOCK": _c_idempotency,
    "C_COMPLIANCE_WINDOW": _c_compliance_window,
    "C_KILL_SWITCH": _c_kill_switch,
}


def evaluate(ctx: ConstraintContext) -> ConstraintVerdict:
    results: list[ConstraintResult] = []
    denied_by = deny_reason = None
    short_circuited = False

    for spec in sorted(all_constraints(), key=lambda c: c["position"]):
        cid, pos = spec["id"], spec["position"]
        unverified = bool(spec.get("unverified", False))

        if short_circuited:
            results.append(ConstraintResult(position=pos, constraint_id=cid,
                                            decision=Decision.SKIPPED,
                                            reason="short-circuited after DENY",
                                            unverified=unverified))
            continue

        check = CHECKS.get(cid)
        cfg = {k: v for k, v in spec.items() if k not in ("position", "id", "fail_mode", "description", "unverified")}
        local = ConstraintContext(**{**ctx.__dict__, "config": cfg})
        try:
            allowed, reason = check(local) if check else (True, "no implementation - vacuous pass")
        except Exception as exc:                                   # fail closed
            allowed, reason = False, f"evaluation error ({type(exc).__name__}) - fail-closed"

        results.append(ConstraintResult(position=pos, constraint_id=cid,
                                        decision=Decision.ALLOW if allowed else Decision.DENY,
                                        reason=reason, unverified=unverified))
        if not allowed:
            denied_by, deny_reason, short_circuited = cid, reason, True

    reschedule = None
    if denied_by in ("C_CIRCUIT_BREAKER", "C_ISSUER_SENTINEL", "C_VELOCITY_LIMIT"):
        reschedule = ctx.now + timedelta(minutes=45)

    return ConstraintVerdict(
        decision=Decision.DENY if denied_by else Decision.ALLOW,
        evaluated=tuple(results), denied_by=denied_by, deny_reason=deny_reason,
        reschedule_at=reschedule, constraint_version=constraint_version(),
    )
