import asyncio

import pytest

from agents.errors import LLMError, LLMRefusal
from agents.pipeline import REFUSALS, ask, run
from memory.store import InMemoryStore
from schemas import (
    SECTION_HEADINGS,
    AskRequest,
    BriefingDraft,
    Claim,
    CriticVerdict,
    FollowUpDraft,
    PlannerOutput,
)
from tests.fakes import (
    BRIEFING,
    FOLLOW_UP,
    PASS,
    FakeLLM,
    FakeSearch,
    good_draft,
    make_deps,
    wrong_section_draft,
)


def events(req, deps):
    async def collect():
        return [e async for e in run(req, deps)]

    return asyncio.run(collect())


def req(question="Briefing on CHF", **kw):
    return AskRequest(question=question, user_id="u1", **kw)


# --- refusals: stop before any retrieval ---


@pytest.mark.parametrize(
    ("planned", "reason"),
    [
        (PlannerOutput(intent="out_of_scope", refuse_reason="unrelated"), "unrelated"),
        (PlannerOutput(intent="out_of_scope", refuse_reason="clinical_advice"), "clinical_advice"),
        (
            PlannerOutput(intent="out_of_scope", refuse_reason="unknown_condition"),
            "unknown_condition",
        ),
        (PlannerOutput(intent="briefing", condition_id="lupus"), "unknown_condition"),
    ],
)
def test_refusals_never_search(planned, reason):
    search = FakeSearch()
    deps = make_deps(FakeLLM(planned), search)
    out = asyncio.run(ask(req("What's the weather?"), deps))
    assert out.action == "refuse"
    assert out.answer == REFUSALS[reason]
    assert out.citations == [] and out.retrieved == []
    assert search.calls == []


def test_model_refusal_in_planner_is_a_refusal():
    deps = make_deps(FakeLLM((PlannerOutput, LLMRefusal("haiku"))))
    out = asyncio.run(ask(req("How much metoprolol for my dad?"), deps))
    assert out.action == "refuse"


# --- happy path ---


def test_briefing_happy_path():
    search = FakeSearch()
    llm = FakeLLM(BRIEFING, good_draft(), PASS)
    deps = make_deps(llm, search)
    evs = events(req(), deps)
    names = [n for n, _ in evs]
    agents = [d["agent"] for n, d in evs if n == "status"]
    assert agents == ["planner", "retriever", "answerer", "critic"]
    assert names[-1] == "done" and names.count("done") == 1
    assert names.index("token") > names.index("status") + 3  # tokens only after the critic

    done = evs[-1][1]
    assert done["action"] == "answer"
    assert done["citations"] == ["hf-soc-0", "hf-em-0", "hf-ki-0"]
    assert {c["chunk_id"] for c in done["retrieved"]} >= set(done["citations"])
    assert all(c["source_label"] and c["as_of"] for c in done["retrieved"])
    for heading in SECTION_HEADINGS.values():
        assert done["answer"].count(heading) == 1
    assert "".join(d["text"] for n, d in evs if n == "token") == done["answer"]

    # Retriever: three section-filtered searches for the resolved condition.
    assert sorted(s for _, _, s in search.calls) == sorted(SECTION_HEADINGS)
    assert {c for _, c, _ in search.calls} == {"heart-failure"}
    # Models: haiku planner/critic, sonnet answerer.
    assert [c["model"] for c in llm.calls] == [
        "claude-haiku-4-5",
        "claude-sonnet-5-5",
        "claude-haiku-4-5",
    ]


def test_planner_gets_code_alias_hint():
    llm = FakeLLM(BRIEFING, good_draft(), PASS)
    asyncio.run(ask(req("CHF please"), make_deps(llm)))
    assert "Code matched the condition name: heart-failure." in llm.calls[0]["prompt"]


# --- critic: retry once, then refuse ---


def test_section_integrity_rejection_retries_then_passes():
    llm = FakeLLM(BRIEFING, wrong_section_draft(), good_draft(), PASS)
    out = asyncio.run(ask(req(), make_deps(llm)))
    assert out.action == "answer"
    # The code check rejected draft 1 without an LLM critic call; the retry carries the reason.
    assert llm.formats() == ["PlannerOutput", "BriefingDraft", "BriefingDraft", "CriticVerdict"]
    assert "from section emerging_treatments" in llm.calls[2]["prompt"]


def test_retry_then_refuse_streams_no_draft_text():
    llm = FakeLLM(BRIEFING, wrong_section_draft(), wrong_section_draft())
    evs = events(req(), make_deps(llm))
    done = evs[-1][1]
    assert done["action"] == "refuse"
    assert done["answer"] == REFUSALS["unchecked"]
    assert done["citations"] == []
    tokens = [d["text"] for n, d in evs if n == "token"]
    assert tokens == [REFUSALS["unchecked"]]
    assert llm.formats().count("BriefingDraft") == 2


def test_faithfulness_failure_retries():
    bad = CriticVerdict(faithful=False, unsupported_claims=["GDMT is standard."])
    llm = FakeLLM(BRIEFING, good_draft(), good_draft(), bad, PASS)
    out = asyncio.run(ask(req(), make_deps(llm)))
    assert out.action == "answer"
    assert "unsupported claim: GDMT is standard." in llm.calls[3]["prompt"]


def test_no_evidence_refuses():
    deps = make_deps(FakeLLM(BRIEFING), FakeSearch(chunks={}))
    assert asyncio.run(ask(req(), deps)).action == "refuse"


# --- memory: follow-up + recent ---


def test_follow_up_answers_from_session_chunks_without_searching():
    search = FakeSearch()
    follow = FollowUpDraft(claims=[Claim(text="HCV-11 is in Phase 3.", chunk_ids=["hf-em-0"])])
    llm = FakeLLM(BRIEFING, good_draft(), PASS, FOLLOW_UP, follow, PASS)
    deps = make_deps(llm, search)
    first = asyncio.run(ask(req(), deps))
    searches = len(search.calls)

    second = asyncio.run(ask(req("Which of those are Phase 3?", session_id=first.session_id), deps))
    assert second.session_id == first.session_id
    assert second.action == "answer"
    assert second.citations == ["hf-em-0"]
    assert len(search.calls) == searches  # no new retrieval
    assert "A briefing on Heart failure exists" in llm.calls[3]["prompt"]


def test_follow_up_without_briefing_refuses():
    deps = make_deps(FakeLLM(FOLLOW_UP))
    assert asyncio.run(ask(req("Which of those are Phase 3?"), deps)).action == "refuse"


def test_session_of_another_user_is_not_reused():
    deps = make_deps(FakeLLM(BRIEFING, good_draft(), PASS, FOLLOW_UP))
    first = asyncio.run(ask(req(), deps))
    other = AskRequest(question="Which are Phase 3?", user_id="u2", session_id=first.session_id)
    out = asyncio.run(ask(other, deps))
    assert out.session_id != first.session_id
    assert out.action == "refuse"  # u2 has no briefing to follow up on


def test_recent_conditions_newest_first():
    asthma = PlannerOutput(intent="briefing", condition_id="asthma")
    llm = FakeLLM(BRIEFING, good_draft(), PASS, asthma, good_draft(), PASS)
    deps = make_deps(llm)
    asyncio.run(ask(req(), deps))
    asyncio.run(ask(req("asthma"), deps))
    recent = asyncio.run(deps.memory.recent("u1"))
    assert [cid for cid, _ in recent] == ["asthma", "heart-failure"]


# --- PII ---


def test_pii_is_redacted_before_the_planner_and_storage():
    llm = FakeLLM(BRIEFING, good_draft(), PASS)
    deps = make_deps(llm)
    out = asyncio.run(ask(req("Briefing on CHF for my patient John Smith"), deps))
    assert out.action == "redact"
    assert all("John Smith" not in c["prompt"] for c in llm.calls)
    assert isinstance(deps.memory, InMemoryStore)
    assert all("John Smith" not in content for _, _, content, _ in deps.memory.turns)


# --- errors ---


def test_llm_error_propagates_as_pipeline_error():
    deps = make_deps(FakeLLM(BRIEFING, (BriefingDraft, LLMError("APIConnectionError"))))
    with pytest.raises(LLMError):
        asyncio.run(ask(req(), deps))


def test_client_chosen_session_id_is_kept():
    deps = make_deps(FakeLLM(BRIEFING, good_draft(), PASS))
    out = asyncio.run(ask(req(session_id="eval-run1-hf"), deps))
    assert out.session_id == "eval-run1-hf"
