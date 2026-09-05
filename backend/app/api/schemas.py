from __future__ import annotations
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field

_IN = ConfigDict(extra="forbid")     # blocks mass assignment


class RunCreate(BaseModel):
    model_config = _IN
    arm: str = Field(pattern="^(ARM_CONTROL|ARM_DUNNFLOW)$")
    seed: int = Field(ge=0, le=2**31 - 1)
    n: int = Field(ge=1, le=2000)
    llm_mode: str = Field(default="STUB", pattern="^(STUB|T1_ONLY|FULL)$")


class ApproveIn(BaseModel):
    model_config = _IN
    confirmed_case_ref: str = Field(min_length=1, max_length=32)
    actor: str = Field(default="operator", max_length=64)


class RejectIn(BaseModel):
    model_config = _IN
    reason: str = Field(min_length=1, max_length=500)
    actor: str = Field(default="operator", max_length=64)


class KillSwitchIn(BaseModel):
    model_config = _IN
    armed: bool


class CaseIntakeIn(BaseModel):
    model_config = _IN
    merchant_id: str = Field(min_length=1, max_length=64)
    obligation_ref: str = Field(min_length=1, max_length=64)
    amount_minor: int = Field(gt=0, le=10_000_000_000)
    failure_source: str = Field(default="gateway", min_length=1, max_length=64)
    failure_step: str = Field(default="payment_authorization", min_length=1, max_length=64)
    failure_reason: str = Field(default="gateway_timeout", min_length=1, max_length=128)
    error_description: str = Field(min_length=10, max_length=2000)
    customer_tokens: list[str] = Field(default_factory=list)
    retry_count: int = Field(default=0, ge=0, le=20)
