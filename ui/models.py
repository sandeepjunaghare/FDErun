"""Mirror of evals/contract.py (the /ask and /chat contract) — keep names in sync.

The ui Docker build context is ./ui, so the contract is mirrored here rather than imported.
"""

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Action = Literal["answer", "refuse", "redact", "escalate"]
Section = Literal["standard_of_care", "emerging_treatments", "key_institutions"]


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


class ChatRequest(BaseModel):
    question: str
    user_id: str
    session_id: str | None = None


class RecentCondition(BaseModel):
    """One row of GET /recent. Permissive: pane A hasn't fixed the shape yet."""

    model_config = ConfigDict(extra="ignore")

    condition_id: str
    name: str | None = None
    viewed_at: datetime | None = None

    @property
    def label(self) -> str:
        return self.name or self.condition_id.replace("-", " ").replace("_", " ")
