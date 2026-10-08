"""Public request/response shapes; mirrors `evals/contract.py` (a separate uv project) exactly."""

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field

Action = Literal["answer", "refuse", "redact", "escalate"]
Section = Literal["standard_of_care", "emerging_treatments", "key_institutions"]
SECTIONS: tuple[Section, ...] = ("standard_of_care", "emerging_treatments", "key_institutions")
SECTION_HEADINGS: dict[Section, str] = {
    "standard_of_care": "## Current standard of care",
    "emerging_treatments": "## Emerging treatments",
    "key_institutions": "## Key companies and institutions",
}


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    user_id: str = Field(min_length=1, max_length=200)
    # Optional so the eval harness's {"question", "user_id"} still works (interface note 7).
    session_id: str | None = Field(default=None, max_length=200)


class RetrievedChunk(BaseModel):
    chunk_id: str
    doc: str
    text: str
    score: float | None = None
    section: str | None = None
    source_label: str | None = None
    as_of: date | None = None


class AskResponse(BaseModel):
    answer: str
    citations: list[str] = Field(default_factory=list)
    action: Action = "answer"
    retrieved: list[RetrievedChunk] = Field(default_factory=list)
    # Additive: lets the UI keep the session after the first turn.
    session_id: str | None = None


class Condition(BaseModel):
    id: str
    name: str
    aliases: list[str] = Field(default_factory=list)
