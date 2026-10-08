"""Builds the pipeline's dependencies for the app.

STUB until pane B merges: `rag.search` and `rag.conditions` don't exist on this branch, so search
and condition lookup read the corpus files directly (no embeddings, paragraph order as rank).
Merge step: replace `stub_search` / `stub_list_conditions` below with
`from rag.search import search` and `from rag.conditions import list_conditions`.
"""

import logging
import re
from datetime import date
from functools import cache
from pathlib import Path
from typing import Any

from agents.llm import ClaudeLLM
from agents.pipeline import PipelineDeps
from config import Settings
from memory.store import InMemoryStore, PgMemoryStore
from schemas import Condition, RetrievedChunk, Section

log = logging.getLogger("api")

CORPUS = Path(__file__).resolve().parents[2] / "corpus" / "condition-briefing"


@cache
def _corpus() -> tuple[list[Condition], list[RetrievedChunk]]:
    log.warning("rag stubs in use: search reads %s without embeddings", CORPUS)
    conditions: dict[str, Condition] = {}
    chunks: list[RetrievedChunk] = []
    for path in sorted(CORPUS.glob("*/*.md")):
        _, front, body = path.read_text().split("---", 2)
        meta = dict(line.split(":", 1) for line in front.strip().splitlines() if ":" in line)
        meta = {k.strip(): v.strip().strip('"') for k, v in meta.items()}
        slug, section = path.parent.name, meta["section"]
        aliases = [a.strip() for a in meta.get("aliases", "").strip("[]").split(",") if a.strip()]
        conditions[slug] = Condition(id=slug, name=meta["condition"], aliases=aliases)
        paragraphs = [p.strip() for p in re.split(r"\n\s*\n", body) if p.strip()]
        for ord_, text in enumerate(paragraphs):
            chunks.append(
                RetrievedChunk(
                    chunk_id=f"{slug}-{section}-{ord_}",
                    doc=f"{slug}/{section}.md",
                    text=text,
                    score=None,
                    section=section,
                    source_label=meta.get("source_label"),
                    as_of=date.fromisoformat(meta["as_of"]) if meta.get("as_of") else None,
                )
            )
    return list(conditions.values()), chunks


async def stub_list_conditions(pool: Any) -> list[Condition]:
    return _corpus()[0]


async def stub_search(
    pool: Any, query: str, condition_id: str, section: Section, k: int = 5
) -> list[RetrievedChunk]:
    hits = [c for c in _corpus()[1] if c.doc == f"{condition_id}/{section}.md"]
    return hits[:k]


def build_deps(settings: Settings, pool: Any) -> PipelineDeps:
    """Real LLM and Postgres memory; stub retrieval until pane B's rag/ merges."""
    memory = PgMemoryStore(pool) if pool is not None else InMemoryStore()
    return PipelineDeps(
        llm=ClaudeLLM(settings),
        settings=settings,
        search=stub_search,
        list_conditions=stub_list_conditions,
        memory=memory,
        pool=pool,
    )
