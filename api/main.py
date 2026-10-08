"""FastAPI entrypoint: app lifespan (DB pool), health routes, and the briefing pipeline routes."""

import json
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import psycopg
from fastapi import FastAPI, Query, Request
from fastapi.responses import JSONResponse, StreamingResponse

from agents.deps import build_deps
from agents.errors import PipelineError
from agents.pipeline import PipelineDeps, ask, run
from config import get_settings
from db import SmokeCheckError, check_db, create_pool, smoke_roundtrip
from schemas import AskRequest, AskResponse, RecentCondition, RecentResponse

log = logging.getLogger("api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    pool = create_pool(get_settings())
    # wait=False: start even if Supabase is down, so /health/db can report 503
    # instead of the container crash-looping.
    await pool.open(wait=False)
    app.state.pool = pool
    app.state.deps = build_deps(get_settings(), pool)
    yield
    await pool.close()


app = FastAPI(title="FDErun API", lifespan=lifespan)


@app.get("/health")
async def health() -> dict:
    """Liveness: the process is serving. Render's health check path — never touches the DB."""
    return {"status": "ok"}


@app.get("/version")
async def version() -> dict:
    """The git commit this instance was deployed from ("local" outside Render)."""
    return {"commit": get_settings().render_git_commit}


@app.get("/health/db")
async def health_db(request: Request) -> JSONResponse:
    """Readiness of the data layer: Supabase reachable and pgvector installed."""
    try:
        version = await check_db(request.app.state.pool)
    except psycopg.Error as e:
        # Full error goes to logs; the public response names only the class (no hostnames).
        log.warning("health/db failed: %r", e)
        return JSONResponse({"db": "error", "detail": type(e).__name__}, status_code=503)
    if version is None:
        return JSONResponse({"db": "ok", "pgvector": "missing"}, status_code=503)
    return JSONResponse({"db": "ok", "pgvector": version})


@app.post("/smoke")
async def smoke(request: Request) -> JSONResponse:
    """Deploy smoke test: write, read and vector-search a row on a real table, then roll back."""
    try:
        distance = await smoke_roundtrip(request.app.state.pool)
    except (psycopg.Error, SmokeCheckError) as e:
        log.warning("smoke failed: %r", e)
        # UndefinedTable here means migrations haven't run: uv run python -m db.migrate
        return JSONResponse({"smoke": "error", "detail": type(e).__name__}, status_code=503)
    return JSONResponse(
        {"smoke": "ok", "write": "ok", "read": "ok", "vector_search": "ok", "distance": distance}
    )


# Errors the pipeline can hit: the LLM (PipelineError) or Supabase (memory, search).
PIPELINE_ERRORS = (PipelineError, psycopg.Error)


def _error_response(route: str, e: Exception) -> JSONResponse:
    log.warning("%s failed: %r", route, e)
    return JSONResponse({"detail": type(e).__name__}, status_code=503)


@app.post("/ask", response_model=AskResponse)
async def ask_route(body: AskRequest, request: Request):
    """Run the pipeline and return the briefing (or refusal) as JSON. Used by the evals."""
    deps: PipelineDeps = request.app.state.deps
    try:
        return await ask(body, deps)
    except PIPELINE_ERRORS as e:
        return _error_response("ask", e)


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


@app.post("/chat")
async def chat_route(body: AskRequest, request: Request) -> StreamingResponse:
    """Same pipeline as /ask, streamed: status → token (critic-approved only) → done."""
    deps: PipelineDeps = request.app.state.deps

    async def events() -> AsyncIterator[str]:
        try:
            async for name, data in run(body, deps):
                yield _sse(name, data)
        except PIPELINE_ERRORS as e:
            log.warning("chat failed: %r", e)
            yield _sse("error", {"detail": type(e).__name__})

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/recent", response_model=RecentResponse)
async def recent_route(request: Request, user_id: str = Query(min_length=1, max_length=200)):
    """The user's recently briefed conditions, newest first (persistent memory, for the UI)."""
    deps: PipelineDeps = request.app.state.deps
    try:
        rows = await deps.memory.recent(user_id)
        names = {c.id: c.name for c in await deps.list_conditions(deps.pool)}
    except PIPELINE_ERRORS as e:
        return _error_response("recent", e)
    return RecentResponse(
        user_id=user_id,
        conditions=[
            RecentCondition(condition_id=cid, name=names.get(cid, cid), viewed_at=at)
            for cid, at in rows
        ],
    )
