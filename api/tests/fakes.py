"""Offline stand-ins for the LLM, pane B's search/conditions, and settings."""

from collections import defaultdict
from datetime import date
from typing import Any

from pydantic import BaseModel

from agents.pipeline import PipelineDeps
from config import Settings
from memory.store import InMemoryStore
from schemas import (
    BriefingDraft,
    Claim,
    Condition,
    CriticVerdict,
    PlannerOutput,
    RetrievedChunk,
    Section,
)

SETTINGS = Settings(database_url="postgresql://u:p@h:5432/db")

CONDITIONS = [
    Condition(id="heart-failure", name="Heart failure", aliases=["HF", "CHF", "HFpEF"]),
    Condition(id="asthma", name="Asthma", aliases=[]),
]


def chunk(cid: str, section: Section, text: str = "") -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=cid,
        doc=f"heart-failure/{section}.md",
        text=text or f"text of {cid}",
        score=0.8,
        section=section,
        source_label="Synthetic source — FDErun corpus v1",
        as_of=date(2026, 9, 12),
    )


CHUNKS: dict[Section, list[RetrievedChunk]] = {
    "standard_of_care": [chunk("hf-soc-0", "standard_of_care")],
    "emerging_treatments": [chunk("hf-em-0", "emerging_treatments", "HCV-11 is in Phase 3.")],
    "key_institutions": [chunk("hf-ki-0", "key_institutions")],
}


def good_draft() -> BriefingDraft:
    return BriefingDraft(
        standard_of_care=[Claim(text="GDMT is standard.", chunk_ids=["hf-soc-0"])],
        emerging_treatments=[Claim(text="HCV-11 is in Phase 3.", chunk_ids=["hf-em-0"])],
        key_institutions=[Claim(text="Halvard Cardio leads.", chunk_ids=["hf-ki-0"])],
    )


def wrong_section_draft() -> BriefingDraft:
    draft = good_draft()
    draft.key_institutions = [Claim(text="HCV-11 is in Phase 3.", chunk_ids=["hf-em-0"])]
    return draft


BRIEFING = PlannerOutput(intent="briefing", condition_id="heart-failure")
FOLLOW_UP = PlannerOutput(intent="follow_up", condition_id="heart-failure")
PASS = CriticVerdict(faithful=True)


class FakeLLM:
    """Scripted outputs per output_format, in order. `(Format, exc)` raises exc for that format."""

    def __init__(self, *script: BaseModel | tuple[type, Exception]):
        self.queues: dict[type, list[Any]] = defaultdict(list)
        self.calls: list[dict[str, Any]] = []
        for item in script:
            if isinstance(item, tuple):
                self.queues[item[0]].append(item[1])
            else:
                self.queues[type(item)].append(item)

    async def parse(self, *, model, system, prompt, output_format, max_tokens=1024, extra=None):
        self.calls.append({"model": model, "prompt": prompt, "format": output_format})
        queue = self.queues[output_format]
        assert queue, f"no scripted output for {output_format.__name__}"
        item = queue.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    def formats(self) -> list[str]:
        return [c["format"].__name__ for c in self.calls]


class FakeSearch:
    def __init__(self, chunks: dict[Section, list[RetrievedChunk]] | None = None):
        self.chunks = CHUNKS if chunks is None else chunks
        self.calls: list[tuple[str, str, str]] = []

    async def __call__(self, pool, query, condition_id, section, k=5):
        self.calls.append((query, condition_id, section))
        return self.chunks.get(section, [])[:k]


async def fake_conditions(pool) -> list[Condition]:
    return CONDITIONS


def make_deps(llm: FakeLLM, search: FakeSearch | None = None) -> PipelineDeps:
    return PipelineDeps(
        llm=llm,
        settings=SETTINGS,
        search=search or FakeSearch(),
        list_conditions=fake_conditions,
        memory=InMemoryStore(),
    )
