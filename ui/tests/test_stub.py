from briefing import build_briefing
from models import AskResponse
from stub import stub_chat_events


def run(question: str) -> tuple[list[str], AskResponse]:
    events = list(stub_chat_events(question, delay=0))
    names = [e for e, _ in events]
    assert names[-1] == "done"
    return names, AskResponse.model_validate(events[-1][1])


def test_briefing_streams_all_stages_then_tokens_then_done():
    names, resp = run("heart failure")
    stages = [n for n in names if n == "status"]
    assert len(stages) == 4 and names[:4] == ["status"] * 4
    assert "token" in names and names.index("token") > 3
    assert resp.action == "answer"
    assert set(resp.citations) <= {c.chunk_id for c in resp.retrieved}


def test_briefing_has_three_sections_with_different_dates():
    _, resp = run("heart failure")
    views = build_briefing(resp)
    assert [v.title for v in views] == [
        "Current standard of care",
        "Emerging treatments",
        "Key companies and institutions",
    ]
    assert len({v.newest_as_of for v in views}) == 3


def test_follow_up_cites_from_the_same_evidence():
    _, resp = run("Which of those are Phase 3?")
    assert resp.citations == ["heart-failure-emerging_treatments-0"]


def test_out_of_scope_refuses_after_planner_only():
    names, resp = run("What's the weather tomorrow?")
    assert names == ["status", "done"] and resp.action == "refuse"


def test_patient_name_is_redacted():
    _, resp = run("Briefing for patient Smith with heart failure")
    assert resp.action == "redact"
