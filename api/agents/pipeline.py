"""Wires the four stages and yields events; /chat streams them as SSE, /ask returns the last one.

Order: redact → planner → scope check → retriever → answerer → critic (→ one retry → refuse).
`token` events are yielded only after the critic passes, so no unchecked text reaches the user.
"""

from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass
from typing import Any, Literal

from agents.answerer import draft_briefing, draft_follow_up
from agents.critic import review
from agents.errors import PipelineError
from agents.llm import LLM
from agents.planner import plan
from agents.render import citations_of, to_markdown, token_chunks
from agents.retriever import SearchFn, retrieve
from config import Settings
from guardrails.pii import redact
from guardrails.scope import check_scope, match_condition
from memory.store import Briefing, MemoryStore
from schemas import (
    AskRequest,
    AskResponse,
    BriefingDraft,
    Condition,
    FollowUpDraft,
    RefuseReason,
    RetrievedChunk,
)

EventName = Literal["status", "token", "done"]
Event = tuple[EventName, dict[str, Any]]
ListConditionsFn = Callable[[Any], Awaitable[list[Condition]]]

MAX_DRAFTS = 2  # first draft + one retry

REFUSALS: dict[RefuseReason, str] = {
    "unrelated": "I can only brief on the medical conditions in this tool's library.",
    "clinical_advice": (
        "I can't give clinical or patient-specific advice. I can brief on the standard of care, "
        "emerging treatments, and key companies for a condition."
    ),
    "unknown_condition": (
        "That condition isn't in the briefing library yet. Try one of the listed conditions."
    ),
    "no_evidence": "I found no sources for that condition, so I can't brief on it.",
    "unchecked": (
        "I couldn't produce a briefing that passed the source checks, so I'm not showing one."
    ),
}


@dataclass
class PipelineDeps:
    llm: LLM
    settings: Settings
    search: SearchFn
    list_conditions: ListConditionsFn
    memory: MemoryStore
    pool: Any = None


def _status(agent: str) -> Event:
    return ("status", {"agent": agent})


async def run(req: AskRequest, deps: PipelineDeps) -> AsyncIterator[Event]:
    """Run one request. Ends with exactly one `done` event carrying the AskResponse."""
    question, pii_found = redact(req.question)
    memory = deps.memory
    session_id = await memory.ensure_session(req.session_id, req.user_id)
    await memory.add_turn(session_id, "user", question, [])

    async def refuse(reason: RefuseReason, retrieved: list[RetrievedChunk]) -> AsyncIterator[Event]:
        text = REFUSALS[reason]
        await memory.add_turn(session_id, "assistant", text, [])
        response = AskResponse(
            answer=text, action="refuse", retrieved=retrieved, session_id=session_id
        )
        yield ("token", {"text": text})
        yield ("done", response.model_dump(mode="json"))

    yield _status("planner")
    conditions = await deps.list_conditions(deps.pool)
    by_id = {c.id: c for c in conditions}
    briefing = await memory.last_briefing(session_id)
    briefing_name = (
        by_id[briefing.condition_id].name if briefing and briefing.condition_id in by_id else None
    )
    planned = await plan(
        deps.llm,
        deps.settings,
        question,
        conditions,
        briefing_name,
        match_condition(question, conditions),
    )
    reason = check_scope(planned, conditions, has_briefing=briefing is not None)
    if reason:
        async for event in refuse(reason, []):
            yield event
        return

    follow_up = planned.intent == "follow_up" and briefing is not None
    if follow_up:
        assert briefing is not None
        condition_id, chunks = briefing.condition_id, briefing.chunks
    else:
        condition_id = planned.condition_id or ""
        yield _status("retriever")
        chunks = await retrieve(
            deps.search, deps.pool, question, condition_id, deps.settings.retrieval_k
        )
        if not chunks:
            async for event in refuse("no_evidence", []):
                yield event
            return

    problems: list[str] | None = None
    draft: BriefingDraft | FollowUpDraft | None = None
    for _ in range(MAX_DRAFTS):
        yield _status("answerer")
        if follow_up:
            draft = await draft_follow_up(deps.llm, deps.settings, question, chunks, problems)
        else:
            draft = await draft_briefing(
                deps.llm, deps.settings, by_id[condition_id], chunks, problems
            )
        yield _status("critic")
        problems = await review(deps.llm, deps.settings, draft, chunks)
        if not problems:
            break
    if problems or draft is None:
        async for event in refuse("unchecked", chunks):
            yield event
        return

    answer = to_markdown(draft)
    citations = citations_of(draft)
    if not follow_up:
        await memory.save_briefing(session_id, Briefing(condition_id, chunks))
        await memory.touch_recent(req.user_id, condition_id)
    await memory.add_turn(session_id, "assistant", answer, citations)
    for piece in token_chunks(answer):
        yield ("token", {"text": piece})
    response = AskResponse(
        answer=answer,
        citations=citations,
        action="redact" if pii_found else "answer",
        retrieved=chunks,
        session_id=session_id,
    )
    yield ("done", response.model_dump(mode="json"))


async def ask(req: AskRequest, deps: PipelineDeps) -> AskResponse:
    """Drain the pipeline and return the authoritative `done` payload."""
    async for name, data in run(req, deps):
        if name == "done":
            return AskResponse.model_validate(data)
    raise PipelineError("pipeline ended without a done event")
