from datetime import date

from briefing import (
    DEFAULT_REFUSAL,
    PREAMBLE,
    annotate,
    build_briefing,
    format_source,
    notice_for,
    split_sections,
)
from models import AskResponse, RetrievedChunk

ANSWER = """## Current standard of care
Four classes [soc-0].

## Emerging treatments
HCV-11 is in Phase 3 [em-0]; BWG-3 is Phase 1/2 [em-1].

## Key companies and institutions
Halvard Cardio [ki-0].
"""


def chunk(
    chunk_id: str, section: str | None, as_of: date | None, label: str | None = "Synthetic X"
):
    return RetrievedChunk(
        chunk_id=chunk_id,
        doc=f"hf/{section}.md",
        text="t",
        section=section,
        source_label=label,
        as_of=as_of,
    )


CHUNKS = [
    chunk("soc-0", "standard_of_care", date(2026, 5, 20)),
    chunk("em-0", "emerging_treatments", date(2026, 9, 12)),
    chunk("em-1", "emerging_treatments", date(2026, 8, 1)),
    chunk("ki-0", "key_institutions", date(2025, 12, 3)),
    chunk("unused", "key_institutions", date(2026, 10, 1)),
]


def resp(**kw) -> AskResponse:
    defaults = {
        "answer": ANSWER,
        "citations": ["soc-0", "em-0", "em-1", "ki-0"],
        "retrieved": CHUNKS,
    }
    return AskResponse.model_validate(defaults | kw)


def test_split_sections_maps_the_three_headings():
    sections = split_sections(ANSWER)
    assert list(sections) == ["standard_of_care", "emerging_treatments", "key_institutions"]
    assert sections["emerging_treatments"].startswith("HCV-11")


def test_split_sections_keeps_unknown_headings_and_preamble():
    sections = split_sections("Intro line\n## Something else\nbody")
    assert sections == {PREAMBLE: "Intro line", "Something else": "body"}


def test_build_briefing_attaches_only_cited_chunks_with_newest_date():
    views = {v.section: v for v in build_briefing(resp())}
    em = views["emerging_treatments"]
    assert [s.chunk_id for s in em.sources] == ["em-0", "em-1"]
    assert em.newest_as_of == date(2026, 9, 12)
    assert views["key_institutions"].newest_as_of == date(2025, 12, 3)  # "unused" not cited
    assert [s.number for v in views.values() for s in v.sources] == [1, 2, 3, 4]
    assert views["standard_of_care"].title == "Current standard of care"


def test_build_briefing_falls_back_to_marker_when_section_missing():
    chunks = [chunk("em-0", None, None, label=None)]
    views = {v.section: v for v in build_briefing(resp(citations=["em-0"], retrieved=chunks))}
    src = views["emerging_treatments"].sources[0]
    assert src.source_label == "Source label unavailable"
    assert "date unknown" in format_source(src)


def test_build_briefing_ignores_citations_not_retrieved():
    views = build_briefing(resp(citations=["ghost"]))
    assert all(not v.sources for v in views)


def test_annotate_numbers_inline_markers():
    views = {v.section: v for v in build_briefing(resp())}
    text = annotate(views["emerging_treatments"])
    assert "[em-0]" not in text and "**[2]**" in text and "**[3]**" in text


def test_format_source_shows_label_and_date():
    views = build_briefing(resp())
    assert format_source(views[0].sources[0]) == (
        "[1] Synthetic X · as of 2026-05-20 · `hf/standard_of_care.md`"
    )


def test_notice_for_each_action():
    assert notice_for(resp()) is None
    assert notice_for(resp(action="refuse", answer="")) == ("info", DEFAULT_REFUSAL)
    assert notice_for(resp(action="refuse", answer="Out of scope.")) == ("info", "Out of scope.")
    kind, text = notice_for(resp(action="redact", answer="")) or ("", "")
    assert kind == "warning" and "identifiers were removed" in text
    assert (notice_for(resp(action="escalate", answer="")) or ("",))[0] == "info"
