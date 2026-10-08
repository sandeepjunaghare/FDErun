"""Turn an AskResponse into what the screen shows: sections, cited sources, and as-of dates."""

import re
from dataclasses import dataclass, field
from datetime import date
from typing import Literal

from models import AskResponse, RetrievedChunk

# The answerer's fixed headings (ticket T1) → corpus section labels.
HEADINGS: dict[str, str] = {
    "Current standard of care": "standard_of_care",
    "Emerging treatments": "emerging_treatments",
    "Key companies and institutions": "key_institutions",
}
TITLES = {section: title for title, section in HEADINGS.items()}
PREAMBLE = "preamble"

DEFAULT_REFUSAL = (
    "This assistant only gives condition briefings from its sample corpus; it can't answer that."
)
REDACTED = "Patient identifiers were removed from your question before it was processed."

Notice = tuple[Literal["info", "warning"], str]


@dataclass
class SourceRef:
    number: int
    chunk_id: str
    doc: str
    source_label: str
    as_of: date | None


@dataclass
class SectionView:
    section: str
    title: str
    body: str
    sources: list[SourceRef] = field(default_factory=list)

    @property
    def newest_as_of(self) -> date | None:
        dates = [s.as_of for s in self.sources if s.as_of]
        return max(dates) if dates else None


def split_sections(answer: str) -> dict[str, str]:
    """Split markdown on `## ` headings; known headings map to their section, the rest is kept."""
    parts: dict[str, list[str]] = {}
    key = PREAMBLE
    for line in answer.splitlines():
        match = re.match(r"^##\s+(.+?)\s*$", line)
        if match:
            title = match.group(1)
            key = HEADINGS.get(title, title)
            parts.setdefault(key, [])
        else:
            parts.setdefault(key, []).append(line)
    sections = {k: "\n".join(v).strip() for k, v in parts.items()}
    return {k: v for k, v in sections.items() if v or k != PREAMBLE}


def _section_of(chunk: RetrievedChunk, bodies: dict[str, str]) -> str | None:
    if chunk.section in bodies:
        return chunk.section
    return next((key for key, body in bodies.items() if chunk.chunk_id in body), None)


def build_briefing(resp: AskResponse) -> list[SectionView]:
    """Sections in answer order, each with its cited chunks, numbered 1…n across the briefing."""
    bodies = split_sections(resp.answer)
    views = {key: SectionView(key, TITLES.get(key, key), body) for key, body in bodies.items()}
    by_id = {c.chunk_id: c for c in resp.retrieved}
    number = 0
    for chunk_id in dict.fromkeys(resp.citations):
        chunk = by_id.get(chunk_id)
        if chunk is None:
            continue
        key = _section_of(chunk, bodies)
        if key is None:
            key = PREAMBLE
            views.setdefault(key, SectionView(key, "Other sources", ""))
        number += 1
        views[key].sources.append(
            SourceRef(
                number=number,
                chunk_id=chunk.chunk_id,
                doc=chunk.doc,
                source_label=chunk.source_label or "Source label unavailable",
                as_of=chunk.as_of,
            )
        )
    return list(views.values())


def annotate(view: SectionView) -> str:
    """Replace inline `[chunk_id]` markers with the source's `[n]`; other text is untouched."""
    body = view.body
    for src in view.sources:
        body = body.replace(f"[{src.chunk_id}]", f"**[{src.number}]**")
    return body


def format_source(src: SourceRef) -> str:
    when = f"as of {src.as_of.isoformat()}" if src.as_of else "date unknown"
    return f"[{src.number}] {src.source_label} · {when} · `{src.doc}`"


def notice_for(resp: AskResponse) -> Notice | None:
    """A message for a non-answer (refusal, redaction, escalation); None for a normal briefing."""
    if resp.action == "refuse":
        return "info", resp.answer.strip() or DEFAULT_REFUSAL
    if resp.action == "redact":
        return "warning", f"{REDACTED} {resp.answer.strip()}".strip()
    if resp.action == "escalate":
        return "info", resp.answer.strip() or "This question needs a person to review it."
    return None
