from datetime import date
from pathlib import Path

import pytest

from rag.corpus import CorpusError, chunk_paragraphs, load_corpus, parse_document, validate

CORPUS = Path(__file__).resolve().parents[2] / "corpus" / "condition-briefing"

FRONT = """---
condition: Test condition
aliases: [TC, test cond]
section: {section}
title: "Test condition — {section}"
source_label: "Synthetic test source"
source_type: {source_type}
as_of: 2026-01-15
synthetic: true
---

First paragraph about test condition,
wrapped over two lines.

Second paragraph about test condition.
"""
SOURCE_TYPES = {
    "standard_of_care": "guideline_summary",
    "emerging_treatments": "pipeline_digest",
    "key_institutions": "landscape_profile",
}


def write_condition(root: Path, slug: str = "test-condition", skip: str | None = None) -> Path:
    folder = root / slug
    folder.mkdir(parents=True)
    for section, source_type in SOURCE_TYPES.items():
        if section != skip:
            text = FRONT.format(section=section, source_type=source_type)
            (folder / f"{section}.md").write_text(text)
    return folder


def test_chunk_paragraphs_joins_wrapped_lines_and_drops_blanks():
    body = "\nOne,\nwrapped.\n\n\n  \nTwo.\n\n"
    assert chunk_paragraphs(body) == ["One, wrapped.", "Two."]


def test_parse_document_labels_and_stable_chunk_ids(tmp_path):
    folder = write_condition(tmp_path)
    d = parse_document(folder / "emerging_treatments.md")
    assert d.doc == "test-condition/emerging_treatments.md"
    assert d.condition_id == "test-condition"
    assert d.condition_name == "Test condition"
    assert d.aliases == ["TC", "test cond"]
    assert d.section == "emerging_treatments"
    assert d.source_label == "Synthetic test source"
    assert d.as_of == date(2026, 1, 15)
    assert [c.chunk_id for c in d.chunks] == [
        "test-condition-emerging_treatments-0",
        "test-condition-emerging_treatments-1",
    ]
    assert d.chunks[0].text == "First paragraph about test condition, wrapped over two lines."
    assert {c.section for c in d.chunks} == {"emerging_treatments"}
    # Stable: parsing again yields the same ids.
    assert parse_document(folder / "emerging_treatments.md").chunks == d.chunks


def test_bad_corpus_is_refused(tmp_path):
    write_condition(tmp_path, skip="key_institutions")
    with pytest.raises(CorpusError) as exc:
        validate(tmp_path)
    assert any("key_institutions.md: missing" in p for p in exc.value.problems)


def test_missing_corpus_dir_is_refused(tmp_path):
    with pytest.raises(CorpusError):
        load_corpus(tmp_path / "nope")


def test_real_corpus_loads():
    docs = load_corpus(CORPUS)
    assert len(docs) == 30
    assert len({d.condition_id for d in docs}) == 10
    chunks = [c for d in docs for c in d.chunks]
    assert len({c.chunk_id for c in chunks}) == len(chunks)
    assert all(c.text and c.section == d.section for d in docs for c in d.chunks)
    hf = next(d for d in docs if d.condition_id == "heart-failure")
    assert "CHF" in hf.aliases
