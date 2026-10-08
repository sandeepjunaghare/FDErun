"""Memory stores over pane B's tables: sessions, turns, recent_conditions (0003_memory.sql).

Callers pass redacted text only. A briefing's evidence is kept as a turn with role "retrieved"
(JSON content) so follow-ups answer from the same chunks without searching again.
"""

import json
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Protocol

from psycopg_pool import AsyncConnectionPool

from schemas import RetrievedChunk

RETRIEVED = "retrieved"


@dataclass
class Briefing:
    condition_id: str
    chunks: list[RetrievedChunk]


class MemoryStore(Protocol):
    async def ensure_session(self, session_id: str | None, user_id: str) -> str: ...
    async def add_turn(
        self, session_id: str, role: str, content: str, citations: list[str]
    ) -> None: ...
    async def save_briefing(self, session_id: str, briefing: Briefing) -> None: ...
    async def last_briefing(self, session_id: str) -> Briefing | None: ...
    async def touch_recent(self, user_id: str, condition_id: str) -> None: ...
    async def recent(self, user_id: str, limit: int = 10) -> list[tuple[str, datetime]]: ...


def _encode(briefing: Briefing) -> str:
    return json.dumps(
        {
            "condition_id": briefing.condition_id,
            "chunks": [c.model_dump(mode="json") for c in briefing.chunks],
        }
    )


def _decode(content: str) -> Briefing:
    data = json.loads(content)
    return Briefing(
        data["condition_id"], [RetrievedChunk.model_validate(c) for c in data["chunks"]]
    )


class PgMemoryStore:
    def __init__(self, pool: AsyncConnectionPool):
        self._pool = pool

    async def ensure_session(self, session_id: str | None, user_id: str) -> str:
        """Reuse the session if this user owns it; otherwise start a new one."""
        async with self._pool.connection() as conn:
            if session_id:
                cur = await conn.execute(
                    "select user_id from sessions where session_id = %s", (session_id,)
                )
                row = await cur.fetchone()
                if row and row[0] == user_id:
                    return session_id
            new_id = str(uuid.uuid4())
            await conn.execute(
                "insert into sessions (session_id, user_id, created_at) values (%s, %s, now())",
                (new_id, user_id),
            )
        return new_id

    async def add_turn(
        self, session_id: str, role: str, content: str, citations: list[str]
    ) -> None:
        async with self._pool.connection() as conn:
            await conn.execute(
                "insert into turns (session_id, role, content, citations, created_at)"
                " values (%s, %s, %s, %s, now())",
                (session_id, role, content, citations),
            )

    async def save_briefing(self, session_id: str, briefing: Briefing) -> None:
        ids = [c.chunk_id for c in briefing.chunks]
        await self.add_turn(session_id, RETRIEVED, _encode(briefing), ids)

    async def last_briefing(self, session_id: str) -> Briefing | None:
        async with self._pool.connection() as conn:
            cur = await conn.execute(
                "select content from turns where session_id = %s and role = %s"
                " order by id desc limit 1",
                (session_id, RETRIEVED),
            )
            row = await cur.fetchone()
        return _decode(row[0]) if row else None

    async def touch_recent(self, user_id: str, condition_id: str) -> None:
        async with self._pool.connection() as conn:
            await conn.execute(
                "insert into recent_conditions (user_id, condition_id, viewed_at)"
                " values (%s, %s, now())"
                " on conflict (user_id, condition_id) do update set viewed_at = excluded.viewed_at",
                (user_id, condition_id),
            )

    async def recent(self, user_id: str, limit: int = 10) -> list[tuple[str, datetime]]:
        async with self._pool.connection() as conn:
            cur = await conn.execute(
                "select condition_id, viewed_at from recent_conditions where user_id = %s"
                " order by viewed_at desc limit %s",
                (user_id, limit),
            )
            rows = await cur.fetchall()
        return [(r[0], r[1]) for r in rows]


@dataclass
class InMemoryStore:
    """Same behaviour as PgMemoryStore, in process. Unit tests and the no-DB fallback."""

    sessions: dict[str, str] = field(default_factory=dict)
    turns: list[tuple[str, str, str, list[str]]] = field(default_factory=list)
    recents: dict[tuple[str, str], datetime] = field(default_factory=dict)

    async def ensure_session(self, session_id: str | None, user_id: str) -> str:
        if session_id and self.sessions.get(session_id) == user_id:
            return session_id
        new_id = str(uuid.uuid4())
        self.sessions[new_id] = user_id
        return new_id

    async def add_turn(
        self, session_id: str, role: str, content: str, citations: list[str]
    ) -> None:
        self.turns.append((session_id, role, content, citations))

    async def save_briefing(self, session_id: str, briefing: Briefing) -> None:
        ids = [c.chunk_id for c in briefing.chunks]
        await self.add_turn(session_id, RETRIEVED, _encode(briefing), ids)

    async def last_briefing(self, session_id: str) -> Briefing | None:
        for sid, role, content, _ in reversed(self.turns):
            if sid == session_id and role == RETRIEVED:
                return _decode(content)
        return None

    async def touch_recent(self, user_id: str, condition_id: str) -> None:
        self.recents[(user_id, condition_id)] = datetime.now(UTC)

    async def recent(self, user_id: str, limit: int = 10) -> list[tuple[str, datetime]]:
        mine = [(cid, t) for (uid, cid), t in self.recents.items() if uid == user_id]
        return sorted(mine, key=lambda r: r[1], reverse=True)[:limit]
