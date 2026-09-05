"""Deterministic policy engine.

Hard rules for this module:
  * no I/O, no network, no database, no randomness
  * no datetime.now() - the clock is injected
  * ZERO imports from app.llm.* (enforced by tests/property/test_no_llm_in_domain.py)

Same inputs always produce the same rule_id. That property is what makes the
audit trail replayable and the whole determinism claim meaningful.
"""
from __future__ import annotations
import functools, hashlib, pathlib
import yaml
from datetime import datetime
from app.core.config import settings
from app.domain.models.core import CaseView, Classification, Directive, IssuerHealth
from app.domain.models.enums import ActionType, Backoff
from app.domain.policy import backoff as backoff_mod
from app.domain.taxonomy.loader import get_class, is_known


@functools.lru_cache(maxsize=1)
def _load() -> tuple[list[dict], dict, str]:
    path = pathlib.Path(settings.CONFIG_DIR) / "policy.yaml"
    raw = yaml.safe_load(path.read_text())
    sha = hashlib.sha256(path.read_bytes()).hexdigest()[:12]
    return raw["rules"], raw, f'{raw["version"]}+{sha}'


def policy_version() -> str:
    return _load()[2]


def high_value_ceiling() -> int:
    return _load()[1].get("high_value_ceiling_minor", 5_000_000)


def all_rules() -> list[dict]:
    return _load()[0]


def _matches(rule: dict, code: str, attempt_index: int, amount_minor: int) -> bool:
    m = rule.get("match", {})
    if "class" in m and m["class"] != code:
        return False
    if "amount_minor_gte" in m and amount_minor < m["amount_minor_gte"]:
        return False
    if "attempt_index_lt" in m and not attempt_index < m["attempt_index_lt"]:
        return False
    if "attempt_index_gte" in m and not attempt_index >= m["attempt_index_gte"]:
        return False
    return True


def evaluate(
    *,
    classification: Classification,
    case: CaseView,
    history: tuple,
    issuer_health: IssuerHealth,
    now: datetime,
) -> Directive:
    code = classification.code
    attempt_index = case.attempt_count
    ver = policy_version()

    if not is_known(code):
        return Directive(
            action=ActionType.ESCALATE_HUMAN, rule_id="ESCALATE_UNKNOWN_009",
            policy_version=ver, rationale_code="UNCLASSIFIED",
            attempt_index=attempt_index, requires_human_approval=True,
        )

    fc = get_class(code)
    rules = all_rules()

    # overrides first, then specific matches in declaration order
    chosen = next((r for r in rules if r.get("override") and _matches(r, code, attempt_index, case.amount_minor)), None)
    if chosen is None:
        chosen = next((r for r in rules if not r.get("override") and _matches(r, code, attempt_index, case.amount_minor)), None)
    if chosen is None:
        return Directive(
            action=ActionType.ESCALATE_HUMAN, rule_id="ESCALATE_UNKNOWN_009",
            policy_version=ver, rationale_code="NO_MATCHING_RULE",
            attempt_index=attempt_index, requires_human_approval=True,
        )

    action = ActionType(chosen["action"])
    strat = Backoff(chosen.get("backoff", "NONE"))

    # Structural guard: terminality outranks the matrix. Even a misconfigured
    # rule cannot produce a retry on a HARD or PROHIBITED class.
    if action in (ActionType.RETRY_SAME_RAIL, ActionType.RETRY_ALT_RAIL) and fc.terminality in ("HARD", "PROHIBITED", "AMBIGUOUS"):
        return Directive(
            action=ActionType.TERMINATE, rule_id=chosen["rule_id"], policy_version=ver,
            rationale_code="TERMINALITY_BLOCKS_RETRY", attempt_index=attempt_index,
        )

    scheduled_at = None
    if action in (ActionType.RETRY_SAME_RAIL, ActionType.RETRY_ALT_RAIL):
        scheduled_at = backoff_mod.compute(
            strat, now=now, attempt_index=attempt_index,
            key=f"{case.case_ref}:{attempt_index}:{ver}",
        )

    remaining = max(fc.default_max_attempts - attempt_index, 0)
    return Directive(
        action=action,
        rule_id=chosen["rule_id"],
        policy_version=ver,
        rationale_code=chosen.get("rationale_code", "UNSPECIFIED"),
        backoff=strat if action in (ActionType.RETRY_SAME_RAIL, ActionType.RETRY_ALT_RAIL) else Backoff.NONE,
        scheduled_at=scheduled_at,
        channel=chosen.get("channel"),
        amount_minor=case.amount_minor if action in (ActionType.RETRY_SAME_RAIL, ActionType.RETRY_ALT_RAIL) else None,
        attempt_index=attempt_index,
        attempts_remaining=remaining,
        requires_human_approval=bool(chosen.get("requires_human_approval", False)),
    )
