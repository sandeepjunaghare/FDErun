import json

import httpx
import pytest

from client import UiApiError, chat_available, get_recent, parse_sse, stream_chat
from models import AskResponse, ChatRequest

SSE_BODY = (
    'event: status\ndata: {"agent": "planner"}\n\n'
    ": keep-alive\n\n"
    'event: status\ndata: {"agent": "critic"}\n\n'
    'event: token\ndata: {"text": "## Current"}\n\n'
    'event: done\ndata: {"answer": "x", "citations": ["c1"], "action": "answer",\n'
    'data: "retrieved": [{"chunk_id": "c1", "doc": "d.md", "text": "t",\n'
    'data: "as_of": "2026-09-12"}]}\n\n'
)


def client_for(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_parse_sse_events_comments_and_multiline_data():
    events = list(parse_sse(SSE_BODY.splitlines()))
    assert [e for e, _ in events] == ["status", "status", "token", "done"]
    done = AskResponse.model_validate(events[-1][1])
    as_of = done.retrieved[0].as_of
    assert as_of is not None and as_of.isoformat() == "2026-09-12"


def test_parse_sse_drops_unterminated_event():
    assert list(parse_sse(["event: done", 'data: {"answer": "x"}'])) == []


def test_parse_sse_bad_json_raises_class_name():
    with pytest.raises(UiApiError, match="JSONDecodeError"):
        list(parse_sse(["data: {not json", ""]))


def test_stream_chat_posts_request_without_null_session():
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["path"] = request.url.path
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, text=SSE_BODY, headers={"content-type": "text/event-stream"})

    req = ChatRequest(question="heart failure", user_id="u1")
    events = list(stream_chat("http://api", req, client=client_for(handler)))
    assert seen == {"path": "/chat", "body": {"question": "heart failure", "user_id": "u1"}}
    assert events[0] == ("status", {"agent": "planner"})


def test_stream_chat_sends_session_id_when_set():
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, text="")

    req = ChatRequest(question="q", user_id="u1", session_id="s1")
    list(stream_chat("http://api", req, client=client_for(handler)))
    assert seen["body"]["session_id"] == "s1"


def test_stream_chat_http_error_names_class_only():
    req = ChatRequest(question="q", user_id="u1")
    client = client_for(lambda r: httpx.Response(503, json={"detail": "LLMError"}))
    with pytest.raises(UiApiError, match="^HTTPStatusError$"):
        list(stream_chat("http://api", req, client=client))


def test_chat_available_reads_openapi_paths():
    with_chat = client_for(lambda r: httpx.Response(200, json={"paths": {"/chat": {}}}))
    without = client_for(lambda r: httpx.Response(200, json={"paths": {"/health": {}}}))
    down = client_for(lambda r: (_ for _ in ()).throw(httpx.ConnectError("no")))
    assert chat_available("http://api", client=with_chat) is True
    assert chat_available("http://api", client=without) is False
    assert chat_available("http://api", client=down) is False


@pytest.mark.parametrize(
    "body",
    [
        [{"condition_id": "heart-failure", "name": "Heart failure"}],
        {"conditions": [{"condition_id": "heart-failure", "name": "Heart failure"}]},
    ],
)
def test_get_recent_accepts_list_or_wrapped(body):
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["query"] = dict(request.url.params)
        return httpx.Response(200, json=body)

    rows = get_recent("http://api", "u1", client=client_for(handler))
    assert seen["query"] == {"user_id": "u1"}
    assert [r.label for r in rows] == ["Heart failure"]


def test_get_recent_missing_route_is_empty():
    assert get_recent("http://api", "u1", client=client_for(lambda r: httpx.Response(404))) == []


def test_recent_label_falls_back_to_id():
    rows = get_recent(
        "http://api",
        "u1",
        client=client_for(lambda r: httpx.Response(200, json=[{"condition_id": "heart-failure"}])),
    )
    assert rows[0].label == "heart failure"
