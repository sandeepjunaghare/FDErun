"""Ingest + search round trip against real Supabase and Voyage: uv run pytest -m integration."""

from pathlib import Path

import psycopg
import pytest

from config import get_settings
from db import create_pool
from rag import list_conditions
from rag.ingest import ingest
from rag.search import search

pytestmark = [
    pytest.mark.integration,
    pytest.mark.anyio,
    pytest.mark.skipif(
        not get_settings().voyage_api_key,
        reason="VOYAGE_API_KEY not set (ingest embeds via Voyage)",
    ),
]

CORPUS = Path(__file__).resolve().parents[2] / "corpus" / "condition-briefing"


async def count_chunks(conn: psycopg.AsyncConnection) -> int:
    cur = await conn.execute("select count(*) from chunks")
    row = await cur.fetchone()
    assert row is not None
    return row[0]


async def test_ingest_is_idempotent_and_search_filters():
    settings = get_settings()
    async with await psycopg.AsyncConnection.connect(settings.database_url) as conn:
        first = await ingest(CORPUS, conn)
        after_first = await count_chunks(conn)
        second = await ingest(CORPUS, conn)
        assert second == first
        assert await count_chunks(conn) == after_first

    pool = create_pool(settings)
    await pool.open()
    try:
        results = await search(pool, "CHF quadruple therapy", "heart-failure", "standard_of_care")
        assert results
        assert all(r.doc == "heart-failure/standard_of_care.md" for r in results)
        assert all(r.section == "standard_of_care" and r.source_label and r.as_of for r in results)
        assert results == sorted(results, key=lambda r: r.score or 0, reverse=True)

        assert await search(pool, "anything", "no-such-condition", "standard_of_care") == []

        conditions = await list_conditions(pool)
        assert len(conditions) == 10
        hf = next(c for c in conditions if c.id == "heart-failure")
        assert "CHF" in hf.aliases
    finally:
        await pool.close()
