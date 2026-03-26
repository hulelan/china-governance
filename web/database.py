"""Database connection management for the web app.

Supports two backends:
  - PostgreSQL (asyncpg) — used in production (Railway). Set DATABASE_URL env var.
  - SQLite (aiosqlite) — used for local development. Set SQLITE_PATH env var
    or leave unset to default to documents.db.
"""
import os
from contextlib import asynccontextmanager
from pathlib import Path

DATABASE_URL = os.environ.get("DATABASE_URL")
SQLITE_PATH = os.environ.get("SQLITE_PATH")

# Default to SQLite if no DATABASE_URL is set
if not DATABASE_URL and not SQLITE_PATH:
    SQLITE_PATH = str(Path(__file__).parent.parent / "documents.db")


class PostgresDB:
    """Thin wrapper around asyncpg pool to provide a consistent interface."""

    def __init__(self, pool):
        self.pool = pool

    async def fetch(self, query, *args):
        return await self.pool.fetch(query, *args)

    async def fetchrow(self, query, *args):
        return await self.pool.fetchrow(query, *args)

    async def fetchval(self, query, *args):
        return await self.pool.fetchval(query, *args)

    async def execute(self, query, *args):
        return await self.pool.execute(query, *args)

    async def close(self):
        await self.pool.close()


class SQLiteDB:
    """Wrapper around aiosqlite connection to match the Postgres interface."""

    def __init__(self, conn):
        self.conn = conn

    async def fetch(self, query, *args):
        """Execute query and return all rows. Converts $1/$2 placeholders to ?."""
        query, args = _pg_to_sqlite(query, args)
        return await self.conn.execute_fetchall(query, args)

    async def fetchrow(self, query, *args):
        query, args = _pg_to_sqlite(query, args)
        rows = await self.conn.execute_fetchall(query, args)
        return rows[0] if rows else None

    async def fetchval(self, query, *args):
        query, args = _pg_to_sqlite(query, args)
        rows = await self.conn.execute_fetchall(query, args)
        return rows[0][0] if rows else None

    async def execute(self, query, *args):
        query, args = _pg_to_sqlite(query, args)
        await self.conn.execute(query, args)
        await self.conn.commit()

    async def close(self):
        await self.conn.close()


def _pg_to_sqlite(query: str, args: tuple) -> tuple:
    """Convert Postgres-syntax SQL to SQLite-compatible SQL.

    Handles:
    - $1, $2 placeholders → ?
    - = ANY($n::int[]) → IN (?,?,?)
    - EXTRACT(YEAR FROM to_timestamp(col))::int → CAST(strftime('%Y', col, 'unixepoch') AS INTEGER)
    """
    import re

    # Convert regexp_replace(col, '[chars]', '', 'g') → nested replace() calls
    def _regexp_replace_to_sqlite(match):
        col = match.group(1)
        chars = match.group(2)
        result = col
        for ch in chars:
            result = f"replace({result}, '{ch}', '')"
        return result

    query = re.sub(
        r"regexp_replace\(([^,]+),\s*'\[([^\]]+)\]',\s*'',\s*'g'\)",
        _regexp_replace_to_sqlite,
        query
    )

    # Convert Postgres date functions to SQLite (always, regardless of placeholders)
    query = query.replace(
        "EXTRACT(YEAR FROM to_timestamp(date_written))::int",
        "CAST(strftime('%Y', date_written, 'unixepoch') AS INTEGER)"
    )

    # Replace $N placeholders with ? and reorder args
    placeholders = re.findall(r'\$(\d+)', query)
    if not placeholders:
        return query, args

    new_args = []
    def replace_placeholder(match):
        idx = int(match.group(1)) - 1  # $1 → index 0
        val = args[idx]
        # Handle array parameters: = ANY($n::int[]) → IN (?,?,?)
        if isinstance(val, (list, tuple)):
            new_args.extend(val)
            return 'IN (' + ','.join('?' * len(val)) + ')'
        new_args.append(val)
        return '?'

    # Handle = ANY($N::int[]) pattern first
    query = re.sub(r'=\s*ANY\(\$(\d+)::int\[\]\)', lambda m: replace_placeholder(m), query)
    # Then handle remaining $N
    query = re.sub(r'\$(\d+)', replace_placeholder, query)

    return query, tuple(new_args)


@asynccontextmanager
async def lifespan(app):
    """FastAPI lifespan: open database connection pool."""
    if DATABASE_URL:
        import asyncpg
        pool = await asyncpg.create_pool(DATABASE_URL, min_size=2, max_size=10)
        app.state.db = PostgresDB(pool)
    else:
        import aiosqlite
        conn = await aiosqlite.connect(f"file:{SQLITE_PATH}?mode=ro", uri=True)
        conn.row_factory = aiosqlite.Row
        app.state.db = SQLiteDB(conn)

    yield
    await app.state.db.close()
