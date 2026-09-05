"""Typed domain exceptions. Each maps to one HTTP status in api/errors.py.
Client-facing messages never carry stack traces, SQL, or secrets."""
from __future__ import annotations


class DunnflowError(Exception):
    code = "INTERNAL_ERROR"
    status = 500
    message = "An internal error occurred"

    def __init__(self, message: str | None = None, detail: dict | None = None) -> None:
        self.message = message or self.__class__.message
        self.detail = detail or {}
        super().__init__(self.message)


class NotFound(DunnflowError):
    code, status, message = "NOT_FOUND", 404, "Resource not found"


class Unauthorized(DunnflowError):
    code, status, message = "UNAUTHORIZED", 401, "Missing or invalid credentials"


class Forbidden(DunnflowError):
    code, status, message = "FORBIDDEN", 403, "Action forbidden by system state"


class Conflict(DunnflowError):
    code, status, message = "CONFLICT", 409, "Conflicting state"


class InvalidStateTransition(Conflict):
    code, message = "INVALID_STATE_TRANSITION", "Illegal state transition"


class ConstraintDenied(Forbidden):
    code, message = "CONSTRAINT_DENIED", "Action denied by a constraint"


class IdempotencyNotHeld(DunnflowError):
    code, status = "IDEMPOTENCY_NOT_HELD", 409
    message = "Idempotency lock not held - execution refused"


class KillSwitchArmed(Forbidden):
    code, message = "KILL_SWITCH_ARMED", "Kill switch is armed - money movement halted"


class RateLimited(DunnflowError):
    code, status, message = "RATE_LIMITED", 429, "Too many requests"


class ChaosInjected(DunnflowError):
    code, status, message = "CHAOS_INJECTED", 500, "Injected fault"
