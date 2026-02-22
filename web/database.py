"""Database connection management for the web app."""
import sqlite3
from contextlib import asynccontextmanager
from pathlib import Path

import aiosqlite

DB_PATH = Path(__file__).parent.parent / "documents.db"


def get_sync_db() -> sqlite3.Connection:
    """Synchronous connection for startup tasks."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


async def get_db() -> aiosqlite.Connection:
    """Async database connection (read-only)."""
    db = await aiosqlite.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    db.row_factory = aiosqlite.Row
    return db


@asynccontextmanager
async def lifespan(app):
    """FastAPI lifespan: open shared DB connection."""
    app.state.db = await aiosqlite.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    app.state.db.row_factory = aiosqlite.Row
    yield
    await app.state.db.close()
