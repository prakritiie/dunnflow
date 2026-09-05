"""LangGraph assembly.

Used as a DURABLE EXECUTOR, not an agent framework: no tool-calling loop, no
model-driven routing. Every edge is a deterministic function of state.
"""
from __future__ import annotations
from langgraph.graph import END, StateGraph
from app.graph.state import RecoveryState
from app.graph import nodes as N


def route_after_hydrate(s: RecoveryState) -> str:
    return "reconcile" if s.get("status") == "RECON_PENDING" else "sanitize"


def route_after_verify(s: RecoveryState) -> str:
    return "escalate" if s.get("classification_rejected") else "policy"


def route_after_constrain(s: RecoveryState) -> str:
    from app.domain.models.enums import ActionType, Decision
    v, d = s["verdict"], s["directive"]
    if v.decision == Decision.DENY:
        return "schedule" if v.reschedule_at else "escalate"
    if d.action == ActionType.TERMINATE:
        return "terminate"
    if d.action == ActionType.RECONCILE:
        return "reconcile"
    if d.action == ActionType.ESCALATE_HUMAN or d.requires_human_approval:
        return "escalate"
    if d.action in (ActionType.REQUEST_NEW_INSTRUMENT, ActionType.NUDGE_CUSTOMER):
        return "terminate"          # comms sent, no money action pending
    return "execute"


def route_after_observe(s: RecoveryState) -> str:
    from app.domain.models.enums import Outcome
    ex = s.get("execution")
    if ex is None:
        return "terminate"
    if ex.outcome == Outcome.AMBIGUOUS:
        return "reconcile"
    if ex.outcome == Outcome.SUCCEEDED:
        return "terminate"
    return "policy" if s["directive"].attempts_remaining > 1 else "terminate"


def route_after_reconcile(s: RecoveryState) -> str:
    from app.domain.models.enums import ReconResolution
    r = s.get("recon")
    if r is None or r.resolution == ReconResolution.UNRESOLVED:
        return "escalate"
    return "terminate" if r.resolution == ReconResolution.SUCCEEDED else "policy"


def build_graph(checkpointer=None):
    g = StateGraph(RecoveryState)
    g.add_node("ingest", N.ingest)
    g.add_node("hydrate", N.hydrate)
    g.add_node("sanitize", N.sanitize_node)
    g.add_node("classify", N.classify_node)
    g.add_node("verify", N.verify_node)
    g.add_node("policy", N.policy_node)
    g.add_node("constrain", N.constrain_node)
    g.add_node("execute", N.execute_node)
    g.add_node("observe", N.observe_node)
    g.add_node("reconcile", N.reconcile_node)
    g.add_node("schedule", N.schedule_node)
    g.add_node("escalate", N.escalate_node)
    g.add_node("terminate", N.terminate_node)

    g.set_entry_point("ingest")
    g.add_edge("ingest", "hydrate")
    g.add_conditional_edges("hydrate", route_after_hydrate,
                            {"reconcile": "reconcile", "sanitize": "sanitize"})
    g.add_edge("sanitize", "classify")
    g.add_edge("classify", "verify")
    g.add_conditional_edges("verify", route_after_verify,
                            {"policy": "policy", "escalate": "escalate"})
    g.add_edge("policy", "constrain")
    g.add_conditional_edges("constrain", route_after_constrain, {
        "execute": "execute", "reconcile": "reconcile", "schedule": "schedule",
        "escalate": "escalate", "terminate": "terminate",
    })
    g.add_edge("execute", "observe")
    g.add_conditional_edges("observe", route_after_observe, {
        "reconcile": "reconcile", "policy": "policy", "terminate": "terminate",
    })
    g.add_conditional_edges("reconcile", route_after_reconcile, {
        "terminate": "terminate", "policy": "policy", "escalate": "escalate",
    })
    g.add_edge("schedule", END)
    g.add_edge("escalate", END)
    g.add_edge("terminate", END)
    return g.compile(checkpointer=checkpointer) if checkpointer else g.compile()
