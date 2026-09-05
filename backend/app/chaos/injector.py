"""Runtime fault injection. Two-step arm->fire is enforced here, server-side,
not merely in the UI - a one-click destructive control is the wrong affordance
even in a simulator."""
from __future__ import annotations
import time
from app.chaos.faults import FAULT_IDS
from app.core.exceptions import Conflict, NotFound

_ARM_TTL_S = 120
_FIRE_TTL_S = 30


class ChaosState:
    def __init__(self) -> None:
        self._armed: dict[str, float] = {}
        self._fired: dict[str, float] = {}

    def _sweep(self) -> None:
        now = time.time()
        self._armed = {k: v for k, v in self._armed.items() if v > now}
        self._fired = {k: v for k, v in self._fired.items() if v > now}

    def state(self, fault_id: str) -> str:
        self._sweep()
        if fault_id in self._fired:
            return "FIRED"
        if fault_id in self._armed:
            return "ARMED"
        return "DISARMED"

    def arm(self, fault_id: str) -> None:
        if fault_id not in FAULT_IDS:
            raise NotFound("Unknown fault", {"fault_id": fault_id})
        if self.state(fault_id) != "DISARMED":
            raise Conflict("Fault is already armed or firing", {"fault_id": fault_id})
        self._armed[fault_id] = time.time() + _ARM_TTL_S

    def fire(self, fault_id: str) -> None:
        if fault_id not in FAULT_IDS:
            raise NotFound("Unknown fault", {"fault_id": fault_id})
        if self.state(fault_id) != "ARMED":
            raise Conflict("Fault must be armed before firing", {"fault_id": fault_id})
        self._armed.pop(fault_id, None)
        self._fired[fault_id] = time.time() + _FIRE_TTL_S

    def disarm(self, fault_id: str) -> None:
        self._armed.pop(fault_id, None)
        self._fired.pop(fault_id, None)

    def is_active(self, fault_id: str) -> bool:
        return self.state(fault_id) == "FIRED"

    def clear(self) -> None:
        self._armed.clear(); self._fired.clear()


CHAOS = ChaosState()
