from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol
from app.domain.models.core import CaseView, Classification, Directive, IssuerHealth


@dataclass(frozen=True)
class ConstraintContext:
    """Everything a constraint may read. Deliberately narrow."""
    case: CaseView
    classification: Classification
    directive: Directive
    issuer_health: IssuerHealth
    now: datetime
    attempts_24h: int = 0
    kill_switch_armed: bool = False
    idempotency_consumed: bool = False
    circuit_open: bool = False
    instrument_valid: bool = True
    probe_allowed: bool = False
    config: dict = field(default_factory=dict)


class Constraint(Protocol):
    position: int
    id: str
    fail_mode: str

    def check(self, ctx: ConstraintContext) -> tuple[bool, str]:
        """Returns (allowed, reason). Raising is treated as DENY when fail_mode=CLOSED."""
        ...
