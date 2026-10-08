"""Streamlit front end: condition briefings over POST /chat, with sources, dates, and memory."""

import os
import uuid
from collections.abc import Iterator
from typing import Any

import httpx
import streamlit as st

from briefing import annotate, build_briefing, format_source, notice_for
from client import ChatEvent, UiApiError, chat_available, get_recent, stream_chat
from models import AskResponse, ChatRequest
from stub import stub_chat_events

API_URL = os.environ.get("API_URL", "http://localhost:8710").rstrip("/")
FORCE_STUB = os.environ.get("UI_STUB", "") == "1"

STAGES = {
    "planner": "Planning: checking scope and resolving the condition…",
    "retriever": "Retrieving sources for each section…",
    "answerer": "Drafting the cited briefing…",
    "critic": "Checking every citation before showing it…",
}

st.set_page_config(page_title="Condition briefing", page_icon="🩺", layout="wide")


def get(path: str) -> tuple[bool, str]:
    """GET an API path; returns (ok, body or error class) without raising."""
    try:
        r = httpx.get(f"{API_URL}{path}", timeout=10)
        return r.is_success, r.text
    except httpx.HTTPError as e:
        return False, type(e).__name__


@st.cache_data(ttl=30, show_spinner=False)
def status_checks() -> dict[str, tuple[bool, str]]:
    return {path: get(path) for path in ("/health", "/version", "/health/db")}


@st.cache_data(ttl=30, show_spinner=False)
def use_stub() -> bool:
    return FORCE_STUB or not chat_available(API_URL)


def state() -> Any:
    """Session state, initialized once per browser session."""
    s = st.session_state
    s.setdefault("user_id", "strategist")
    s.setdefault("session_id", uuid.uuid4().hex)
    s.setdefault("turns", [])
    s.setdefault("pending", None)
    return s


def new_session() -> None:
    st.session_state.session_id = uuid.uuid4().hex
    st.session_state.turns = []


def events_for(question: str, user_id: str, session_id: str) -> Iterator[ChatEvent]:
    if use_stub():
        return stub_chat_events(question)
    req = ChatRequest(question=question, user_id=user_id, session_id=session_id)
    return stream_chat(API_URL, req)


def render_response(resp: AskResponse) -> None:
    notice = notice_for(resp)
    if notice:
        kind, text = notice
        (st.warning if kind == "warning" else st.info)(text)
        return
    for view in build_briefing(resp):
        newest = view.newest_as_of
        st.markdown(f"### {view.title}")
        if newest:
            st.caption(f"Newest source in this section: as of {newest.isoformat()}")
        if view.body:
            st.markdown(annotate(view))
        if view.sources:
            st.markdown("\n".join(f"- {format_source(s)}" for s in view.sources))
    if not resp.citations:
        st.caption("No sources were cited.")


def run_turn(question: str) -> None:
    """Stream one question through /chat and store the authoritative `done` response as a turn."""
    s = state()
    s.turns.append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.markdown(question)
    with st.chat_message("assistant"):
        status = st.status("Starting…", expanded=False)
        draft = st.empty()
        text = ""
        resp: AskResponse | None = None
        try:
            for event, data in events_for(question, s.user_id, s.session_id):
                if event == "status":
                    status.update(label=STAGES.get(data.get("agent", ""), "Working…"))
                elif event == "token":
                    text += str(data.get("text", ""))
                    draft.markdown(text)
                elif event == "done":
                    resp = AskResponse.model_validate(data)
        except UiApiError as e:
            status.update(label="Failed", state="error")
            draft.empty()
            st.error(f"The briefing service failed ({e}). Try again.")
            s.turns.append({"role": "assistant", "error": str(e)})
            return
        draft.empty()
        if resp is None:
            status.update(label="Failed", state="error")
            st.error("The briefing stream ended before it finished. Try again.")
            s.turns.append({"role": "assistant", "error": "IncompleteStream"})
            return
        status.update(label="Checked and ready", state="complete")
        render_response(resp)
        s.turns.append({"role": "assistant", "response": resp})


def render_history() -> None:
    for turn in state().turns:
        with st.chat_message(turn["role"]):
            if turn["role"] == "user":
                st.markdown(turn["content"])
            elif "response" in turn:
                render_response(turn["response"])
            else:
                st.error(f"The briefing service failed ({turn['error']}).")


def sidebar() -> None:
    s = state()
    with st.sidebar:
        s.user_id = st.text_input("User", value=s.user_id) or "strategist"
        if st.button("New briefing session", use_container_width=True):
            new_session()
            st.rerun()

        st.subheader("Recent conditions")
        recent = get_recent(API_URL, s.user_id)
        if not recent:
            st.caption("None yet (or the API has no /recent).")
        for i, cond in enumerate(recent):
            if st.button(cond.label, key=f"recent-{i}", use_container_width=True):
                s.pending = f"Briefing on {cond.label}"

        st.subheader("This session")
        questions = [t["content"] for t in s.turns if t["role"] == "user"]
        outcomes = [t for t in s.turns if t["role"] == "assistant"]
        if not questions:
            st.caption("No questions yet.")
        for i, q in enumerate(questions):
            outcome = outcomes[i] if i < len(outcomes) else None
            action = outcome["response"].action if outcome and "response" in outcome else "error"
            st.markdown(f"{i + 1}. {q} — _{action}_")
        st.caption(f"Session `{s.session_id[:8]}`")

        st.divider()
        st.caption("API")
        st.code(API_URL, language=None)
        for path, (ok, body) in status_checks().items():
            st.write(f"{'✅' if ok else '❌'} `{path}` {body}")


st.title("Condition briefing")
st.badge("Synthetic sample data", icon="🧪", color="orange")
st.caption(
    "Standard of care, emerging treatments, and key companies for a condition. "
    "Every source shows its label and as-of date."
)

sidebar()
if use_stub():
    st.warning("Demo mode: answers come from a built-in stub, not the API's /chat.")
elif not all(ok for ok, _ in status_checks().values()):
    st.error(f"Can't reach the API at {API_URL}. Start it, or set API_URL.")

render_history()
question = st.chat_input("A condition (e.g. heart failure) or a follow-up question")
pending = state().pending
if pending:
    state().pending = None
    question = pending
if question:
    run_turn(question)
    st.rerun()
