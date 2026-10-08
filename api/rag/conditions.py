"""The conditions the corpus covers, for the planner's name/alias resolution (interface note 3)."""

from psycopg_pool import AsyncConnectionPool

from rag.models import Condition


async def list_conditions(pool: AsyncConnectionPool) -> list[Condition]:
    """All conditions with their aliases, ordered by name. Raises psycopg.Error."""
    async with pool.connection() as conn:
        cur = await conn.execute("select id, name, aliases from conditions order by name")
        rows = await cur.fetchall()
    return [Condition(id=id_, name=name, aliases=list(aliases)) for id_, name, aliases in rows]
