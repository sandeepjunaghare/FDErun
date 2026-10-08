"""Semantic search over one condition and one section (interface note 2)."""

from psycopg_pool import AsyncConnectionPool

from rag.embed import embed, to_pgvector
from rag.models import RetrievedChunk, Section

SEARCH_SQL = """
select c.chunk_id, c.doc, c.text, 1 - (c.embedding <=> %(q)s::vector) as score,
       c.section, d.source_label, d.as_of
from chunks c join documents d using (doc)
where c.condition_id = %(condition_id)s and c.section = %(section)s
order by c.embedding <=> %(q)s::vector
limit %(k)s
"""


async def search(
    pool: AsyncConnectionPool, query: str, condition_id: str, section: Section, k: int = 5
) -> list[RetrievedChunk]:
    """Top-k chunks for query within condition_id + section, best first.

    Unknown condition → []. Raises EmbeddingError or psycopg.Error.
    """
    [vector] = await embed([query], "query")
    params = {"q": to_pgvector(vector), "condition_id": condition_id, "section": section, "k": k}
    async with pool.connection() as conn:
        cur = await conn.execute(SEARCH_SQL, params)
        rows = await cur.fetchall()
    return [
        RetrievedChunk(
            chunk_id=chunk_id,
            doc=doc,
            text=text,
            score=float(score),
            section=sec,
            source_label=source_label,
            as_of=as_of,
        )
        for chunk_id, doc, text, score, sec, source_label, as_of in rows
    ]
