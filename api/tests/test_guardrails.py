import pytest

from guardrails.citations import check_draft
from guardrails.pii import redact
from guardrails.scope import check_scope, match_condition
from schemas import Claim, FollowUpDraft, PlannerOutput
from tests.fakes import CHUNKS, CONDITIONS, good_draft, wrong_section_draft

RETRIEVED = [c for chunks in CHUNKS.values() for c in chunks]


# --- PII ---


@pytest.mark.parametrize(
    ("text", "kind", "gone"),
    [
        ("Briefing on CHF for my patient John Smith", "NAME", "John Smith"),
        ("Mrs. Lee has asthma, what's new?", "NAME", "Lee"),
        ("Patient MRN: 00123456 has heart failure", "MRN", "00123456"),
        ("DOB 04/12/1961, asthma briefing", "DOB", "04/12/1961"),
        ("email jane.doe@example.com about COPD", "EMAIL", "jane.doe@example.com"),
        ("call 415-555-0134 re heart failure", "PHONE", "415-555-0134"),
        ("SSN 123-45-6789", "SSN", "123-45-6789"),
    ],
)
def test_redacts_patient_identifiers(text, kind, gone):
    out, found = redact(text)
    assert kind in found
    assert gone not in out
    assert f"[REDACTED-{kind}]" in out


@pytest.mark.parametrize(
    "text",
    [
        "Briefing on CHF",
        "What are the emerging treatments for COPD and NSCLC?",
        "Key institutions in heart failure as of 2026",
        "Which of those are Phase 3?",
    ],
)
def test_leaves_plain_questions_alone(text):
    assert redact(text) == (text, [])


# --- scope ---


def test_alias_resolves_to_condition():
    match = match_condition("Give me a briefing on CHF", CONDITIONS)
    assert match is not None and match.id == "heart-failure"


def test_longest_alias_wins_and_no_partial_words():
    assert match_condition("HFpEF pipeline", CONDITIONS).id == "heart-failure"  # type: ignore[union-attr]
    assert match_condition("asthmatic weather", CONDITIONS) is None


@pytest.mark.parametrize(
    ("plan", "has_briefing", "reason"),
    [
        (
            PlannerOutput(intent="out_of_scope", refuse_reason="clinical_advice"),
            False,
            "clinical_advice",
        ),
        (PlannerOutput(intent="out_of_scope"), False, "unrelated"),
        (PlannerOutput(intent="briefing", condition_id="made-up"), False, "unknown_condition"),
        (PlannerOutput(intent="briefing", condition_id=None), False, "unknown_condition"),
        (PlannerOutput(intent="follow_up"), False, "unknown_condition"),
        (PlannerOutput(intent="follow_up"), True, None),
        (PlannerOutput(intent="briefing", condition_id="asthma"), False, None),
    ],
)
def test_check_scope(plan, has_briefing, reason):
    assert check_scope(plan, CONDITIONS, has_briefing) == reason


# --- citations + section integrity ---


def test_good_draft_passes():
    assert check_draft(good_draft(), RETRIEVED) == []


def test_section_integrity_rejects_wrong_section_citation():
    problems = check_draft(wrong_section_draft(), RETRIEVED)
    assert len(problems) == 1
    assert "under key_institutions cites hf-em-0 from section emerging_treatments" in problems[0]


def test_rejects_uncited_and_unretrieved_claims_and_empty_sections():
    draft = good_draft()
    draft.standard_of_care = [Claim(text="No source.", chunk_ids=[])]
    draft.emerging_treatments = [Claim(text="Invented.", chunk_ids=["nope-1"])]
    draft.key_institutions = []
    problems = check_draft(draft, RETRIEVED)
    assert any("cites nothing" in p for p in problems)
    assert any("nope-1, which was not retrieved" in p for p in problems)
    assert any("key_institutions has no claims" in p for p in problems)


def test_follow_up_draft_needs_retrieved_citations_only():
    ok = FollowUpDraft(claims=[Claim(text="HCV-11 is Phase 3.", chunk_ids=["hf-em-0"])])
    assert check_draft(ok, RETRIEVED) == []
    assert check_draft(FollowUpDraft(claims=[]), RETRIEVED) == ["the answer has no claims"]
