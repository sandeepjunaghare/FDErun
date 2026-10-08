"""Stand-in for POST /chat until pane A's pipeline merges: same events, canned heart failure."""

import re
import time
from collections.abc import Iterator
from datetime import date

from client import ChatEvent
from models import AskResponse, RetrievedChunk

AGENTS = ("planner", "retriever", "answerer", "critic")

CHUNKS = [
    RetrievedChunk(
        chunk_id="heart-failure-standard_of_care-0",
        doc="heart-failure/standard_of_care.md",
        text="HFrEF is treated with four medication classes started early and titrated: an ARNI, "
        "a beta blocker, a mineralocorticoid receptor antagonist, and an SGLT2 inhibitor.",
        section="standard_of_care",
        source_label="Synthetic guideline summary — FDErun corpus v1",
        as_of=date(2026, 5, 20),
    ),
    RetrievedChunk(
        chunk_id="heart-failure-standard_of_care-2",
        doc="heart-failure/standard_of_care.md",
        text="For HFpEF, SGLT2 inhibitors are part of standard therapy, along with diuretics.",
        section="standard_of_care",
        source_label="Synthetic guideline summary — FDErun corpus v1",
        as_of=date(2026, 5, 20),
    ),
    RetrievedChunk(
        chunk_id="heart-failure-emerging_treatments-0",
        doc="heart-failure/emerging_treatments.md",
        text="HCV-11, from Halvard Cardio (fictional), is an oral myosin modulator in Phase 3.",
        section="emerging_treatments",
        source_label="Synthetic pipeline digest — FDErun corpus v1",
        as_of=date(2026, 9, 12),
    ),
    RetrievedChunk(
        chunk_id="heart-failure-emerging_treatments-1",
        doc="heart-failure/emerging_treatments.md",
        text="BWG-3, from Brightwater Genetics (fictional), is a gene therapy in Phase 1/2.",
        section="emerging_treatments",
        source_label="Synthetic pipeline digest — FDErun corpus v1",
        as_of=date(2026, 9, 12),
    ),
    RetrievedChunk(
        chunk_id="heart-failure-key_institutions-0",
        doc="heart-failure/key_institutions.md",
        text="Halvard Cardio (fictional) is the leading developer of myosin-modulator drugs.",
        section="key_institutions",
        source_label="Synthetic landscape profile — FDErun corpus v1",
        as_of=date(2025, 12, 3),
    ),
]

BRIEFING = """## Current standard of care
Heart failure with reduced ejection fraction is treated with four medication classes, started \
early: an ARNI, a beta blocker, an MRA, and an SGLT2 inhibitor [heart-failure-standard_of_care-0]. \
With preserved ejection fraction, SGLT2 inhibitors are standard alongside diuretics \
[heart-failure-standard_of_care-2].

## Emerging treatments
HCV-11 (Halvard Cardio, fictional) is an oral myosin modulator in Phase 3 \
[heart-failure-emerging_treatments-0]; BWG-3 (Brightwater Genetics, fictional) is a one-time \
gene therapy in Phase 1/2 [heart-failure-emerging_treatments-1].

## Key companies and institutions
Halvard Cardio (fictional) leads myosin-modulator development [heart-failure-key_institutions-0].
"""

FOLLOW_UP = """## Emerging treatments
Of those, HCV-11 is in Phase 3 [heart-failure-emerging_treatments-0].
"""

REFUSAL = (
    "I can only give condition briefings (standard of care, emerging treatments, key companies) "
    "for the conditions in the corpus. I can't help with that question."
)
PII = re.compile(r"\b(patient|mr\.?|mrs\.?|ms\.?)\s+[A-Z][a-z]+", re.IGNORECASE)
OFF_TOPIC = re.compile(r"\b(weather|should i|my (dose|medication)|stock price)\b", re.IGNORECASE)


def respond(question: str) -> AskResponse:
    """The AskResponse the stub returns for a question."""
    if OFF_TOPIC.search(question):
        return AskResponse(answer=REFUSAL, action="refuse")
    if PII.search(question):
        return AskResponse(
            answer="Ask about the condition rather than a named person.",
            action="redact",
        )
    if "phase 3" in question.lower() or question.lower().startswith(("which", "what about")):
        return AskResponse(
            answer=FOLLOW_UP,
            citations=["heart-failure-emerging_treatments-0"],
            retrieved=CHUNKS,
        )
    return AskResponse(answer=BRIEFING, citations=[c.chunk_id for c in CHUNKS], retrieved=CHUNKS)


def stub_chat_events(question: str, *, delay: float = 0.3) -> Iterator[ChatEvent]:
    """Yield status → token… → done, as POST /chat does. Refusals stop after the planner."""
    resp = respond(question)
    agents = AGENTS if resp.action == "answer" else AGENTS[:1]
    for agent in agents:
        yield "status", {"agent": agent}
        time.sleep(delay)
    if resp.action == "answer":
        for piece in re.findall(r"\S+\s*", resp.answer):
            yield "token", {"text": piece}
            time.sleep(delay / 30)
    yield "done", resp.model_dump(mode="json")
