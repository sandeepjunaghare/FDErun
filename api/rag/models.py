"""Typed shapes for the condition-briefing corpus and search results (interface notes 2–4)."""

from datetime import date
from typing import Literal

from pydantic import BaseModel

Section = Literal["standard_of_care", "emerging_treatments", "key_institutions"]
SECTIONS: tuple[Section, ...] = ("standard_of_care", "emerging_treatments", "key_institutions")


class Condition(BaseModel):
    id: str
    name: str
    aliases: list[str]


class RetrievedChunk(BaseModel):
    """Same names and types as evals/contract.py's RetrievedChunk (api/ can't import evals/)."""

    chunk_id: str
    doc: str
    text: str
    score: float | None = None
    section: str | None = None
    source_label: str | None = None
    as_of: date | None = None


class Chunk(BaseModel):
    chunk_id: str
    doc: str
    ord: int
    condition_id: str
    section: Section
    text: str


class Document(BaseModel):
    doc: str
    condition_id: str
    condition_name: str
    aliases: list[str]
    section: Section
    title: str
    source_label: str
    source_type: str
    as_of: date
    chunks: list[Chunk]
