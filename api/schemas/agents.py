"""Typed agent outputs. Guardrails check these models, not free text."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

RefuseReason = Literal[
    "unrelated", "clinical_advice", "unknown_condition", "no_evidence", "unchecked"
]


class PlannerOutput(BaseModel):
    intent: Literal["briefing", "follow_up", "out_of_scope"]
    condition_id: str | None = None
    refuse_reason: Literal["unrelated", "clinical_advice", "unknown_condition"] | None = None
    rationale: str = ""


class Claim(BaseModel):
    text: str
    chunk_ids: list[str] = Field(default_factory=list)


class BriefingDraft(BaseModel):
    standard_of_care: list[Claim]
    emerging_treatments: list[Claim]
    key_institutions: list[Claim]


class FollowUpDraft(BaseModel):
    claims: list[Claim]


class CriticVerdict(BaseModel):
    faithful: bool
    unsupported_claims: list[str] = Field(default_factory=list)


class RecentCondition(BaseModel):
    condition_id: str
    name: str
    viewed_at: datetime


class RecentResponse(BaseModel):
    user_id: str
    conditions: list[RecentCondition]
