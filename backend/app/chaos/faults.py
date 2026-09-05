"""Fault catalogue. Each fault has a defined, tested recovery path."""
from __future__ import annotations

FAULTS = [
    {"id": "redis-down",        "label": "Redis Unavailable",    "family": "INFRASTRUCTURE", "severity": "critical",
     "description": "Idempotency store unavailable - all money movement halts (fail-closed)"},
    {"id": "gateway-timeout",   "label": "Gateway Timeout",      "family": "TRANSPORT",      "severity": "high",
     "description": "Gateway calls time out - produces an AMBIGUOUS outcome that must be reconciled"},
    {"id": "llm-timeout",       "label": "LLM Timeout",          "family": "AI",             "severity": "medium",
     "description": "Primary and fallback models time out - classifier demotes to T4 UNKNOWN"},
    {"id": "circuit-open",      "label": "Circuit Breaker Open", "family": "TRANSPORT",      "severity": "high",
     "description": "Consecutive gateway failures trip the circuit to OPEN"},
    {"id": "duplicate-event",   "label": "Duplicate Webhook",    "family": "INGEST",         "severity": "low",
     "description": "Replays the last event - must be deduplicated, no second case created"},
    {"id": "poison-payload",    "label": "Poison Payload",       "family": "INGEST",         "severity": "low",
     "description": "Malformed webhook body - must land in dead_letters"},
    {"id": "injection-attempt", "label": "Prompt Injection",     "family": "AI",             "severity": "medium",
     "description": "Role-escalation string in gateway error text - must be stripped and contained"},
    {"id": "high-value-case",   "label": "High-Value Case",      "family": "COMPLIANCE",     "severity": "medium",
     "description": "Case above the ceiling - requires HITL approval before execution"},
    {"id": "issuer-anomaly",    "label": "Issuer Anomaly",       "family": "SENTINEL",       "severity": "high",
     "description": "Issuer EWMA success-rate drops below floor - sentinel denies retries"},
]

FAULT_IDS = {f["id"] for f in FAULTS}
