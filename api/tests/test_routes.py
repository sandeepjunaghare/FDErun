import json

import psycopg
import pytest
from fastapi.testclient import TestClient

import main
from agents.errors import LLMError
from schemas import BriefingDraft
from tests.fakes import BRIEFING, PASS, FakeLLM, good_draft, make_deps


@pytest.fixture
def client_with():
    """Client without the lifespan: no pool, no network; each test supplies the deps."""

    def build(llm: FakeLLM):
        main.app.state.pool = object()
        main.app.state.deps = make_deps(llm)
        return TestClient(main.app)

    return build


def parse_sse(body: str) -> list[tuple[str, dict]]:
    out = []
    for frame in body.strip().split("\n\n"):
        lines = dict(line.split(": ", 1) for line in frame.splitlines())
        out.append((lines["event"], json.loads(lines["data"])))
    return out


def test_ask_returns_ask_response(client_with):
    r = client_with(FakeLLM(BRIEFING, good_draft(), PASS)).post(
        "/ask", json={"question": "CHF", "user_id": "eval"}
    )
    assert r.status_code == 200
    body = r.json()
    assert set(body) == {"answer", "citations", "action", "retrieved", "session_id"}
    assert body["action"] == "answer"


def test_ask_rejects_empty_question(client_with):
    r = client_with(FakeLLM()).post("/ask", json={"question": "", "user_id": "u"})
    assert r.status_code == 422


@pytest.mark.parametrize(
    "err", [LLMError("APIStatusError 529"), psycopg.OperationalError("host db.x.supabase.co")]
)
def test_ask_503_names_the_class_only(client_with, err):
    r = client_with(FakeLLM(BRIEFING, (BriefingDraft, err))).post(
        "/ask", json={"question": "CHF", "user_id": "u"}
    )
    assert r.status_code == 503
    assert r.json() == {"detail": type(err).__name__}
    assert "supabase" not in r.text and "529" not in r.text


def test_chat_streams_status_tokens_then_done(client_with):
    r = client_with(FakeLLM(BRIEFING, good_draft(), PASS)).post(
        "/chat", json={"question": "CHF", "user_id": "u"}
    )
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/event-stream")
    evs = parse_sse(r.text)
    names = [n for n, _ in evs]
    assert names[:4] == ["status", "status", "status", "status"]
    assert set(names[4:-1]) == {"token"}
    assert names[-1] == "done"
    assert "".join(d["text"] for n, d in evs if n == "token") == evs[-1][1]["answer"]


def test_chat_error_event(client_with):
    r = client_with(FakeLLM(BRIEFING, (BriefingDraft, LLMError("x")))).post(
        "/chat", json={"question": "CHF", "user_id": "u"}
    )
    evs = parse_sse(r.text)
    assert evs[-1] == ("error", {"detail": "LLMError"})
    assert "token" not in [n for n, _ in evs]


def test_recent_lists_conditions_newest_first(client_with):
    client = client_with(FakeLLM(BRIEFING, good_draft(), PASS))
    client.post("/ask", json={"question": "CHF", "user_id": "u9"})
    r = client.get("/recent", params={"user_id": "u9"})
    assert r.status_code == 200
    body = r.json()
    assert body["user_id"] == "u9"
    assert [(c["condition_id"], c["name"]) for c in body["conditions"]] == [
        ("heart-failure", "Heart failure")
    ]
    assert client.get("/recent", params={"user_id": "nobody"}).json()["conditions"] == []


def test_recent_requires_user_id(client_with):
    assert client_with(FakeLLM()).get("/recent").status_code == 422
