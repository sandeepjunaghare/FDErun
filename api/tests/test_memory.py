import asyncio
import uuid

import pytest

from config import get_settings
from db import create_pool
from memory.store import Briefing, PgMemoryStore
from tests.fakes import CHUNKS


@pytest.mark.integration
def test_pg_memory_roundtrip():
    """Needs pane B's 0003_memory.sql applied (sessions, turns, recent_conditions)."""

    async def go():
        pool = create_pool(get_settings())
        await pool.open()
        store = PgMemoryStore(pool)
        user = f"test-{uuid.uuid4()}"
        try:
            sid = await store.ensure_session(None, user)
            assert await store.ensure_session(sid, user) == sid
            assert await store.ensure_session(sid, f"{user}-other") != sid
            chunks = CHUNKS["emerging_treatments"]
            await store.save_briefing(sid, Briefing("heart-failure", chunks))
            got = await store.last_briefing(sid)
            assert got is not None and got.chunks == chunks
            await store.touch_recent(user, "asthma")
            await store.touch_recent(user, "heart-failure")
            assert [c for c, _ in await store.recent(user)] == ["heart-failure", "asthma"]
        finally:
            async with pool.connection() as conn:
                await conn.execute(
                    "delete from turns where session_id in"
                    " (select session_id from sessions where user_id like %s)",
                    (f"{user}%",),
                )
                await conn.execute("delete from sessions where user_id like %s", (f"{user}%",))
                await conn.execute("delete from recent_conditions where user_id = %s", (user,))
            await pool.close()

    asyncio.run(go())
