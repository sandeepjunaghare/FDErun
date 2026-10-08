"""App wiring for the pipeline: Claude, pane B's search + conditions, Postgres memory."""

from typing import Any

from agents.errors import PipelineError
from agents.llm import ClaudeLLM
from agents.pipeline import PipelineDeps
from config import Settings
from memory.store import InMemoryStore, PgMemoryStore
from rag import list_conditions
from rag.embed import EmbeddingError
from rag.search import search
from schemas import RetrievedChunk, Section


class RetrievalError(PipelineError):
    """The query couldn't be embedded (Voyage down, key missing); /ask answers 503."""


async def search_or_fail(
    pool: Any, query: str, condition_id: str, section: Section, k: int = 5
) -> list[RetrievedChunk]:
    """rag.search with EmbeddingError mapped onto the pipeline's error class."""
    try:
        return await search(pool, query, condition_id, section, k)
    except EmbeddingError as e:
        raise RetrievalError(str(e)) from e


def build_deps(settings: Settings, pool: Any) -> PipelineDeps:
    memory = PgMemoryStore(pool) if pool is not None else InMemoryStore()
    return PipelineDeps(
        llm=ClaudeLLM(settings),
        settings=settings,
        search=search_or_fail,
        list_conditions=list_conditions,
        memory=memory,
        pool=pool,
    )
