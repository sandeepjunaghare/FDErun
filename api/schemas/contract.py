"""Public request/response shapes; mirrors `evals/contract.py` (a separate uv project) exactly.

`RetrievedChunk`, `Condition`, `Section` come from `rag.models` (pane B) so the retriever's output
and the response use one class each; Pydantic rejects an instance of a look-alike class.
"""

from typing import Literal

from pydantic import BaseModel, Field

from rag.models import SECTIONS, Condition, RetrievedChunk, Section

Action = Literal["answer", "refuse", "redact", "escalate"]
SECTION_HEADINGS: dict[Section, str] = {
    "standard_of_care": "## Current standard of care",
    "emerging_treatments": "## Emerging treatments",
    "key_institutions": "## Key companies and institutions",
}

__all__ = [
    "SECTIONS",
    "SECTION_HEADINGS",
    "Action",
    "AskRequest",
    "AskResponse",
    "Condition",
    "RetrievedChunk",
    "Section",
]


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    user_id: str = Field(min_length=1, max_length=200)
    # Optional so the eval harness's {"question", "user_id"} still works (interface note 7).
    session_id: str | None = Field(default=None, max_length=200)


class AskResponse(BaseModel):
    answer: str
    citations: list[str] = Field(default_factory=list)
    action: Action = "answer"
    retrieved: list[RetrievedChunk] = Field(default_factory=list)
    # Additive: lets the UI keep the session after the first turn.
    session_id: str | None = None
