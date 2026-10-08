"""Load the condition-briefing corpus into Supabase: validate, chunk, embed, upsert.

Run from api/, once, after migrate:  uv run python -m rag.ingest ../corpus/condition-briefing
Idempotent: stable chunk ids + upserts, and chunks past a document's new length are deleted.
A corpus that fails scripts/check_corpus.py is refused before anything is embedded or written.
"""

import asyncio
import sys
from dataclasses import dataclass
from pathlib import Path

import psycopg

from config import get_settings
from rag.corpus import CorpusError, load_corpus
from rag.embed import embed, to_pgvector
from rag.models import Document

UPSERT_CONDITION = """
insert into conditions (id, name, aliases) values (%s, %s, %s)
on conflict (id) do update set name = excluded.name, aliases = excluded.aliases
"""
UPSERT_DOCUMENT = """
insert into documents (doc, condition_id, section, title, source_label, source_type, as_of)
values (%s, %s, %s, %s, %s, %s, %s)
on conflict (doc) do update set condition_id = excluded.condition_id, section = excluded.section,
    title = excluded.title, source_label = excluded.source_label,
    source_type = excluded.source_type, as_of = excluded.as_of
"""
UPSERT_CHUNK = """
insert into chunks (chunk_id, doc, ord, condition_id, section, text, embedding)
values (%s, %s, %s, %s, %s, %s, %s::vector)
on conflict (chunk_id) do update set doc = excluded.doc, ord = excluded.ord,
    condition_id = excluded.condition_id, section = excluded.section, text = excluded.text,
    embedding = excluded.embedding
"""
DELETE_TAIL = "delete from chunks where doc = %s and ord >= %s"


@dataclass(frozen=True)
class IngestStats:
    conditions: int
    documents: int
    chunks: int


async def ingest(root: Path, conn: psycopg.AsyncConnection) -> IngestStats:
    """Validate and load root into the DB in one transaction. Raises CorpusError, EmbeddingError."""
    docs = load_corpus(root)
    chunks = [c for d in docs for c in d.chunks]
    # Embed before opening the transaction: no transaction held open across Voyage calls.
    vectors = await embed([c.text for c in chunks], "document")

    conditions = {d.condition_id: d for d in docs}
    async with conn.transaction(), conn.cursor() as cur:
        await cur.executemany(
            UPSERT_CONDITION,
            [(d.condition_id, d.condition_name, d.aliases) for d in conditions.values()],
        )
        await cur.executemany(UPSERT_DOCUMENT, [_document_row(d) for d in docs])
        await cur.executemany(
            UPSERT_CHUNK,
            [
                (c.chunk_id, c.doc, c.ord, c.condition_id, c.section, c.text, to_pgvector(v))
                for c, v in zip(chunks, vectors, strict=True)
            ],
        )
        await cur.executemany(DELETE_TAIL, [(d.doc, len(d.chunks)) for d in docs])
    return IngestStats(len(conditions), len(docs), len(chunks))


def _document_row(d: Document) -> tuple:
    return (d.doc, d.condition_id, d.section, d.title, d.source_label, d.source_type, d.as_of)


async def main(argv: list[str]) -> int:
    if len(argv) != 1:
        print("usage: python -m rag.ingest <corpus-dir>")
        return 2
    root = Path(argv[0])
    try:
        async with await psycopg.AsyncConnection.connect(get_settings().database_url) as conn:
            stats = await ingest(root, conn)
    except CorpusError as exc:
        for problem in exc.problems:
            print(f"FAIL {problem}")
        print("refused: corpus is invalid, nothing ingested")
        return 1
    s = stats
    print(f"ingested {s.conditions} conditions, {s.documents} documents, {s.chunks} chunks")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main(sys.argv[1:])))
