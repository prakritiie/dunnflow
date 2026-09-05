from __future__ import annotations
from operator import add
from typing import Annotated, Any, TypedDict


class RecoveryState(TypedDict, total=False):
    # identity
    run_id: str
    case_ref: str
    merchant_id: str
    obligation_ref: str
    amount_minor: int

    # versions pinned at run start - a hot reload mid-batch must not produce a
    # run where half the decisions used v3 and half used v4 with no record
    policy_version: str
    taxonomy_version: str
    constraint_version: str

    # payload
    raw_error: dict
    sanitized_text: str
    sanitizer_report: dict

    # classify
    classification: Any
    classifier_tier: str
    classification_rejected: str | None

    # decide
    directive: Any
    verdict: Any

    # execute
    execution: Any
    recon: Any
    well_timed: bool

    # control
    status: str
    terminal: bool
    events: Annotated[list[dict], add]
    refusals: Annotated[list[dict], add]
    node_errors: Annotated[list[dict], add]
