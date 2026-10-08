"""Retriever: a plain function, not an agent. One filtered search per section."""

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

from schemas import SECTIONS, RetrievedChunk, Section

# rag.search.search (pane B, interface note 2).
SearchFn = Callable[[Any, str, str, Section, int], Awaitable[list[RetrievedChunk]]]


async def retrieve(
    search: SearchFn, pool: Any, query: str, condition_id: str, k: int
) -> list[RetrievedChunk]:
    """Three searches in parallel, concatenated in section order, duplicate ids dropped."""
    results = await asyncio.gather(
        *(search(pool, query, condition_id, section, k) for section in SECTIONS)
    )
    seen: set[str] = set()
    chunks: list[RetrievedChunk] = []
    for section, found in zip(SECTIONS, results, strict=True):
        for chunk in found:
            if chunk.chunk_id in seen:
                continue
            seen.add(chunk.chunk_id)
            # The filter guarantees the section; fill it if the search left it empty.
            chunks.append(chunk if chunk.section else chunk.model_copy(update={"section": section}))
    return chunks
