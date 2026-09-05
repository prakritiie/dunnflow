from __future__ import annotations
import hashlib, json
from typing import Any

GENESIS = "0" * 64


def canonical_json(body: dict[str, Any]) -> str:
    """Stable serialisation - sorted keys, no whitespace, UTC ISO strings.
    Any drift here breaks every previously written hash, so it must never change."""
    return json.dumps(body, sort_keys=True, separators=(",", ":"), default=str)


def compute_hash(prev_hash: str, body: dict[str, Any]) -> str:
    return hashlib.sha256((prev_hash + canonical_json(body)).encode()).hexdigest()


def chain_body(entry: dict[str, Any]) -> dict[str, Any]:
    """The subset of an entry that is hashed. Excludes seq (assigned by the DB)
    and the hash columns themselves."""
    return {k: entry.get(k) for k in (
        "entry_id", "run_id", "case_id", "case_ref", "entry_type", "node",
        "state_from", "state_to", "rule_id", "policy_version", "model_id",
        "classifier_tier", "idempotency_key", "amount_minor", "outcome",
        "input_snapshot", "output_snapshot", "occurred_at",
    )}
