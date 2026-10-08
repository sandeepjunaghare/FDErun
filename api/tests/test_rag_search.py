from datetime import date

import pytest

import rag.search as search_module
from rag.embed import EmbeddingError, embed, to_pgvector

pytestmark = pytest.mark.anyio


class FakeCursor:
    def __init__(self, rows):
        self.rows = rows

    async def fetchall(self):
        return self.rows


class FakeConn:
    def __init__(self, rows):
        self.rows = rows
        self.calls: list[tuple[str, dict | None]] = []

    async def execute(self, sql, params=None):
        self.calls.append((sql, params))
        return FakeCursor(self.rows)


class FakePool:
    def __init__(self, rows):
        self.conn = FakeConn(rows)

    def connection(self):
        conn = self.conn

        class Ctx:
            async def __aenter__(self):
                return conn

            async def __aexit__(self, *exc):
                return False

        return Ctx()


ROW = (
    "heart-failure-standard_of_care-0",
    "heart-failure/standard_of_care.md",
    "HFrEF is treated with four medication classes.",
    0.81,
    "standard_of_care",
    "Synthetic guideline summary — FDErun corpus v1",
    date(2026, 5, 20),
)


async def test_search_filters_by_condition_and_section_and_maps_labels(monkeypatch):
    seen = {}

    async def fake_embed(texts, input_type):
        seen["texts"], seen["input_type"] = texts, input_type
        return [[0.1, 0.2]]

    monkeypatch.setattr(search_module, "embed", fake_embed)
    pool = FakePool([ROW])
    results = await search_module.search(
        pool,  # pyright: ignore[reportArgumentType]
        "CHF quadruple therapy",
        "heart-failure",
        "standard_of_care",
        k=3,
    )

    assert seen == {"texts": ["CHF quadruple therapy"], "input_type": "query"}
    [(sql, params)] = pool.conn.calls
    assert "c.condition_id = %(condition_id)s and c.section = %(section)s" in sql
    assert params == {
        "q": "[0.1,0.2]",
        "condition_id": "heart-failure",
        "section": "standard_of_care",
        "k": 3,
    }
    [chunk] = results
    assert chunk.chunk_id == ROW[0]
    assert chunk.score == pytest.approx(0.81)
    assert chunk.section == "standard_of_care"
    assert chunk.source_label == ROW[5]
    assert chunk.as_of == date(2026, 5, 20)


async def test_list_conditions_maps_rows():
    from rag.conditions import list_conditions

    pool = FakePool([("heart-failure", "Heart failure", ["HF", "CHF"])])
    [c] = await list_conditions(pool)  # pyright: ignore[reportArgumentType]
    assert (c.id, c.name, c.aliases) == ("heart-failure", "Heart failure", ["HF", "CHF"])


async def test_embed_without_key_raises(monkeypatch):
    from config import Settings

    settings = Settings(database_url="postgresql://u:p@h/db", voyage_api_key="")
    monkeypatch.setattr("rag.embed.get_settings", lambda: settings)
    with pytest.raises(EmbeddingError, match="VOYAGE_API_KEY"):
        await embed(["x"], "query")


def test_to_pgvector():
    assert to_pgvector([1.0, -0.5]) == "[1.0,-0.5]"
